#!/usr/bin/env python3
"""Flask server to receive health data from Health Auto Export iOS app."""

import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import DB_PATH, HEALTH_RECEIVER_PORT
from scripts.notify import notify_error, log_pipeline

from flask import Flask, request, jsonify

app = Flask(__name__)


def normalize_metric_name(name):
    """Convert metric name to lowercase snake_case."""
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9]+", "_", name)
    name = name.strip("_")
    return name


def normalize_date(date_str):
    """Extract YYYY-MM-DD from various date formats."""
    for fmt in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str[:fmt.count("%") + len(fmt) - fmt.count("%")], fmt).strftime("%Y-%m-%d")
        except (ValueError, IndexError):
            continue
    # Fallback: take first 10 chars if they look like a date
    if len(date_str) >= 10:
        return date_str[:10]
    return date_str


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "running"})


@app.route("/health", methods=["POST"])
def receive_health():
    try:
        payload = request.get_json(force=True)
        data = payload.get("data", payload)
        metrics = data.get("metrics", [])

        conn = sqlite3.connect(DB_PATH)
        inserted = 0

        for metric in metrics:
            metric_name = normalize_metric_name(metric.get("name", ""))
            unit = metric.get("units", "")

            for entry in metric.get("data", []):
                date_raw = entry.get("date", "")
                date = normalize_date(date_raw)
                value = entry.get("qty", 0)

                try:
                    value = float(value)
                except (TypeError, ValueError):
                    value = 0

                conn.execute(
                    "INSERT INTO health_metrics (metric_name, value, unit, date, source) "
                    "VALUES (?, ?, ?, ?, 'apple_health') "
                    "ON CONFLICT(metric_name, date, source) "
                    "DO UPDATE SET value = value + excluded.value",
                    (metric_name, value, unit, date),
                )
                inserted += 1

        conn.commit()
        conn.close()

        log_pipeline("health_receiver", "success", records_synced=inserted)
        return jsonify({"status": "ok", "records": inserted})

    except Exception as e:
        notify_error("health_receiver", str(e))
        log_pipeline("health_receiver", "error", error_message=str(e))
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=HEALTH_RECEIVER_PORT)
