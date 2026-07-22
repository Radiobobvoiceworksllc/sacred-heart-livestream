"""
config.py — Sacred Heart Catholic Church Dual Livestream Automation
Cloud-native configuration: all secrets come from environment variables.
Credential files are decoded from base64 env vars and written to /tmp at startup.

Call config.cloud_init() once at the top of automation.py before anything else.
"""

import base64
import os

# ─────────────────────────────────────────────────────────────────────────────
# GOOGLE SHEETS
# ─────────────────────────────────────────────────────────────────────────────

GOOGLE_SA_JSON_B64   = os.getenv("GOOGLE_SA_JSON_B64", "")
GOOGLE_SA_JSON       = os.getenv("GOOGLE_SA_JSON", "/tmp/google_sa.json")

SPREADSHEET_NAME     = os.getenv("SPREADSHEET_NAME", "Sacred Heart Livestream Events")
WORKSHEET_NAME       = os.getenv("WORKSHEET_NAME",   "Sheet1")

# ─────────────────────────────────────────────────────────────────────────────
# FACEBOOK GRAPH API
# ─────────────────────────────────────────────────────────────────────────────

FB_PAGE_ID           = os.getenv("FB_PAGE_ID",           "")
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
FB_GRAPH_VERSION     = "v21.0"
FB_PRIVACY           = os.getenv("FB_PRIVACY", "EVERYONE")

# ─────────────────────────────────────────────────────────────────────────────
# YOUTUBE DATA API v3
# ─────────────────────────────────────────────────────────────────────────────

YT_TOKEN_PICKLE_B64     = os.getenv("YT_TOKEN_PICKLE_B64", "")
YT_TOKEN_PICKLE         = os.getenv("YT_TOKEN_PICKLE",     "/tmp/youtube_token.pickle")

YT_CLIENT_SECRETS_B64   = os.getenv("YT_CLIENT_SECRETS_B64", "")
YT_CLIENT_SECRETS_JSON  = os.getenv("YT_CLIENT_SECRETS_JSON", "/tmp/youtube_client_secrets.json")

YT_CHANNEL_NAME      = "Sacred Heart Catholic Church - Bolivar, MO"
YT_PRIVACY_STATUS    = os.getenv("YT_PRIVACY_STATUS",   "public")
YT_STREAM_RESOLUTION = os.getenv("YT_STREAM_RESOLUTION","1080p")
YT_FRAME_RATE        = os.getenv("YT_FRAME_RATE",       "30fps")

# ─────────────────────────────────────────────────────────────────────────────
# OPERATOR NOTIFICATION EMAIL
# ─────────────────────────────────────────────────────────────────────────────

NOTIFY_ENABLED           = os.getenv("NOTIFY_ENABLED", "true").lower() == "true"
NOTIFY_SMTP_HOST         = os.getenv("NOTIFY_SMTP_HOST",     "smtp.gmail.com")
NOTIFY_SMTP_PORT         = int(os.getenv("NOTIFY_SMTP_PORT", "465"))
NOTIFY_FROM_EMAIL        = os.getenv("NOTIFY_FROM_EMAIL",    "")
NOTIFY_FROM_APP_PASSWORD = os.getenv("NOTIFY_FROM_APP_PASSWORD", "")
NOTIFY_TO_EMAILS         = os.getenv("NOTIFY_TO_EMAILS",     "")

# ─────────────────────────────────────────────────────────────────────────────
# AUTOMATION TIMING
# ─────────────────────────────────────────────────────────────────────────────

TRIGGER_WINDOW_MINUTES_MIN = int(os.getenv("TRIGGER_MIN", "13"))
TRIGGER_WINDOW_MINUTES_MAX = int(os.getenv("TRIGGER_MAX", "22"))
CLEANUP_AFTER_MINUTES      = int(os.getenv("CLEANUP_MIN", "60"))
POLL_INTERVAL_SECONDS      = int(os.getenv("POLL_INTERVAL", "60"))

# ─────────────────────────────────────────────────────────────────────────────
# SPREADSHEET COLUMN NAMES  (must exactly match your header row)
# ─────────────────────────────────────────────────────────────────────────────

COL_EVENT_NAME  = "EventName"
COL_START_DATE  = "EventStartDate"
COL_START_TIME  = "EventStartTime"
COL_END_DATE    = "EventEndDate"
COL_END_TIME    = "EventEndTime"
COL_LOCATION    = "EventLocation"
COL_DETAILS     = "EventDetails"
COL_FB_SUCCESS  = "FBEventSuccess"
COL_FB_ID       = "FBEventID"
COL_YT_SUCCESS  = "YTEventSuccess"
COL_YT_ID       = "YTEventID"

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────────────────

LOG_FILE  = os.getenv("LOG_FILE", "")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ─────────────────────────────────────────────────────────────────────────────
# CHURCH METADATA
# ─────────────────────────────────────────────────────────────────────────────

CHURCH_NAME    = "Sacred Heart Catholic Church"
CHURCH_CITY    = "Bolivar, Missouri"
CHURCH_WEBSITE = "https://sacredheartbolivar.org"

# ─────────────────────────────────────────────────────────────────────────────
# CLOUD INIT
# ─────────────────────────────────────────────────────────────────────────────

def cloud_init():
    """
    Decode base64 credential env vars and write them to /tmp so the rest of
    the codebase can treat them as normal files. Safe to call in both local
    and cloud/GitHub Actions environments.
    """
    global GOOGLE_SA_JSON, YT_TOKEN_PICKLE, YT_CLIENT_SECRETS_JSON

    if GOOGLE_SA_JSON_B64:
        GOOGLE_SA_JSON = "/tmp/google_sa.json"
        _write_b64(GOOGLE_SA_JSON_B64, GOOGLE_SA_JSON)

    if YT_TOKEN_PICKLE_B64:
        YT_TOKEN_PICKLE = "/tmp/youtube_token.pickle"
        _write_b64(YT_TOKEN_PICKLE_B64, YT_TOKEN_PICKLE)

    if YT_CLIENT_SECRETS_B64:
        YT_CLIENT_SECRETS_JSON = "/tmp/youtube_client_secrets.json"
        _write_b64(YT_CLIENT_SECRETS_B64, YT_CLIENT_SECRETS_JSON)


def _write_b64(b64_string: str, dest_path: str):
    data = base64.b64decode(b64_string.strip())
    with open(dest_path, "wb") as f:
        f.write(data)


def encode_file_to_b64(file_path: str) -> str:
    """Encode a local credential file to base64 — used by --encode-creds."""
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode()
