"""
notifier.py — Pre-event operator email notification.
Sends a Go-Live alert email 13–22 minutes before each event with
all RTMP credentials and an OBS checklist.
"""

import logging
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config

logger = logging.getLogger(__name__)


def send_golive_alert(
    event_name: str,
    start_dt: datetime,
    yt_broadcast_id: str,
    yt_rtmp_url: str,
    yt_stream_key: str,
    fb_live_id: str,
    fb_rtmps_url: str,
    spreadsheet_name: str = "",
) -> bool:
    if not config.NOTIFY_ENABLED:
        logger.debug("Notifications disabled — skipping email.")
        return True

    if not config.NOTIFY_FROM_EMAIL or not config.NOTIFY_FROM_APP_PASSWORD:
        logger.warning("NOTIFY_FROM_EMAIL or NOTIFY_FROM_APP_PASSWORD not set — skipping email.")
        return False

    recipients = [r.strip() for r in config.NOTIFY_TO_EMAILS.split(",") if r.strip()]
    if not recipients:
        logger.warning("NOTIFY_TO_EMAILS is empty — skipping email.")
        return False

    start_str = start_dt.strftime("%A, %B %-d, %Y  at  %-I:%M %p CDT")
    mins_away = int((start_dt - datetime.now()).total_seconds() / 60)
    yt_watch  = f"https://youtu.be/{yt_broadcast_id}"
    yt_studio = f"https://studio.youtube.com/video/{yt_broadcast_id}/livestreaming"
    fb_studio = f"https://www.facebook.com/live/producer/{fb_live_id}/"

    subject = f"🔴 GO LIVE IN ~{mins_away} MIN — {event_name} | Sacred Heart"

    plain = f"""
Sacred Heart Catholic Church — Live Stream Alert
─────────────────────────────────────────────────

EVENT  : {event_name}
TIME   : {start_str}
STARTS IN ~ {mins_away} MINUTES

══════════════════════════════════════════════════
  YOUTUBE STREAM SETTINGS
══════════════════════════════════════════════════

  RTMP URL   : {yt_rtmp_url}
  Stream Key : {yt_stream_key}

  Watch link : {yt_watch}
  YT Studio  : {yt_studio}

══════════════════════════════════════════════════
  FACEBOOK STREAM SETTINGS
══════════════════════════════════════════════════

  RTMPS URL  : {fb_rtmps_url}
  (Paste the entire URL above — stream key is embedded in it)

  FB Creator Studio : {fb_studio}

══════════════════════════════════════════════════
  GO-LIVE CHECKLIST
══════════════════════════════════════════════════

  [ ] Power on camera, audio, and computer running OBS
  [ ] OBS → Settings → Stream:
        Service : Custom
        Server  : {yt_rtmp_url}
        Key     : {yt_stream_key}
  [ ] obs-multi-rtmp plugin → add output:
        URL+Key : {fb_rtmps_url}
  [ ] Preview — confirm video and audio look good
  [ ] Click START STREAMING in OBS
  [ ] Confirm green Live dot in YouTube Studio
  [ ] Confirm green Live dot in Facebook Creator Studio
  [ ] Done ✓

──────────────────────────────────────────────────
{config.CHURCH_NAME} | {config.CHURCH_CITY}
This message was sent automatically by the Livestream Automation.
""".strip()

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8">
<style>
  body      {{ font-family: Arial, sans-serif; font-size:14px; color:#222; max-width:640px; margin:auto; padding:20px; }}
  h1        {{ background:#8B0000; color:#fff; padding:14px 18px; border-radius:6px; font-size:20px; margin:0 0 16px; }}
  table     {{ border-collapse:collapse; width:100%; margin:12px 0 20px; }}
  td,th     {{ padding:8px 12px; border:1px solid #ddd; }}
  th        {{ background:#f4f4f4; text-align:left; font-size:12px; color:#555; width:30%; }}
  .mono     {{ font-family:"Courier New",monospace; background:#f7f7f7; padding:2px 5px; border-radius:3px; font-size:13px; word-break:break-all; }}
  .section  {{ font-weight:bold; background:#1a1a2e; color:#fff; padding:8px 12px; border-radius:4px 4px 0 0; font-size:13px; margin-top:20px; }}
  .checklist{{ background:#f9fafb; border:1px solid #e0e0e0; border-radius:4px; padding:14px 18px; margin-top:16px; }}
  .btn      {{ display:inline-block; padding:8px 16px; border-radius:4px; text-decoration:none; font-weight:bold; color:#fff; margin-right:8px; margin-top:6px; font-size:13px; }}
  .yt       {{ background:#FF0000; }}
  .fb       {{ background:#1877F2; }}
  footer    {{ margin-top:28px; font-size:11px; color:#999; border-top:1px solid #eee; padding-top:10px; }}
</style>
</head>
<body>
<h1>🔴 Go Live in ~{mins_away} Minutes</h1>
<p><strong>{event_name}</strong><br>{start_str}</p>

<div class="section">📺 YouTube Stream Settings</div>
<table>
  <tr><th>RTMP URL</th><td><span class="mono">{yt_rtmp_url}</span></td></tr>
  <tr><th>Stream Key</th><td><span class="mono">{yt_stream_key}</span></td></tr>
  <tr><th>Watch Link</th><td><a href="{yt_watch}">{yt_watch}</a></td></tr>
</table>
<a class="btn yt" href="{yt_studio}">Open YouTube Studio →</a>

<div class="section" style="margin-top:24px;">📘 Facebook Stream Settings</div>
<table>
  <tr><th>RTMPS URL</th><td><span class="mono">{fb_rtmps_url}</span></td></tr>
  <tr><th>Note</th><td>Paste the entire URL above — the stream key is embedded in it.</td></tr>
</table>
<a class="btn fb" href="{fb_studio}">Open Facebook Creator Studio →</a>

<div class="section" style="margin-top:24px;">✅ Go-Live Checklist</div>
<div class="checklist">
<ol>
  <li>Power on camera, audio, and computer running OBS</li>
  <li>OBS → Settings → Stream → Service: <strong>Custom</strong><br>
      Server: <code>{yt_rtmp_url}</code><br>
      Key: <code>{yt_stream_key}</code></li>
  <li>obs-multi-rtmp plugin → add output → paste full Facebook RTMPS URL</li>
  <li>Preview — confirm video and audio look good</li>
  <li>Click <strong>START STREAMING</strong> in OBS</li>
  <li>Confirm green Live dot in YouTube Studio</li>
  <li>Confirm green Live dot in Facebook Creator Studio</li>
</ol>
</div>
<footer>{config.CHURCH_NAME} &bull; {config.CHURCH_CITY} &bull; {config.CHURCH_WEBSITE}<br>
Sent automatically by the Sacred Heart Livestream Automation.</footer>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{config.CHURCH_NAME} Livestream <{config.NOTIFY_FROM_EMAIL}>"
    msg["To"]      = ", ".join(recipients)
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html,  "html"))

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(config.NOTIFY_SMTP_HOST, config.NOTIFY_SMTP_PORT, context=ctx) as server:
            server.login(config.NOTIFY_FROM_EMAIL, config.NOTIFY_FROM_APP_PASSWORD)
            server.sendmail(config.NOTIFY_FROM_EMAIL, recipients, msg.as_string())
        logger.info("Go-Live alert sent to: %s", ", ".join(recipients))
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("Email auth failed. Check NOTIFY_FROM_APP_PASSWORD — must be a Gmail App Password.")
    except smtplib.SMTPException as exc:
        logger.error("SMTP error: %s", exc)
    except Exception as exc:
        logger.error("Unexpected email error: %s", exc)

    return False
