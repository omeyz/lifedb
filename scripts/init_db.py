#!/usr/bin/env python3
"""Create the life.db database and all tables."""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS bank_transactions (
    id TEXT PRIMARY KEY,
    account_name TEXT,
    description TEXT,
    amount REAL,
    currency TEXT DEFAULT 'USD',
    date TEXT,
    category TEXT,
    pending INTEGER DEFAULT 0,
    ingested_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS health_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name TEXT NOT NULL,
    value REAL,
    unit TEXT,
    date TEXT NOT NULL,
    source TEXT DEFAULT 'apple_health',
    ingested_at TEXT DEFAULT (datetime('now')),
    UNIQUE(metric_name, date, source)
);

CREATE TABLE IF NOT EXISTS screen_time (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id TEXT NOT NULL,
    usage_seconds REAL,
    device_model TEXT NOT NULL DEFAULT '',
    date TEXT NOT NULL,
    ingested_at TEXT DEFAULT (datetime('now')),
    UNIQUE(app_id, date, device_model)
);

CREATE TABLE IF NOT EXISTS texts_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    sent_count INTEGER DEFAULT 0,
    received_count INTEGER DEFAULT 0,
    ingested_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS emails_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    account TEXT NOT NULL,
    sent_count INTEGER DEFAULT 0,
    received_count INTEGER DEFAULT 0,
    ingested_at TEXT DEFAULT (datetime('now')),
    UNIQUE(date, account)
);

CREATE TABLE IF NOT EXISTS phone_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    direction TEXT,
    duration_seconds REAL DEFAULT 0,
    call_type TEXT,
    answered INTEGER,
    ingested_at TEXT DEFAULT (datetime('now')),
    UNIQUE(date, direction, duration_seconds)
);

CREATE TABLE IF NOT EXISTS ai_conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    conversation_id TEXT,
    title TEXT,
    date TEXT NOT NULL,
    message_count INTEGER DEFAULT 0,
    ingested_at TEXT DEFAULT (datetime('now')),
    UNIQUE(platform, conversation_id)
);

CREATE TABLE IF NOT EXISTS pipeline_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline TEXT NOT NULL,
    status TEXT NOT NULL,
    records_synced INTEGER DEFAULT 0,
    error_message TEXT,
    run_at TEXT DEFAULT (datetime('now'))
);

CREATE VIEW IF NOT EXISTS daily_summary AS
SELECT
    d.date,
    COALESCE(t.sent_count, 0) AS texts_sent,
    COALESCE(t.received_count, 0) AS texts_received,
    COALESCE(e.sent_count, 0) AS emails_sent,
    COALESCE(e.received_count, 0) AS emails_received,
    COALESCE(pc.call_count, 0) AS phone_calls,
    COALESCE(pc.talk_minutes, 0) AS talk_minutes,
    COALESCE(h_steps.value, 0) AS steps,
    COALESCE(h_dist.value, 0) AS distance_km,
    ROUND(COALESCE(st.screen_hours, 0), 2) AS screen_time_hours
FROM (
    SELECT DISTINCT date FROM texts_daily
    UNION SELECT DISTINCT date FROM emails_daily
    UNION SELECT DISTINCT date FROM health_metrics
    UNION SELECT DISTINCT date FROM screen_time
    UNION SELECT DISTINCT DATE(date) FROM phone_calls
) d
LEFT JOIN texts_daily t ON d.date = t.date
LEFT JOIN (
    SELECT date, SUM(sent_count) AS sent_count, SUM(received_count) AS received_count
    FROM emails_daily GROUP BY date
) e ON d.date = e.date
LEFT JOIN (
    SELECT DATE(date) AS date, COUNT(*) AS call_count,
           ROUND(SUM(duration_seconds) / 60.0, 1) AS talk_minutes
    FROM phone_calls GROUP BY DATE(date)
) pc ON d.date = pc.date
LEFT JOIN (
    SELECT date, value FROM health_metrics WHERE metric_name = 'step_count'
    UNION ALL
    SELECT date, value FROM health_metrics WHERE metric_name = 'steps'
) h_steps ON d.date = h_steps.date
LEFT JOIN health_metrics h_dist
    ON d.date = h_dist.date AND h_dist.metric_name = 'walking_running_distance'
LEFT JOIN (
    SELECT date, ROUND(SUM(usage_seconds) / 3600.0, 2) AS screen_hours
    FROM screen_time GROUP BY date
) st ON d.date = st.date
ORDER BY d.date DESC;
"""


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.close()
    print(f"Database initialized at {DB_PATH}")


if __name__ == "__main__":
    init_db()
