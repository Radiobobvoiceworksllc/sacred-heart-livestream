"""
automation.py — Main entry point for Sacred Heart Dual Livestream Automation.

Default mode (GitHub Actions):
    python automation.py          → single poll cycle, then exit

Optional modes:
    python automation.py --auth-yt         → run YouTube OAuth browser flow and save token
    python automation.py --encode-creds    → print base64 of credential files for GitHub Secrets
    python automation.py --daemon          → continuous local polling loop (for development)
"""

import argparse
import base64
import logging
import os
import sys
import time
from datetime import datetime

# ── Cloud init MUST run before any module that touches credential file paths ──
import config
config.cloud_init()

import sheets_client
import facebook_client
import youtube_client
import notifier

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("automation")


# ─────────────────────────────────────────────
#  Credential encoding helper (run locally once)
# ─────────────────────────────────────────────

def encode_credentials():
    files_to_encode = {
        "GOOGLE_SA_JSON_B64":   config.GOOGLE_SA_JSON,
        "YT_TOKEN_PICKLE_B64":  config.YT_TOKEN_PICKLE,
    }
    print("\n" + "="*60)
    print("  Copy each value below into the matching GitHub Secret")
    print("="*60)
    any_missing = False
    for secret_name, path in files_to_encode.items():
        if not os.path.exists(path):
            print(f"\n⚠️  NOT FOUND: {path}")
            print(f"   → Run --auth-yt first to generate the YouTube token,")
            print(f"     or download the Google SA JSON from Cloud Console.")
            any_missing = True
            continue
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        print(f"\n── {secret_name} ──")
        print(encoded)
    if any_missing:
        print("\n⚠️  Some files were missing. Resolve them and re-run --encode-creds.")
    print("\n" + "="*60)


# ─────────────────────────────────────────────
#  YouTube OAuth (run locally once)
# ─────────────────────────────────────────────

def run_youtube_auth():
    print("\nStarting YouTube OAuth flow — your browser will open.")
    print("Sign in with the Google account that owns the Sacred Heart YouTube channel.\n")
    from youtube_client import _get_credentials
    creds = _get_credentials()
    if creds and creds.valid:
        print(f"\n✅ YouTube token saved to: {config.YT_TOKEN_PICKLE}")
        print("   Run  python automation.py --encode-creds  next.")
    else:
        print("\n❌ OAuth flow failed. Please try again.")


# ─────────────────────────────────────────────
#  Core event processor
# ─────────────────────────────────────────────

def process_event(row: dict) -> bool:
    """
    Attempt to create FB + YT livestreams for a single pending event row.
    Partial success is preserved — IDs written for whichever platform succeeded.
    Returns True only when both platforms succeeded.
    """
    event_name = row.get("EventName", "Unnamed Event")
    start_dt   = row["_start_dt"]
    end_dt     = row.get("_end_dt")
    location   = row.get("EventLocation", "")
    details    = row.get("EventDetails", "")

    logger.info("Processing event: '%s' at %s", event_name, start_dt.strftime("%Y-%m-%d %H:%M"))

    fb_live_id  = None
    fb_rtmps    = None
    yt_bcast_id = None
    yt_rtmp_url = None
    yt_key      = None

    # ── Facebook ──────────────────────────────
    try:
        fb_data = facebook_client.create_scheduled_live(
            title       = event_name,
            description = details or f"{event_name} — Live from {config.CHURCH_NAME}",
            start_dt    = start_dt,
        )
        fb_live_id = fb_data["id"]
        fb_rtmps   = fb_data["stream_url"]
        sheets_client.update_status(
            row["_row_index"],
            fb_success=True, fb_id=fb_live_id,
            yt_success=False, yt_id="",
        )
        logger.info("✅  Facebook Live created: %s", fb_live_id)
    except Exception as exc:
        logger.error("❌  Facebook Live creation failed for '%s': %s", event_name, exc)
        sheets_client.update_status(
            row["_row_index"],
            fb_success=False, fb_id="ERROR",
            yt_success=False, yt_id="",
        )

    # ── YouTube ───────────────────────────────
    try:
        yt_bcast_id, yt_rtmp_url, yt_key = youtube_client.create_scheduled_broadcast(
            event_name = event_name,
            start_dt   = start_dt,
            end_dt     = end_dt,
            location   = location,
            details    = details,
        )
        sheets_client.update_status(
            row["_row_index"],
            fb_success = (fb_live_id is not None),
            fb_id      = fb_live_id or row.get("FBEventID", ""),
            yt_success = True,
            yt_id      = yt_bcast_id,
        )
        logger.info("✅  YouTube broadcast created: %s", yt_bcast_id)
    except Exception as exc:
        logger.error("❌  YouTube broadcast creation failed for '%s': %s", event_name, exc)
        sheets_client.update_status(
            row["_row_index"],
            fb_success = (fb_live_id is not None),
            fb_id      = fb_live_id or row.get("FBEventID", ""),
            yt_success = False,
            yt_id      = "ERROR",
        )

    # ── Notify operator if at least one platform succeeded ──
    if fb_live_id and yt_bcast_id:
        logger.info("Both platforms ready — sending Go-Live alert email.")
        notifier.send_golive_alert(
            event_name      = event_name,
            start_dt        = start_dt,
            yt_broadcast_id = yt_bcast_id,
            yt_rtmp_url     = yt_rtmp_url,
            yt_stream_key   = yt_key,
            fb_live_id      = fb_live_id,
            fb_rtmps_url    = fb_rtmps,
        )
        return True
    elif fb_live_id or yt_bcast_id:
        logger.warning(
            "Partial success for '%s' — FB: %s, YT: %s. Email not sent.",
            event_name,
            "✅" if fb_live_id  else "❌",
            "✅" if yt_bcast_id else "❌",
        )
    return False


# ─────────────────────────────────────────────
#  Poll cycle
# ─────────────────────────────────────────────

def poll():
    """
    One complete poll cycle:
      1. Delete rows more than CLEANUP_MINUTES_AFTER_START past start time.
      2. Read all rows where FBEventSuccess and YTEventSuccess are not 'TRUE'.
      3. Process rows whose start time falls within the trigger window.
    """
    logger.debug("Poll started at %s", datetime.now().strftime("%H:%M:%S"))

    # 1 — Cleanup aged rows
    try:
        deleted = sheets_client.cleanup_old_rows()
        if deleted:
            logger.info("Cleaned up %d aged row(s).", deleted)
    except Exception as exc:
        logger.error("Row cleanup error: %s", exc)

    # 2 — Fetch pending rows
    try:
        pending_rows = sheets_client.get_pending_rows()
    except Exception as exc:
        logger.error("Could not read Google Sheet: %s", exc)
        return

    if not pending_rows:
        logger.debug("No pending events found.")
        return

    logger.info("Found %d pending event(s). Checking trigger window (%d–%d min)...",
                len(pending_rows), config.TRIGGER_WINDOW_MIN, config.TRIGGER_WINDOW_MAX)

    # 3 — Process events within trigger window
    now = datetime.now(config.TZ)
    processed = 0
    for row in pending_rows:
        start_dt = row.get("_start_dt")
        if not start_dt:
            continue
        minutes_away = (start_dt - now).total_seconds() / 60.0
        if config.TRIGGER_WINDOW_MIN <= minutes_away <= config.TRIGGER_WINDOW_MAX:
            logger.info(
                "Event '%s' is %.1f min away — within trigger window.",
                row.get("EventName", "?"), minutes_away,
            )
            process_event(row)
            processed += 1
        else:
            logger.debug(
                "Event '%s' is %.1f min away — outside trigger window, skipping.",
                row.get("EventName", "?"), minutes_away,
            )

    if processed == 0:
        logger.debug("No events fell within the trigger window this cycle.")


# ─────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Sacred Heart Dual Livestream Automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--auth-yt",
        action="store_true",
        help="Run YouTube OAuth flow and save token (run locally once).",
    )
    parser.add_argument(
        "--encode-creds",
        action="store_true",
        help="Print base64-encoded credential files for GitHub Secrets (run locally once).",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help=f"Run continuously, polling every {config.POLL_INTERVAL_SECONDS}s (local dev mode).",
    )
    args = parser.parse_args()

    if args.auth_yt:
        run_youtube_auth()
        sys.exit(0)

    if args.encode_creds:
        encode_credentials()
        sys.exit(0)

    if args.daemon:
        logger.info(
            "Daemon mode — polling every %ds. Press Ctrl+C to stop.",
            config.POLL_INTERVAL_SECONDS,
        )
        while True:
            try:
                poll()
            except KeyboardInterrupt:
                logger.info("Daemon stopped by user.")
                break
            except Exception as exc:
                logger.error("Unhandled error in poll: %s", exc, exc_info=True)
            time.sleep(config.POLL_INTERVAL_SECONDS)
    else:
        # Default: single poll cycle for GitHub Actions
        poll()


if __name__ == "__main__":
    main()
