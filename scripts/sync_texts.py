#!/usr/bin/env python3
"""Sync daily text message counts from macOS chat.db (iMessage)."""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import DB_PATH, CHAT_DB, APPLE_EPOCH_OFFSET
from scripts.notify import run_pipeline


def sync():
    if not CHAT_DB.exists():
        raise FileNotFoundError(f"chat.db not found at {CHAT_DB}")

    source = sqlite3.connect(f"file:{CHAT_DB}?mode=ro", uri=True)

    # iMessage timestamps are nanoseconds since 2001-01-01
    rows = source.execute("""
        SELECT
            DATE(DATETIME(message.date / 1000000000 + ?, 'unixepoch', 'localtime')) AS msg_date,
            SUM(CASE WHEN is_from_me = 1 THEN 1 ELSE 0 END) AS sent,
            SUM(CASE WHEN is_from_me = 0 THEN 1 ELSE 0 END) AS received
        FROM message
        WHERE message.date > 0
        GROUP BY msg_date
    """, (APPLE_EPOCH_OFFSET,)).fetchall()

    source.close()

    dest = sqlite3.connect(DB_PATH)
    inserted = 0

    for msg_date, sent, received in rows:
        if not msg_date:
            continue
        dest.execute(
            "INSERT OR REPLACE INTO texts_daily (date, sent_count, received_count) "
            "VALUES (?, ?, ?)",
            (msg_date, sent, received),
        )
        inserted += 1

    dest.commit()
    dest.close()
    return inserted


if __name__ == "__main__":
    run_pipeline("sync_texts", sync)
