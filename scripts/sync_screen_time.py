#!/usr/bin/env python3
"""Sync screen time data from macOS knowledgeC.db."""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import DB_PATH, KNOWLEDGE_DB, APPLE_EPOCH_OFFSET
from scripts.notify import run_pipeline


def sync():
    if not KNOWLEDGE_DB.exists():
        raise FileNotFoundError(f"knowledgeC.db not found at {KNOWLEDGE_DB}")

    source = sqlite3.connect(f"file:{KNOWLEDGE_DB}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row

    rows = source.execute("""
        SELECT
            ZOBJECT.ZVALUESTRING AS app_id,
            SUM(ZOBJECT.ZENDDATE - ZOBJECT.ZSTARTDATE) AS usage_seconds,
            DATE(DATETIME(ZOBJECT.ZSTARTDATE + ?, 'unixepoch', 'localtime')) AS date,
            ZSYNCPEER.ZMODEL AS device_model
        FROM ZOBJECT
        LEFT JOIN ZSTRUCTUREDMETADATA ON ZOBJECT.ZSTRUCTUREDMETADATA = ZSTRUCTUREDMETADATA.Z_PK
        LEFT JOIN ZSOURCE ON ZOBJECT.ZSOURCE = ZSOURCE.Z_PK
        LEFT JOIN ZSYNCPEER ON ZSOURCE.ZDEVICEID = ZSYNCPEER.ZDEVICEID
        WHERE ZSTREAMNAME = '/app/usage'
          AND ZOBJECT.ZVALUESTRING IS NOT NULL
          AND ZOBJECT.ZSTARTDATE IS NOT NULL
          AND ZOBJECT.ZENDDATE IS NOT NULL
        GROUP BY app_id, date, device_model
    """, (APPLE_EPOCH_OFFSET,)).fetchall()

    source.close()

    if not rows:
        print("Warning: knowledgeC.db returned no screen time data. "
              "On macOS 13+, data may have moved to the Biome database.")

    dest = sqlite3.connect(DB_PATH)
    inserted = 0

    for row in rows:
        if not row["app_id"] or not row["date"]:
            continue
        # Coalesce NULL device_model to '' so the UNIQUE constraint works
        device_model = row["device_model"] or ""
        dest.execute(
            "INSERT OR REPLACE INTO screen_time "
            "(app_id, usage_seconds, device_model, date) "
            "VALUES (?, ?, ?, ?)",
            (row["app_id"], row["usage_seconds"], device_model, row["date"]),
        )
        inserted += 1

    dest.commit()
    dest.close()
    return inserted


if __name__ == "__main__":
    run_pipeline("sync_screen_time", sync)
