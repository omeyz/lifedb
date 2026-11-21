#!/usr/bin/env python3
"""Sync phone call history from macOS CallHistory.storedata."""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import DB_PATH, CALL_HISTORY_DB, APPLE_EPOCH_OFFSET
from scripts.notify import run_pipeline


def sync():
    if not CALL_HISTORY_DB.exists():
        raise FileNotFoundError(f"CallHistory.storedata not found at {CALL_HISTORY_DB}")

    source = sqlite3.connect(f"file:{CALL_HISTORY_DB}?mode=ro", uri=True)

    rows = source.execute("""
        SELECT
            DATETIME(ZDATE + ?, 'unixepoch', 'localtime') AS call_date,
            ZDURATION AS duration_seconds,
            ZORIGINATED AS originated,
            ZANSWERED AS answered,
            ZCALLTYPE AS call_type_raw
        FROM ZCALLRECORD
        WHERE ZDATE IS NOT NULL
    """, (APPLE_EPOCH_OFFSET,)).fetchall()

    source.close()

    dest = sqlite3.connect(DB_PATH)
    inserted = 0

    for call_date, duration, originated, answered, call_type_raw in rows:
        # Direction logic
        if originated == 1:
            direction = "outgoing"
        elif answered == 1:
            direction = "incoming"
        else:
            direction = "missed"

        # Call type mapping
        call_type_raw = call_type_raw or 0
        if call_type_raw == 16:
            call_type = "facetime_video"
        elif call_type_raw == 8:
            call_type = "facetime_audio"
        else:
            call_type = "regular"

        duration = duration or 0
        answered_flag = 1 if answered else 0

        # UNIQUE(date, direction, duration_seconds) constraint handles dedup
        cursor = dest.execute(
            "INSERT OR IGNORE INTO phone_calls "
            "(date, direction, duration_seconds, call_type, answered) "
            "VALUES (?, ?, ?, ?, ?)",
            (call_date, direction, duration, call_type, answered_flag),
        )
        inserted += cursor.rowcount

    dest.commit()
    dest.close()
    return inserted


if __name__ == "__main__":
    run_pipeline("sync_calls", sync)
