"""
youtube_client.py — YouTube Data API v3 broadcast creator.
"""

import logging
import os
import pickle
from datetime import datetime, timezone, timedelta
from typing import Optional

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import config

logger = logging.getLogger(__name__)

YT_SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


class YouTubeLiveError(Exception):
    pass


def _get_credentials():
    creds = None
    token_path = config.YT_TOKEN_PICKLE

    if os.path.exists(token_path):
        with open(token_path, "rb") as f:
            creds = pickle.load(f)

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as exc:
            logger.warning("Token refresh failed (%s). Re-running OAuth flow.", exc)
            creds = None

    if not creds or not creds.valid:
        if not os.path.exists(config.YT_CLIENT_SECRETS_JSON):
            raise YouTubeLiveError(
                f"YouTube client secrets not found: {config.YT_CLIENT_SECRETS_JSON}"
            )
        flow = InstalledAppFlow.from_client_secrets_file(
            config.YT_CLIENT_SECRETS_JSON, scopes=YT_SCOPES
        )
        creds = flow.run_local_server(port=0, open_browser=True)
        os.makedirs(os.path.dirname(token_path) or ".", exist_ok=True)
        with open(token_path, "wb") as f:
            pickle.dump(creds, f)
        logger.info("YouTube OAuth token saved to %s", token_path)

    return creds


def _build_service():
    return build("youtube", "v3", credentials=_get_credentials(), cache_discovery=False)


def _local_to_utc_rfc3339(dt: datetime) -> str:
    local_aware = dt.astimezone()
    utc_aware   = local_aware.astimezone(timezone.utc)
    return utc_aware.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _build_title(event_name: str) -> str:
    return f"{config.CHURCH_NAME} — {event_name}"


def _build_description(event_name: str, location: str, details: str) -> str:
    parts = [
        f"📍 {location}" if location else f"📍 {config.CHURCH_CITY}",
        "",
        details if details else "",
        "",
        config.CHURCH_WEBSITE if config.CHURCH_WEBSITE else "",
    ]
    return "\n".join(parts).strip()


def _create_broadcast(service, title, description, start_dt, end_dt) -> str:
    scheduled_start = _local_to_utc_rfc3339(start_dt)
    scheduled_end   = _local_to_utc_rfc3339(end_dt if end_dt else start_dt + timedelta(hours=3))

    body = {
        "snippet": {
            "title":              title,
            "description":        description,
            "scheduledStartTime": scheduled_start,
            "scheduledEndTime":   scheduled_end,
        },
        "status": {
            "privacyStatus":           config.YT_PRIVACY_STATUS,
            "selfDeclaredMadeForKids": False,
        },
        "contentDetails": {
            "enableAutoStart":      True,
            "enableAutoStop":       True,
            "enableClosedCaptions": False,
            "latencyPreference":    "normal",
            "monitorStream": {"enableMonitorStream": False},
        },
    }
    try:
        resp = service.liveBroadcasts().insert(
            part="snippet,status,contentDetails", body=body
        ).execute()
    except HttpError as exc:
        raise YouTubeLiveError(f"liveBroadcasts.insert failed: {exc}") from exc

    broadcast_id = resp["id"]
    logger.info("Created YouTube broadcast ID: %s", broadcast_id)
    return broadcast_id


def _get_or_create_stream(service, title) -> tuple:
    try:
        list_resp = service.liveStreams().list(
            part="id,snippet,cdn,status", mine=True, maxResults=10
        ).execute()
        for item in list_resp.get("items", []):
            status = item.get("status", {}).get("streamStatus", "")
            if status in ("active", "ready", "inactive"):
                stream_id  = item["id"]
                ingestion  = item["cdn"]["ingestionInfo"]
                rtmp_url   = ingestion["ingestionAddress"]
                stream_key = ingestion["streamName"]
                logger.info("Reusing existing YouTube live stream: %s", stream_id)
                return stream_id, rtmp_url, stream_key
    except HttpError as exc:
        logger.warning("Could not list existing streams: %s", exc)

    body = {
        "snippet": {"title": title},
        "cdn": {
            "frameRate":    config.YT_FRAME_RATE,
            "resolution":   config.YT_STREAM_RESOLUTION,
            "ingestionType": "rtmp",
        },
        "contentDetails": {"isReusable": True},
    }
    try:
        resp = service.liveStreams().insert(
            part="snippet,cdn,contentDetails", body=body
        ).execute()
    except HttpError as exc:
        raise YouTubeLiveError(f"liveStreams.insert failed: {exc}") from exc

    stream_id  = resp["id"]
    ingestion  = resp["cdn"]["ingestionInfo"]
    rtmp_url   = ingestion["ingestionAddress"]
    stream_key = ingestion["streamName"]
    logger.info("Created new YouTube live stream: %s", stream_id)
    return stream_id, rtmp_url, stream_key


def _bind_broadcast_to_stream(service, broadcast_id, stream_id):
    try:
        service.liveBroadcasts().bind(
            part="id,contentDetails", id=broadcast_id, streamId=stream_id
        ).execute()
        logger.info("Bound broadcast %s → stream %s.", broadcast_id, stream_id)
    except HttpError as exc:
        raise YouTubeLiveError(f"liveBroadcasts.bind failed: {exc}") from exc


def create_scheduled_broadcast(
    event_name: str,
    start_dt: datetime,
    end_dt: Optional[datetime] = None,
    location: str = "",
    details: str = "",
) -> tuple:
    title       = _build_title(event_name)
    description = _build_description(event_name, location, details)
    service     = _build_service()

    broadcast_id             = _create_broadcast(service, title, description, start_dt, end_dt)
    stream_id, rtmp_url, key = _get_or_create_stream(service, title)
    _bind_broadcast_to_stream(service, broadcast_id, stream_id)

    logger.info(
        "YouTube broadcast ready.\n"
        "  Broadcast ID : %s\n"
        "  Watch URL    : https://youtu.be/%s\n"
        "  RTMP URL     : %s\n"
        "  Stream Key   : %s",
        broadcast_id, broadcast_id, rtmp_url, key,
    )
    return broadcast_id, rtmp_url, key


def delete_broadcast(broadcast_id: str) -> bool:
    try:
        _build_service().liveBroadcasts().delete(id=broadcast_id).execute()
        logger.info("Deleted YouTube broadcast %s.", broadcast_id)
        return True
    except HttpError as exc:
        logger.warning("Could not delete YouTube broadcast %s: %s", broadcast_id, exc)
        return False
