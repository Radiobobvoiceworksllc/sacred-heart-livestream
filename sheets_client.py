"""
sheets_client.py — Google Sheets interface for the livestream automation.
"""

import logging
from datetime import datetime, date, time
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

import config

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _parse_datetime(date_val: str, time_val: str) -> Optional[datetime]:
    date_val = str(date_val).strip()
    time_val = str(time_val).strip()
    if not date_val or not time_val:
        return None

    parsed_date: Optional[date] = None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%#m/%#d/%Y"):
        try:
            parsed_date = datetime.strptime(date_val, fmt).date()
            break
        except ValueError:
            continue
    if parsed_date is None:
        logger.warning("Cannot parse date: %r", date_val)
        return None

    parsed_time: Optional[time] = None
    for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M", "%H:%M:%S"):
        try:
            parsed_time = datetime.strptime(time_val.upper(), fmt).time()
            break
        except ValueError:
            continue
    if parsed_time is None:
        logger.warning("Cannot parse time: %r", time_val)
        return None

    return datetime.combine(parsed_date, parsed_time)


class SheetsClient:
    def __init__(self):
        creds = Credentials.from_service_account_file(
            config.GOOGLE_SA_JSON, scopes=SCOPES
        )
        gc = gspread.authorize(creds)

        name_or_id = config.SPREADSHEET_NAME
        if name_or_id.startswith("http") or (
            "/" not in name_or_id and len(name_or_id) > 40
        ):
            key = name_or_id.split("/")[-2] if "/" in name_or_id else name_or_id
            sh = gc.open_by_key(key)
        else:
            sh = gc.open(name_or_id)

        self.ws = sh.worksheet(config.WORKSHEET_NAME)
        logger.info("Connected to sheet '%s' / '%s'",
                    config.SPREADSHEET_NAME, config.WORKSHEET_NAME)

    # ── Reading ───────────────────────────────────────────────────────────────

    def get_all_records(self) -> list:
        records = self.ws.get_all_records(default_blank="")
        for i, rec in enumerate(records):
            rec["_row_index"] = i + 2
        return records

    def get_pending_events(self) -> list:
        all_rows = self.get_all_records()
        pending = []
        for row in all_rows:
            fb_done = str(row.get(config.COL_FB_SUCCESS, "")).upper() == "TRUE"
            yt_done = str(row.get(config.COL_YT_SUCCESS, "")).upper() == "TRUE"
            if fb_done and yt_done:
                continue
            dt = _parse_datetime(
                row.get(config.COL_START_DATE, ""),
                row.get(config.COL_START_TIME, ""),
            )
            if dt is None:
                continue
            row["_start_dt"] = dt
            pending.append(row)
        return pending

    # ── Writing ───────────────────────────────────────────────────────────────

    def _col_index(self, header_name: str) -> Optional[int]:
        headers = self.ws.row_values(1)
        try:
            return headers.index(header_name) + 1
        except ValueError:
            logger.error("Header '%s' not found in sheet.", header_name)
            return None

    def mark_facebook_success(self, row_index: int, live_id: str):
        col_s = self._col_index(config.COL_FB_SUCCESS)
        col_i = self._col_index(config.COL_FB_ID)
        if col_s and col_i:
            self.ws.update_cell(row_index, col_s, "TRUE")
            self.ws.update_cell(row_index, col_i, live_id)
            logger.info("Row %d → Facebook: TRUE / %s", row_index, live_id)

    def mark_facebook_failure(self, row_index: int, error: str = "ERROR"):
        col_s = self._col_index(config.COL_FB_SUCCESS)
        if col_s:
            self.ws.update_cell(row_index, col_s, f"FALSE: {error[:80]}")
            logger.info("Row %d → Facebook: FAILED (%s)", row_index, error)

    def mark_youtube_success(self, row_index: int, broadcast_id: str):
        col_s = self._col_index(config.COL_YT_SUCCESS)
        col_i = self._col_index(config.COL_YT_ID)
        if col_s and col_i:
            self.ws.update_cell(row_index, col_s, "TRUE")
            self.ws.update_cell(row_index, col_i, broadcast_id)
            logger.info("Row %d → YouTube: TRUE / %s", row_index, broadcast_id)

    def mark_youtube_failure(self, row_index: int, error: str = "ERROR"):
        col_s = self._col_index(config.COL_YT_SUCCESS)
        if col_s:
            self.ws.update_cell(row_index, col_s, f"FALSE: {error[:80]}")
            logger.info("Row %d → YouTube: FAILED (%s)", row_index, error)

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def delete_aged_rows(self, now: datetime) -> int:
        all_rows = self.get_all_records()
        rows_to_delete = []
        for row in all_rows:
            dt = _parse_datetime(
                row.get(config.COL_START_DATE, ""),
                row.get(config.COL_START_TIME, ""),
            )
            if dt is None:
                continue
            elapsed = (now - dt).total_seconds() / 60.0
            if elapsed > config.CLEANUP_AFTER_MINUTES:
                rows_to_delete.append(row["_row_index"])

        for row_idx in sorted(rows_to_delete, reverse=True):
            self.ws.delete_rows(row_idx)
            logger.info("Deleted aged-out row %d.", row_idx)

        return len(rows_to_delete)
