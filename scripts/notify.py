#!/usr/bin/env python3
"""Discord webhook notifications and pipeline run wrapper."""

import sqlite3
import traceback
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import DB_PATH, DISCORD_WEBHOOK_URL

# Embed colors
COLOR_GREEN = 0x2ECC71
COLOR_RED = 0xE74C3C
COLOR_BLUE = 0x3498DB


def send_discord(message, title=None, color=COLOR_BLUE):
    """Post an embed to the Discord webhook."""
    if not DISCORD_WEBHOOK_URL:
        return  # notifications disabled (DISCORD_WEBHOOK_URL not set)
    embed = {"description": message, "color": color}
    if title:
        embed["title"] = title

    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]})
        resp.raise_for_status()
    except Exception as e:
        print(f"Discord webhook failed: {e}", file=sys.stderr)


def notify_error(pipeline_name, error_msg):
    """Red embed with error details."""
    send_discord(
        f"```\n{error_msg}\n```",
        title=f"\u274c {pipeline_name} — ERROR",
        color=COLOR_RED,
    )


def notify_success(pipeline_name, records_synced):
    """Green embed with record count."""
    send_discord(
        f"Synced **{records_synced}** records.",
        title=f"\u2705 {pipeline_name} — OK",
        color=COLOR_GREEN,
    )


def notify_reminder(message):
    """Blue embed for reminders."""
    send_discord(message, title="\U0001f514 Reminder", color=COLOR_BLUE)


def log_pipeline(pipeline_name, status, records_synced=0, error_message=None):
    """Write a row to the pipeline_log table."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO pipeline_log (pipeline, status, records_synced, error_message) "
        "VALUES (?, ?, ?, ?)",
        (pipeline_name, status, records_synced, error_message),
    )
    conn.commit()
    conn.close()


def run_pipeline(pipeline_name, func):
    """Call func(), log result, send Discord notification. Re-raise on failure."""
    try:
        records = func()
        records = records or 0
        log_pipeline(pipeline_name, "success", records_synced=records)
        notify_success(pipeline_name, records)
        return records
    except Exception:
        tb = traceback.format_exc()
        log_pipeline(pipeline_name, "error", error_message=tb)
        notify_error(pipeline_name, tb[-1500:])  # trim for Discord limit
        raise
