"""
facebook_client.py — Facebook Graph API livestream creator.
"""

import logging
import calendar
from datetime import datetime
from typing import Optional

import requests
import config

logger = logging.getLogger(__name__)
GRAPH_BASE = f"https://graph.facebook.com/{config.FB_GRAPH_VERSION}"


class FacebookLiveError(Exception):
    pass


def _build_title(event_name: str) -> str:
    return f"{config.CHURCH_NAME} — {event_name}"


def _build_description(event_name: str, location: str, details: str) -> str:
    parts = [
        f"📍 {location}" if location else "",
        details if details else "",
        f"\n{config.CHURCH_WEBSITE}" if config.CHURCH_WEBSITE else "",
    ]
    return "\n".join(p for p in parts if p).strip()


def create_scheduled_live(
    event_name: str,
    start_dt: datetime,
    end_dt: Optional[datetime] = None,
    location: str = "",
    details: str = "",
) -> str:
    if not config.FB_PAGE_ID:
        raise FacebookLiveError("FB_PAGE_ID is not set.")
    if not config.FB_PAGE_ACCESS_TOKEN:
        raise FacebookLiveError("FB_PAGE_ACCESS_TOKEN is not set.")

    planned_start_unix = calendar.timegm(start_dt.timetuple())

    payload: dict = {
        "title":              _build_title(event_name),
        "description":        _build_description(event_name, location, details),
        "status":             "SCHEDULED_UNPUBLISHED",
        "planned_start_time": planned_start_unix,
        "privacy":            f'{{"value":"{config.FB_PRIVACY}"}}',
        "access_token":       config.FB_PAGE_ACCESS_TOKEN,
    }
    if end_dt:
        payload["stop_live_video_at_end"] = "true"
        payload["scheduled_end_time"] = calendar.timegm(end_dt.timetuple())

    url = f"{GRAPH_BASE}/{config.FB_PAGE_ID}/live_videos"
    logger.info("Creating Facebook scheduled live: '%s' at %s",
                payload["title"], start_dt.strftime("%Y-%m-%d %H:%M"))

    try:
        response = requests.post(url, data=payload, timeout=30)
        data = response.json()
    except requests.RequestException as exc:
        raise FacebookLiveError(f"Network error: {exc}") from exc

    if "error" in data:
        err = data["error"]
        msg = f"[{err.get('code')}] {err.get('message', 'Unknown error')}"
        logger.error("Facebook API error: %s", msg)
        raise FacebookLiveError(msg)

    live_id = data.get("id")
    if not live_id:
        raise FacebookLiveError(f"No 'id' in response: {data}")

    stream_url = data.get("stream_url", "")
    secure_url = data.get("secure_stream_url", "")
    logger.info("Facebook Live created. ID: %s\n  RTMP : %s\n  RTMPS: %s",
                live_id, stream_url, secure_url)

    return str(live_id)


def get_stream_key(live_video_id: str) -> dict:
    url = f"{GRAPH_BASE}/{live_video_id}"
    params = {
        "fields": "id,title,status,stream_url,secure_stream_url",
        "access_token": config.FB_PAGE_ACCESS_TOKEN,
    }
    try:
        response = requests.get(url, params=params, timeout=20)
        return response.json()
    except requests.RequestException as exc:
        logger.warning("Could not fetch FB stream key for %s: %s", live_video_id, exc)
        return {}


def delete_live_video(live_video_id: str) -> bool:
    url = f"{GRAPH_BASE}/{live_video_id}"
    params = {"access_token": config.FB_PAGE_ACCESS_TOKEN}
    try:
        response = requests.delete(url, params=params, timeout=20)
        data = response.json()
        if data.get("success"):
            logger.info("Deleted Facebook live video %s.", live_video_id)
            return True
        return False
    except requests.RequestException as exc:
        logger.warning("Error deleting FB live %s: %s", live_video_id, exc)
        return False
