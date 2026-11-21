#!/usr/bin/env python3
"""Local web dashboard for the life database."""

import re
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import DB_PATH, DASHBOARD_PORT

from flask import Flask, jsonify, request, render_template_string

app = Flask(__name__)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.route("/api/insight")
def api_insight():
    """Return the most recent generated insight."""
    conn = get_db()
    row = conn.execute(
        "SELECT message, long_message, model, generated_at, input_tokens, output_tokens "
        "FROM insights ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        return jsonify({"message": None, "generated_at": None}), 200
    return jsonify(dict(row))


@app.route("/api/summary")
def api_summary():
    target = request.args.get("date", date.today().isoformat())
    days = int(request.args.get("days", 7))
    yesterday = (date.fromisoformat(target) - timedelta(days=1)).isoformat()

    conn = get_db()

    def day_row(d):
        r = conn.execute("SELECT * FROM daily_summary WHERE date = ?", (d,)).fetchone()
        if r:
            return dict(r)
        return {}

    today_data = day_row(target)
    yesterday_data = day_row(yesterday)

    # Period range
    period_start = (date.fromisoformat(target) - timedelta(days=days)).isoformat()
    prior_start = (date.fromisoformat(period_start) - timedelta(days=days)).isoformat()

    # Period averages
    avg = conn.execute("""
        SELECT
            ROUND(AVG(texts_sent), 1) AS texts_sent,
            ROUND(AVG(texts_received), 1) AS texts_received,
            ROUND(AVG(emails_sent), 1) AS emails_sent,
            ROUND(AVG(emails_received), 1) AS emails_received,
            ROUND(AVG(phone_calls), 1) AS phone_calls,
            ROUND(AVG(talk_minutes), 1) AS talk_minutes,
            ROUND(AVG(steps), 0) AS steps,
            ROUND(AVG(distance_km), 2) AS distance_km,
            ROUND(AVG(screen_time_hours), 2) AS screen_time_hours
        FROM daily_summary WHERE date BETWEEN ? AND ?
    """, (period_start, target)).fetchone()
    avg_data = dict(avg) if avg else {}

    # Period totals (sums over selected range)
    period_totals = conn.execute("""
        SELECT
            COALESCE(SUM(texts_sent), 0) AS texts_sent,
            COALESCE(SUM(texts_received), 0) AS texts_received,
            COALESCE(SUM(emails_sent), 0) AS emails_sent,
            COALESCE(SUM(emails_received), 0) AS emails_received,
            COALESCE(SUM(phone_calls), 0) AS phone_calls,
            ROUND(COALESCE(SUM(talk_minutes), 0), 1) AS talk_minutes,
            COALESCE(SUM(steps), 0) AS steps,
            ROUND(COALESCE(SUM(distance_km), 0), 2) AS distance_km,
            ROUND(COALESCE(SUM(screen_time_hours), 0), 1) AS screen_time_hours
        FROM daily_summary WHERE date BETWEEN ? AND ?
    """, (period_start, target)).fetchone()
    period_totals_data = dict(period_totals) if period_totals else {}

    # Prior period totals (for comparison)
    prior_totals = conn.execute("""
        SELECT
            COALESCE(SUM(texts_sent), 0) AS texts_sent,
            COALESCE(SUM(texts_received), 0) AS texts_received,
            COALESCE(SUM(emails_sent), 0) AS emails_sent,
            COALESCE(SUM(emails_received), 0) AS emails_received,
            COALESCE(SUM(phone_calls), 0) AS phone_calls,
            ROUND(COALESCE(SUM(talk_minutes), 0), 1) AS talk_minutes,
            COALESCE(SUM(steps), 0) AS steps,
            ROUND(COALESCE(SUM(distance_km), 0), 2) AS distance_km,
            ROUND(COALESCE(SUM(screen_time_hours), 0), 1) AS screen_time_hours
        FROM daily_summary WHERE date BETWEEN ? AND ?
    """, (prior_start, period_start)).fetchone()
    prior_totals_data = dict(prior_totals) if prior_totals else {}

    # Spending today
    spend_today = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM bank_transactions WHERE date = ?",
        (target,)
    ).fetchone()

    spend_yesterday = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM bank_transactions WHERE date = ?",
        (yesterday,)
    ).fetchone()

    spend_avg = conn.execute(
        "SELECT ROUND(COALESCE(SUM(amount) / CAST(? AS REAL), 0), 2) AS avg FROM bank_transactions WHERE date BETWEEN ? AND ?",
        (days, period_start, target)
    ).fetchone()

    # Spending transaction count today
    spend_count_today = conn.execute(
        "SELECT COUNT(*) AS count FROM bank_transactions WHERE date = ?",
        (target,)
    ).fetchone()

    # Spending transaction count for period
    spend_count_period = conn.execute(
        "SELECT COUNT(*) AS count FROM bank_transactions WHERE date BETWEEN ? AND ?",
        (period_start, target)
    ).fetchone()

    # Spending for period and prior period
    spend_period = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM bank_transactions WHERE date BETWEEN ? AND ?",
        (period_start, target)
    ).fetchone()
    spend_prior = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM bank_transactions WHERE date BETWEEN ? AND ?",
        (prior_start, period_start)
    ).fetchone()

    # AI conversations today / yesterday / avg
    ai_today = conn.execute(
        "SELECT COUNT(*) AS count FROM ai_conversations WHERE date = ?", (target,)
    ).fetchone()
    ai_yesterday = conn.execute(
        "SELECT COUNT(*) AS count FROM ai_conversations WHERE date = ?", (yesterday,)
    ).fetchone()
    ai_avg = conn.execute(
        "SELECT ROUND(COUNT(*) / CAST(? AS REAL), 1) AS avg FROM ai_conversations WHERE date BETWEEN ? AND ?",
        (days, period_start, target)
    ).fetchone()
    ai_period = conn.execute(
        "SELECT COUNT(*) AS count FROM ai_conversations WHERE date BETWEEN ? AND ?",
        (period_start, target)
    ).fetchone()
    ai_prior = conn.execute(
        "SELECT COUNT(*) AS count FROM ai_conversations WHERE date BETWEEN ? AND ?",
        (prior_start, period_start)
    ).fetchone()
    ai_platforms = conn.execute(
        "SELECT platform, COUNT(*) AS count FROM ai_conversations WHERE date = ? GROUP BY platform",
        (target,)
    ).fetchone()
    ai_platforms_list = conn.execute(
        "SELECT platform, COUNT(*) AS count FROM ai_conversations WHERE date = ? GROUP BY platform",
        (target,)
    ).fetchall()
    ai_platforms_period = conn.execute(
        "SELECT platform, COUNT(*) AS count FROM ai_conversations WHERE date BETWEEN ? AND ? GROUP BY platform",
        (period_start, target)
    ).fetchall()

    # Last synced per pipeline
    pipelines = conn.execute("""
        SELECT pipeline, status, records_synced, run_at
        FROM pipeline_log
        WHERE id IN (SELECT MAX(id) FROM pipeline_log GROUP BY pipeline)
        ORDER BY pipeline
    """).fetchall()

    conn.close()

    return jsonify({
        "date": target,
        "days": days,
        "today": today_data,
        "yesterday": yesterday_data,
        "avg_7d": avg_data,
        "period": period_totals_data,
        "prior_period": prior_totals_data,
        "spending": {
            "today": spend_today["total"] if spend_today else 0,
            "yesterday": spend_yesterday["total"] if spend_yesterday else 0,
            "avg_7d": spend_avg["avg"] if spend_avg else 0,
            "txn_count_today": spend_count_today["count"] if spend_count_today else 0,
            "txn_count_period": spend_count_period["count"] if spend_count_period else 0,
            "period_total": spend_period["total"] if spend_period else 0,
            "prior_period_total": spend_prior["total"] if spend_prior else 0,
        },
        "ai": {
            "today": ai_today["count"] if ai_today else 0,
            "yesterday": ai_yesterday["count"] if ai_yesterday else 0,
            "avg_7d": ai_avg["avg"] if ai_avg else 0,
            "period": ai_period["count"] if ai_period else 0,
            "prior_period": ai_prior["count"] if ai_prior else 0,
            "platforms": {r["platform"]: r["count"] for r in ai_platforms_list},
            "platforms_period": {r["platform"]: r["count"] for r in ai_platforms_period},
        },
        "pipelines": [dict(p) for p in pipelines],
    })


@app.route("/api/trends")
def api_trends():
    metric = request.args.get("metric", "texts")
    days = int(request.args.get("days", 30))
    end = request.args.get("end", date.today().isoformat())
    start = (date.fromisoformat(end) - timedelta(days=days)).isoformat()

    conn = get_db()

    if metric == "texts":
        rows = conn.execute(
            "SELECT date, sent_count AS sent, received_count AS received FROM texts_daily WHERE date BETWEEN ? AND ? ORDER BY date",
            (start, end)
        ).fetchall()
    elif metric == "emails":
        rows = conn.execute(
            "SELECT date, SUM(sent_count) AS sent, SUM(received_count) AS received FROM emails_daily WHERE date BETWEEN ? AND ? GROUP BY date ORDER BY date",
            (start, end)
        ).fetchall()
    elif metric == "calls":
        rows = conn.execute("""
            SELECT DATE(date) AS date,
                SUM(CASE WHEN direction!='missed' THEN 1 ELSE 0 END) AS calls,
                SUM(CASE WHEN direction='missed' THEN 1 ELSE 0 END) AS missed,
                ROUND(SUM(duration_seconds)/60.0, 1) AS minutes
            FROM phone_calls WHERE DATE(date) BETWEEN ? AND ?
            GROUP BY DATE(date) ORDER BY date
        """, (start, end)).fetchall()
    elif metric == "steps":
        rows = conn.execute(
            "SELECT date, value FROM health_metrics WHERE metric_name = 'step_count' AND date BETWEEN ? AND ? ORDER BY date",
            (start, end)
        ).fetchall()
    elif metric == "distance":
        rows = conn.execute(
            "SELECT date, value FROM health_metrics WHERE metric_name = 'walking_running_distance' AND date BETWEEN ? AND ? ORDER BY date",
            (start, end)
        ).fetchall()
    elif metric == "screen_time":
        rows = conn.execute("""
            WITH RECURSIVE dates(date) AS (
                VALUES(?)
                UNION ALL
                SELECT date(date, '+1 day') FROM dates WHERE date < ?
            )
            SELECT d.date, COALESCE(ROUND(SUM(s.usage_seconds)/3600.0, 2), 0) AS hours
            FROM dates d
            LEFT JOIN screen_time s ON d.date = s.date
            GROUP BY d.date ORDER BY d.date
        """, (start, end)).fetchall()
    elif metric == "screen_time_apps":
        rows = conn.execute(
            "SELECT app_id, ROUND(SUM(usage_seconds)/3600.0, 2) AS hours FROM screen_time WHERE date BETWEEN ? AND ? GROUP BY app_id ORDER BY hours DESC LIMIT 15",
            (start, end)
        ).fetchall()
    elif metric == "spending":
        rows = conn.execute(
            "SELECT date, SUM(amount) AS total FROM bank_transactions WHERE date BETWEEN ? AND ? GROUP BY date ORDER BY date",
            (start, end)
        ).fetchall()
    elif metric == "ai":
        rows = conn.execute(
            "SELECT date, platform, COUNT(*) AS count FROM ai_conversations WHERE date BETWEEN ? AND ? GROUP BY date, platform ORDER BY date",
            (start, end)
        ).fetchall()
    elif metric == "spending_count":
        rows = conn.execute(
            "SELECT date, COUNT(*) AS count, SUM(amount) AS total FROM bank_transactions WHERE date BETWEEN ? AND ? GROUP BY date ORDER BY date",
            (start, end)
        ).fetchall()
    else:
        conn.close()
        return jsonify({"error": f"Unknown metric: {metric}"}), 400

    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/spending")
def api_spending():
    end = request.args.get("end", date.today().isoformat())
    start = request.args.get("start", (date.fromisoformat(end) - timedelta(days=30)).isoformat())

    conn = get_db()

    transactions = conn.execute(
        "SELECT id, account_name, description, amount, date FROM bank_transactions WHERE date BETWEEN ? AND ? ORDER BY date DESC",
        (start, end)
    ).fetchall()

    by_account = conn.execute(
        "SELECT account_name, SUM(amount) AS total FROM bank_transactions WHERE date BETWEEN ? AND ? GROUP BY account_name",
        (start, end)
    ).fetchall()

    monthly = conn.execute("""
        SELECT strftime('%Y-%m', date) AS month,
            SUM(CASE WHEN amount >= 0 THEN amount ELSE 0 END) AS income,
            SUM(CASE WHEN amount < 0 THEN amount ELSE 0 END) AS expenses,
            SUM(amount) AS net,
            COUNT(*) AS count
        FROM bank_transactions WHERE date BETWEEN ? AND ?
        GROUP BY month ORDER BY month DESC
    """, (start, end)).fetchall()

    search = request.args.get("search", "")
    if search:
        transactions = conn.execute(
            "SELECT id, account_name, description, amount, date FROM bank_transactions WHERE date BETWEEN ? AND ? AND description LIKE ? ORDER BY date DESC",
            (start, end, f"%{search}%")
        ).fetchall()

    conn.close()

    return jsonify({
        "transactions": [dict(r) for r in transactions],
        "by_account": [dict(r) for r in by_account],
        "monthly": [dict(r) for r in monthly],
    })


@app.route("/api/pipelines")
def api_pipelines():
    conn = get_db()
    rows = conn.execute("""
        SELECT pipeline, status, records_synced, error_message, run_at
        FROM pipeline_log
        WHERE id IN (SELECT MAX(id) FROM pipeline_log GROUP BY pipeline)
        ORDER BY pipeline
    """).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


FORBIDDEN_SQL = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|ATTACH|DETACH|REINDEX|VACUUM|PRAGMA\s+\w+\s*=)",
    re.IGNORECASE,
)


@app.route("/api/query", methods=["POST"])
def api_query():
    body = request.get_json(force=True)
    sql = body.get("sql", "").strip()

    if not sql:
        return jsonify({"error": "Empty query"}), 400

    if FORBIDDEN_SQL.match(sql):
        return jsonify({"error": "Only read-only queries are allowed."}), 403

    conn = get_db()
    try:
        cursor = conn.execute(sql)
        columns = [d[0] for d in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        conn.close()
        return jsonify({"columns": columns, "rows": [list(r) for r in rows]})
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 400


# ---------------------------------------------------------------------------
# HTML Template
# ---------------------------------------------------------------------------

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Omar's SQL</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🗄️</text></svg>">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://cdn.tailwindcss.com"></script>
<style>
  body { font-family: 'Inter', system-ui, -apple-system, sans-serif; background: #f8f9fb; }
  .tab-active { border-bottom: 2px solid #378ADD; color: #378ADD; font-weight: 600; }
  .tab-btn { border-bottom: 2px solid transparent; }
  .tab-btn:hover { color: #378ADD; }
  .stat-card { transition: transform 0.15s, box-shadow 0.15s; }
  .stat-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.06); }
  .health-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
  .dot-green { background: #1D9E75; }
  .dot-red { background: #D85A30; }
  .dot-yellow { background: #EF9F27; }
  canvas { max-height: 320px; }
  #sql-input { font-family: 'SF Mono', 'Fira Code', monospace; }
  .range-btn { padding: 2px 10px; border-radius: 4px; font-size: 12px; cursor: pointer; border: 1px solid #e5e7eb; background: white; color: #6b7280; }
  .range-btn.active { background: #378ADD; color: white; border-color: #378ADD; }
  .chart-card { background: white; border-radius: 12px; border: 1px solid #e5e7eb; padding: 20px; }
  @media (max-width: 640px) {
    .chart-card { padding: 14px; }
    canvas { max-height: 240px; }
    .range-btn { padding: 2px 7px; font-size: 11px; }
  }
</style>
</head>
<body class="text-gray-800">

<!-- Header -->
<header class="bg-white border-b border-gray-200 sticky top-0 z-50">
  <div class="max-w-7xl mx-auto px-3 sm:px-6">
    <!-- Top row: title + global range -->
    <div class="flex items-center justify-between h-11 sm:h-12">
      <span class="text-base sm:text-lg font-bold text-gray-900 tracking-tight">Omar's SQL</span>
      <div class="flex gap-1" id="global-range">
        <button onclick="setGlobalDays(1)" class="range-btn" data-days="1">24h</button>
        <button onclick="setGlobalDays(7)" class="range-btn active" data-days="7">7d</button>
        <button onclick="setGlobalDays(30)" class="range-btn" data-days="30">30d</button>
        <button onclick="setGlobalDays(90)" class="range-btn" data-days="90">90d</button>
      </div>
    </div>
    <!-- Tab row -->
    <nav class="flex gap-0 -mb-px overflow-x-auto">
      <button onclick="showTab('overview')" id="tab-overview" class="tab-btn tab-active px-3 py-2 text-xs sm:text-sm whitespace-nowrap">Overview</button>
      <button onclick="showTab('spending')" id="tab-spending" class="tab-btn px-3 py-2 text-xs sm:text-sm whitespace-nowrap">Spending</button>
      <button onclick="showTab('pipelines')" id="tab-pipelines" class="tab-btn px-3 py-2 text-xs sm:text-sm whitespace-nowrap">Pipelines</button>
      <button onclick="showTab('sql')" id="tab-sql" class="tab-btn px-3 py-2 text-xs sm:text-sm whitespace-nowrap">SQL Console</button>
    </nav>
  </div>
</header>

<main class="max-w-7xl mx-auto px-3 sm:px-6 py-4 sm:py-6">

<!-- ==================== OVERVIEW ==================== -->
<section id="page-overview">
  <!-- Summary Cards -->
  <div id="summary-cards" class="mb-8"></div>
  <!-- Charts -->
  <div id="overview-charts" class="space-y-4 sm:space-y-6"></div>
</section>

<!-- ==================== SPENDING ==================== -->
<section id="page-spending" class="hidden">
  <div class="flex flex-col sm:flex-row sm:items-center justify-between mb-5 gap-3">
    <h2 class="text-xl font-bold">Spending</h2>
    <div class="flex flex-wrap gap-2 items-center">
      <input type="date" id="spend-start" class="border rounded px-2 py-1 text-sm w-32">
      <span class="text-gray-400">to</span>
      <input type="date" id="spend-end" class="border rounded px-2 py-1 text-sm w-32">
      <input type="text" id="spend-search" placeholder="Search..." class="border rounded px-2 py-1 text-sm w-32 sm:w-40">
      <button onclick="loadSpending()" class="bg-blue-600 text-white px-3 py-1 rounded text-sm">Go</button>
    </div>
  </div>
  <div class="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6 mb-4 sm:mb-6">
    <div class="chart-card"><h3 class="font-semibold mb-3 text-sm text-gray-600">By Account</h3><canvas id="chart-by-account"></canvas></div>
    <div class="lg:col-span-2 chart-card">
      <h3 class="font-semibold mb-3 text-sm text-gray-600">Monthly Totals</h3>
      <div id="monthly-table" class="overflow-x-auto"></div>
    </div>
  </div>
  <div class="chart-card">
    <h3 class="font-semibold mb-3 text-sm text-gray-600">Transactions</h3>
    <div id="txn-table" class="overflow-x-auto max-h-96 overflow-y-auto"></div>
  </div>
</section>

<!-- ==================== PIPELINES ==================== -->
<section id="page-pipelines" class="hidden">
  <h2 class="text-xl font-bold mb-5">Pipeline Health</h2>
  <div id="pipeline-table" class="chart-card overflow-x-auto"></div>
</section>

<!-- ==================== SQL ==================== -->
<section id="page-sql" class="hidden">
  <h2 class="text-xl font-bold mb-5">SQL Console</h2>
  <div class="chart-card mb-4">
    <div class="flex gap-2 mb-2 flex-wrap">
      <select id="sql-examples" onchange="loadExample()" class="border rounded px-2 py-1 text-sm text-gray-600">
        <option value="">Example queries...</option>
        <optgroup label="Overview">
          <option value="SELECT * FROM daily_summary WHERE date = date('now')">Today's summary</option>
          <option value="SELECT * FROM daily_summary WHERE date >= date('now', '-7 days') ORDER BY date DESC">This week's summary</option>
          <option value="SELECT * FROM daily_summary WHERE date >= date('now', '-30 days') ORDER BY date DESC">Last 30 days summary</option>
        </optgroup>
        <optgroup label="Communication">
          <option value="SELECT * FROM texts_daily WHERE date >= date('now', '-7 days') ORDER BY date DESC">This week's texts</option>
          <option value="SELECT date, SUM(sent_count) AS sent, SUM(received_count) AS received FROM emails_daily WHERE date >= date('now', '-7 days') GROUP BY date ORDER BY date DESC">This week's emails</option>
          <option value="SELECT DATE(date) AS day, direction, COUNT(*) AS count, ROUND(SUM(duration_seconds)/60.0,1) AS minutes FROM phone_calls WHERE DATE(date) >= date('now', '-7 days') GROUP BY day, direction ORDER BY day DESC">Calls by direction (7d)</option>
          <option value="SELECT strftime('%Y-%m', date) AS month, SUM(sent_count) AS sent, SUM(received_count) AS received FROM texts_daily GROUP BY month ORDER BY month DESC">Monthly text totals</option>
        </optgroup>
        <optgroup label="Screen Time">
          <option value="SELECT app_id, ROUND(SUM(usage_seconds)/3600.0, 2) AS hours FROM screen_time GROUP BY app_id ORDER BY hours DESC LIMIT 10">Top 10 apps (all time)</option>
          <option value="SELECT app_id, ROUND(SUM(usage_seconds)/3600.0, 2) AS hours FROM screen_time WHERE date >= date('now', '-7 days') GROUP BY app_id ORDER BY hours DESC LIMIT 10">Top 10 apps (7d)</option>
          <option value="SELECT date, ROUND(SUM(usage_seconds)/3600.0, 2) AS hours FROM screen_time WHERE date >= date('now', '-30 days') GROUP BY date ORDER BY date DESC">Daily screen time (30d)</option>
          <option value="SELECT DISTINCT device_model FROM screen_time WHERE device_model IS NOT NULL">Devices tracked</option>
        </optgroup>
        <optgroup label="Spending">
          <option value="SELECT * FROM bank_transactions ORDER BY date DESC LIMIT 20">Recent transactions</option>
          <option value="SELECT strftime('%Y-%m', date) AS month, ROUND(SUM(amount), 2) AS total FROM bank_transactions GROUP BY month ORDER BY month DESC">Monthly net spending</option>
          <option value="SELECT strftime('%Y-%m', date) AS month, ROUND(SUM(CASE WHEN amount >= 0 THEN amount ELSE 0 END), 2) AS income, ROUND(SUM(CASE WHEN amount < 0 THEN amount ELSE 0 END), 2) AS expenses FROM bank_transactions GROUP BY month ORDER BY month DESC">Monthly income vs expenses</option>
          <option value="SELECT description, COUNT(*) AS times, ROUND(AVG(amount), 2) AS avg_amount FROM bank_transactions GROUP BY description ORDER BY times DESC LIMIT 15">Most frequent transactions</option>
          <option value="SELECT date, description, amount FROM bank_transactions WHERE amount > 0 ORDER BY amount DESC LIMIT 20">Largest deposits</option>
          <option value="SELECT date, description, amount FROM bank_transactions WHERE amount < 0 ORDER BY amount ASC LIMIT 20">Largest expenses</option>
        </optgroup>
        <optgroup label="Health">
          <option value="SELECT date, value, unit FROM health_metrics WHERE metric_name = 'step_count' AND date >= date('now', '-30 days') ORDER BY date DESC">Steps (30d)</option>
          <option value="SELECT metric_name, COUNT(*) AS days, ROUND(AVG(value), 2) AS avg_val, unit FROM health_metrics GROUP BY metric_name">Health metrics overview</option>
        </optgroup>
        <optgroup label="AI Conversations">
          <option value="SELECT platform, COUNT(*) AS conversations, SUM(message_count) AS total_messages, ROUND(AVG(message_count), 1) AS avg_messages FROM ai_conversations GROUP BY platform">AI usage by platform</option>
          <option value="SELECT strftime('%Y-%m', date) AS month, platform, COUNT(*) AS conversations FROM ai_conversations GROUP BY month, platform ORDER BY month DESC">Monthly AI conversations</option>
          <option value="SELECT * FROM ai_conversations ORDER BY date DESC LIMIT 20">Recent AI conversations</option>
        </optgroup>
        <optgroup label="Pipelines">
          <option value="SELECT * FROM pipeline_log ORDER BY run_at DESC LIMIT 20">Recent pipeline runs</option>
          <option value="SELECT pipeline, COUNT(*) AS runs, SUM(CASE WHEN status='error' THEN 1 ELSE 0 END) AS errors, SUM(records_synced) AS total_records FROM pipeline_log GROUP BY pipeline">Pipeline stats</option>
        </optgroup>
      </select>
    </div>
    <textarea id="sql-input" rows="3" class="w-full border rounded p-2 sm:p-3 text-xs sm:text-sm bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-300" placeholder="SELECT * FROM daily_summary LIMIT 10"></textarea>
    <div class="flex justify-between items-center mt-2">
      <span id="sql-status" class="text-sm text-gray-500"></span>
      <button onclick="runQuery()" class="bg-blue-600 text-white px-4 py-1.5 rounded text-sm font-medium">Run Query</button>
    </div>
  </div>
  <div id="sql-results" class="chart-card overflow-x-auto hidden"></div>
</section>

</main>

<script>
// ---------------------------------------------------------------------------
// Colors per spec
// ---------------------------------------------------------------------------
const C = {
  textsSent:'#378ADD', textsRecv:'#B5D4F4',
  emailsSent:'#534AB7', emailsRecv:'#CECBF6',
  calls:'#1D9E75', talkMin:'#9FE1CB',
  steps:'#1D9E75', distance:'#378ADD',
  screen:'#534AB7',
  spendDay:'#D85A30', spendRun:'rgba(216,90,48,0.2)',
  aiClaude:'#378ADD', aiChatgpt:'#EF9F27',
};

// ---------------------------------------------------------------------------
// Global state
// ---------------------------------------------------------------------------
let globalDays = 7;
const chartInstances = {};
const chartRanges = {};  // per-chart override
const tabs = ['overview','spending','pipelines','sql'];

function destroyChart(id) {
  if (chartInstances[id]) { chartInstances[id].destroy(); delete chartInstances[id]; }
}

function getDays(chartId) {
  return chartRanges[chartId] || globalDays;
}

// ---------------------------------------------------------------------------
// Tab navigation
// ---------------------------------------------------------------------------
function showTab(name) {
  tabs.forEach(t => {
    document.getElementById('page-'+t).classList.toggle('hidden', t !== name);
    document.getElementById('tab-'+t).classList.toggle('tab-active', t === name);
  });
  if (name === 'overview') loadOverview();
  if (name === 'spending') loadSpending();
  if (name === 'pipelines') loadPipelines();
}

// ---------------------------------------------------------------------------
// Global range
// ---------------------------------------------------------------------------
function setGlobalDays(n) {
  globalDays = n;
  document.querySelectorAll('#global-range .range-btn').forEach(b => {
    b.classList.toggle('active', parseInt(b.dataset.days) === n);
  });
  // Reset per-chart overrides
  Object.keys(chartRanges).forEach(k => delete chartRanges[k]);
  loadOverview();
}

// Per-chart range
function setChartDays(chartId, n) {
  chartRanges[chartId] = n;
  // Update buttons for that chart
  document.querySelectorAll(`[data-chart="${chartId}"] .range-btn`).forEach(b => {
    b.classList.toggle('active', parseInt(b.dataset.days) === n);
  });
  loadSingleChart(chartId);
}

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------
function timeSince(dt) {
  if (!dt) return 'never';
  const diff = (Date.now() - new Date(dt + 'Z').getTime()) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return Math.floor(diff/60) + 'm ago';
  if (diff < 86400) return Math.floor(diff/3600) + 'h ago';
  return Math.floor(diff/86400) + 'd ago';
}

function mean(arr) { return arr.length ? arr.reduce((a,b)=>a+b,0)/arr.length : 0; }
function stddev(arr) {
  if (arr.length < 2) return 0;
  const m = mean(arr);
  return Math.sqrt(arr.reduce((s,v)=>s+(v-m)**2,0)/(arr.length-1));
}
function statLine(metrics) {
  // metrics: [{label, values, fmt}] — renders "Label: M=x SD=x" for each
  return '<div class="flex flex-wrap gap-x-5 gap-y-1 mb-2 text-xs text-gray-500">' +
    metrics.filter(m => m.values.length > 0).map(m => {
      const f = m.fmt || (v => v.toFixed(1));
      return `<span><span class="font-semibold text-gray-600">${m.label}:</span> M=${f(mean(m.values))} &nbsp;SD=${f(stddev(m.values))}</span>`;
    }).join('') + '</div>';
}
function setStats(chartId, html) {
  const el = document.querySelector(`[data-chart="${chartId}"] .chart-stats`);
  if (el) el.innerHTML = html;
}

function fmtNum(v, decimals=0) {
  if (v == null) return '0';
  return typeof v === 'number' ? (decimals ? Math.abs(v).toFixed(decimals) : Math.round(Math.abs(v)).toLocaleString()) : v;
}

function rangeButtons(chartId) {
  const cur = getDays(chartId);
  return [1,7,30,90].map(d => {
    const label = d === 1 ? '24h' : d + 'd';
    const cls = d === cur ? 'range-btn active' : 'range-btn';
    return `<button class="${cls}" data-days="${d}" onclick="setChartDays('${chartId}',${d})">${label}</button>`;
  }).join('');
}

// ---------------------------------------------------------------------------
// OVERVIEW — Summary Cards
// ---------------------------------------------------------------------------
async function loadOverview() {
  const res = await fetch(`/api/summary?days=${globalDays}`);
  const d = await res.json();
  const t = d.today || {};
  const y = d.yesterday || {};
  const a = d.avg_7d || {};
  const s = d.spending || {};
  const ai = d.ai || {};
  const p = d.period || {};
  const pp = d.prior_period || {};
  const isOneDay = globalDays === 1;
  const rangeLabel = isOneDay ? '24h' : globalDays + 'd';

  function card(label, value, subtitle, delta, deltaLabel, favorable) {
    const deltaNum = parseFloat(delta) || 0;
    const arrow = deltaNum > 0 ? '\u25B2' : deltaNum < 0 ? '\u25BC' : '';
    let deltaColor = 'text-gray-400';
    if (deltaNum !== 0) {
      deltaColor = (favorable === 'neg') ?
        (deltaNum < 0 ? 'text-green-600' : 'text-red-500') :
        (deltaNum > 0 ? 'text-green-600' : 'text-red-500');
    }
    return `<div class="stat-card bg-white rounded-xl p-3 sm:p-4 border border-gray-200">
      <div class="text-gray-500 uppercase tracking-wider" style="font-size:10px">${label}</div>
      <div class="font-bold mt-1 text-lg sm:text-xl">${value}</div>
      ${subtitle ? `<div class="text-xs text-gray-400 mt-0.5 truncate">${subtitle}</div>` : ''}
      <div class="text-xs mt-1 ${deltaColor}">${arrow} ${fmtNum(Math.abs(deltaNum), 1)} ${deltaLabel}</div>
    </div>`;
  }

  // For 24h: show today's values vs yesterday
  // For 7d/30d/90d: show period totals vs prior period totals
  let tSent, tRecv, eSent, eRecv, callsVal, talkMin, stepsVal, dist, screenH;
  let dTexts, dTextsR, dEmails, dEmailsR, dCalls, dSteps, dDist, dScreen;
  let deltaLabel;
  let spendVal, spendDelta, spendDeltaLabel, spendSub;
  let txnCount;
  let aiVal, aiDelta, aiDeltaLabel, aiSub;

  if (isOneDay) {
    tSent = t.texts_sent ?? 0;      tRecv = t.texts_received ?? 0;
    eSent = t.emails_sent ?? 0;      eRecv = t.emails_received ?? 0;
    callsVal = t.phone_calls ?? 0;   talkMin = t.talk_minutes ?? 0;
    stepsVal = t.steps ?? 0;         dist = t.distance_km ?? 0;
    screenH = t.screen_time_hours ?? 0;
    dTexts = tSent - (y.texts_sent??0);       dTextsR = tRecv - (y.texts_received??0);
    dEmails = eSent - (y.emails_sent??0);     dEmailsR = eRecv - (y.emails_received??0);
    dCalls = callsVal - (y.phone_calls??0);   dSteps = stepsVal - (y.steps??0);
    dDist = dist - (y.distance_km??0);        dScreen = screenH - (y.screen_time_hours??0);
    deltaLabel = 'vs yesterday';

    spendVal = s.today ?? 0;
    spendDelta = spendVal - (s.yesterday??0);
    spendDeltaLabel = 'vs yesterday';
    txnCount = s.txn_count_today ?? 0;
    spendSub = txnCount + ' transactions';

    aiVal = ai.today ?? 0;
    aiDelta = aiVal - (ai.yesterday??0);
    aiDeltaLabel = 'vs yesterday';
    const aiPlatforms = ai.platforms || {};
    aiSub = Object.entries(aiPlatforms).map(([k,v]) => `${k}: ${v}`).join(', ') || '';
  } else {
    tSent = p.texts_sent ?? 0;      tRecv = p.texts_received ?? 0;
    eSent = p.emails_sent ?? 0;      eRecv = p.emails_received ?? 0;
    callsVal = p.phone_calls ?? 0;   talkMin = p.talk_minutes ?? 0;
    stepsVal = p.steps ?? 0;         dist = p.distance_km ?? 0;
    screenH = p.screen_time_hours ?? 0;
    dTexts = tSent - (pp.texts_sent??0);       dTextsR = tRecv - (pp.texts_received??0);
    dEmails = eSent - (pp.emails_sent??0);     dEmailsR = eRecv - (pp.emails_received??0);
    dCalls = callsVal - (pp.phone_calls??0);   dSteps = stepsVal - (pp.steps??0);
    dDist = dist - (pp.distance_km??0);        dScreen = screenH - (pp.screen_time_hours??0);
    deltaLabel = 'vs prior ' + rangeLabel;

    spendVal = s.period_total ?? 0;
    spendDelta = spendVal - (s.prior_period_total??0);
    spendDeltaLabel = 'vs prior ' + rangeLabel;
    txnCount = s.txn_count_period ?? 0;
    spendSub = txnCount + ' transactions';

    aiVal = ai.period ?? 0;
    aiDelta = aiVal - (ai.prior_period??0);
    aiDeltaLabel = 'vs prior ' + rangeLabel;
    const aiPlatforms = ai.platforms_period || {};
    aiSub = Object.entries(aiPlatforms).map(([k,v]) => `${k}: ${v}`).join(', ') || '';
  }

  const cards = `
    <div class="grid grid-cols-2 md:grid-cols-4 gap-2 sm:gap-4 mb-3 sm:mb-4">
      ${card('Texts Sent', fmtNum(tSent), '', dTexts, deltaLabel)}
      ${card('Texts Received', fmtNum(tRecv), '', dTextsR, deltaLabel)}
      ${card('Emails Sent', fmtNum(eSent), '', dEmails, deltaLabel)}
      ${card('Emails Received', fmtNum(eRecv), '', dEmailsR, deltaLabel)}
    </div>
    <div class="grid grid-cols-2 md:grid-cols-4 gap-2 sm:gap-4 mb-3 sm:mb-4">
      ${card('Phone Calls', fmtNum(callsVal), fmtNum(talkMin,1) + ' min talk time', dCalls, deltaLabel)}
      ${card('Steps', fmtNum(stepsVal), '', dSteps, deltaLabel)}
      ${card('Distance', fmtNum(dist,2) + ' km', '', dDist, deltaLabel)}
      ${card('Screen Time', fmtNum(screenH,1) + 'h', '', dScreen, deltaLabel, 'neg')}
    </div>
    <div class="grid grid-cols-2 md:grid-cols-3 gap-2 sm:gap-4 mb-3 sm:mb-4">
      ${card('Spending', '$' + fmtNum(Math.abs(spendVal),2), spendSub, spendDelta, spendDeltaLabel, 'neg')}
      ${card('Spending Avg/Day', '$' + fmtNum(Math.abs(s.avg_7d??0),2), rangeLabel + ' daily average', '', '')}
      ${card('AI Conversations', aiVal, aiSub, aiDelta, aiDeltaLabel)}
    </div>`;
  document.getElementById('summary-cards').innerHTML = cards;

  buildChartContainers();
  loadAllCharts();
}

// ---------------------------------------------------------------------------
// OVERVIEW — Chart containers
// ---------------------------------------------------------------------------
function buildChartContainers() {
  const el = document.getElementById('overview-charts');
  el.innerHTML = `
    <!-- Texts (full width) -->
    <div class="chart-card" data-chart="texts">
      <div class="flex items-center justify-between mb-1">
        <h3 class="font-semibold text-sm text-gray-700">Texts</h3>
        <div class="flex gap-1">${rangeButtons('texts')}</div>
      </div>
      <div class="chart-stats"></div>
      <canvas id="chart-texts"></canvas>
    </div>

    <!-- Emails + Calls (side by side) -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
      <div class="chart-card" data-chart="emails">
        <div class="flex items-center justify-between mb-1">
          <h3 class="font-semibold text-sm text-gray-700">Emails</h3>
          <div class="flex gap-1">${rangeButtons('emails')}</div>
        </div>
        <div class="chart-stats"></div>
        <canvas id="chart-emails"></canvas>
      </div>
      <div class="chart-card" data-chart="calls">
        <div class="flex items-center justify-between mb-1">
          <h3 class="font-semibold text-sm text-gray-700">Phone Calls</h3>
          <div class="flex gap-1">${rangeButtons('calls')}</div>
        </div>
        <div class="chart-stats"></div>
        <canvas id="chart-calls"></canvas>
      </div>
    </div>

    <!-- Steps + Distance (side by side) -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
      <div class="chart-card" data-chart="steps">
        <div class="flex items-center justify-between mb-1">
          <h3 class="font-semibold text-sm text-gray-700">Steps</h3>
          <div class="flex gap-1">${rangeButtons('steps')}</div>
        </div>
        <div class="chart-stats"></div>
        <canvas id="chart-steps"></canvas>
      </div>
      <div class="chart-card" data-chart="distance">
        <div class="flex items-center justify-between mb-1">
          <h3 class="font-semibold text-sm text-gray-700">Distance</h3>
          <div class="flex gap-1">${rangeButtons('distance')}</div>
        </div>
        <div class="chart-stats"></div>
        <canvas id="chart-distance"></canvas>
      </div>
    </div>

    <!-- Screen time (full width) -->
    <div class="chart-card" data-chart="screen">
      <div class="flex items-center justify-between mb-1">
        <h3 class="font-semibold text-sm text-gray-700">Screen Time</h3>
        <div class="flex gap-1">${rangeButtons('screen')}</div>
      </div>
      <div class="chart-stats"></div>
      <canvas id="chart-screen"></canvas>
    </div>

    <!-- Spending (full width) -->
    <div class="chart-card" data-chart="spend">
      <div class="flex items-center justify-between mb-1">
        <h3 class="font-semibold text-sm text-gray-700">Daily Spending</h3>
        <div class="flex gap-1">${rangeButtons('spend')}</div>
      </div>
      <div class="chart-stats"></div>
      <canvas id="chart-spend"></canvas>
    </div>

    <!-- AI (full width) -->
    <div class="chart-card" data-chart="ai">
      <div class="flex items-center justify-between mb-1">
        <h3 class="font-semibold text-sm text-gray-700">AI Conversations</h3>
        <div class="flex gap-1">${rangeButtons('ai')}</div>
      </div>
      <div class="chart-stats"></div>
      <canvas id="chart-ai"></canvas>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// OVERVIEW — Chart loading
// ---------------------------------------------------------------------------
const chartLoaders = {
  async texts() {
    const days = getDays('texts');
    const data = await fetch(`/api/trends?metric=texts&days=${days}`).then(r=>r.json());
    setStats('texts', statLine([
      {label:'Sent', values:data.map(r=>r.sent)},
      {label:'Received', values:data.map(r=>r.received)},
    ]));
    destroyChart('chart-texts');
    chartInstances['chart-texts'] = new Chart(document.getElementById('chart-texts'), {
      type:'bar', data:{
        labels:data.map(r=>r.date),
        datasets:[
          {label:'Sent', data:data.map(r=>r.sent), backgroundColor:C.textsSent},
          {label:'Received', data:data.map(r=>r.received), backgroundColor:C.textsRecv},
        ]
      }, options:{responsive:true, plugins:{legend:{labels:{usePointStyle:true,pointStyle:'circle'}}}, scales:{x:{stacked:true, ticks:{maxTicksLimit:15}}, y:{stacked:true, beginAtZero:true}}, interaction:{mode:'index',intersect:false}}
    });
  },
  async emails() {
    const days = getDays('emails');
    const data = await fetch(`/api/trends?metric=emails&days=${days}`).then(r=>r.json());
    setStats('emails', statLine([
      {label:'Sent', values:data.map(r=>r.sent)},
      {label:'Received', values:data.map(r=>r.received)},
    ]));
    destroyChart('chart-emails');
    chartInstances['chart-emails'] = new Chart(document.getElementById('chart-emails'), {
      type:'bar', data:{
        labels:data.map(r=>r.date),
        datasets:[
          {label:'Sent', data:data.map(r=>r.sent), backgroundColor:C.emailsSent},
          {label:'Received', data:data.map(r=>r.received), backgroundColor:C.emailsRecv},
        ]
      }, options:{responsive:true, plugins:{legend:{labels:{usePointStyle:true,pointStyle:'circle'}}}, scales:{x:{ticks:{maxTicksLimit:12}}, y:{beginAtZero:true}}, interaction:{mode:'index',intersect:false}}
    });
  },
  async calls() {
    const days = getDays('calls');
    const data = await fetch(`/api/trends?metric=calls&days=${days}`).then(r=>r.json());
    setStats('calls', statLine([
      {label:'Calls', values:data.map(r=>r.calls)},
      {label:'Missed', values:data.map(r=>r.missed)},
      {label:'Talk min', values:data.map(r=>r.minutes)},
    ]));
    destroyChart('chart-calls');
    chartInstances['chart-calls'] = new Chart(document.getElementById('chart-calls'), {
      type:'bar', data:{
        labels:data.map(r=>r.date),
        datasets:[
          {label:'Calls', data:data.map(r=>r.calls), backgroundColor:C.calls, stack:'calls', yAxisID:'y'},
          {label:'Missed', data:data.map(r=>r.missed), backgroundColor:'#F87171', stack:'calls', yAxisID:'y'},
          {label:'Talk min', data:data.map(r=>r.minutes), type:'line', borderColor:C.calls, backgroundColor:'transparent', tension:0.3, pointRadius:2, yAxisID:'y1'},
        ]
      }, options:{responsive:true, plugins:{legend:{labels:{usePointStyle:true,pointStyle:'circle'}}}, scales:{x:{ticks:{maxTicksLimit:12}}, y:{stacked:true,beginAtZero:true,position:'left'}, y1:{beginAtZero:true,position:'right',grid:{drawOnChartArea:false}}}, interaction:{mode:'index',intersect:false}}
    });
  },
  async steps() {
    const days = getDays('steps');
    const data = await fetch(`/api/trends?metric=steps&days=${days}`).then(r=>r.json());
    setStats('steps', statLine([
      {label:'Steps', values:data.map(r=>r.value), fmt:v=>Math.round(v).toLocaleString()},
    ]));
    destroyChart('chart-steps');
    chartInstances['chart-steps'] = new Chart(document.getElementById('chart-steps'), {
      type:'line', data:{
        labels:data.map(r=>r.date),
        datasets:[{label:'Steps', data:data.map(r=>r.value), borderColor:C.steps, backgroundColor:C.steps+'20', fill:true, tension:0.3, pointRadius:2}]
      }, options:{responsive:true, plugins:{legend:{display:false}}, scales:{x:{ticks:{maxTicksLimit:12}}, y:{beginAtZero:true}}}
    });
  },
  async distance() {
    const days = getDays('distance');
    const data = await fetch(`/api/trends?metric=distance&days=${days}`).then(r=>r.json());
    setStats('distance', statLine([
      {label:'Distance', values:data.map(r=>r.value), fmt:v=>v.toFixed(2)+' km'},
    ]));
    destroyChart('chart-distance');
    chartInstances['chart-distance'] = new Chart(document.getElementById('chart-distance'), {
      type:'line', data:{
        labels:data.map(r=>r.date),
        datasets:[{label:'km', data:data.map(r=>r.value), borderColor:C.distance, backgroundColor:C.distance+'20', fill:true, tension:0.3, pointRadius:2}]
      }, options:{responsive:true, plugins:{legend:{display:false}}, scales:{x:{ticks:{maxTicksLimit:12}}, y:{beginAtZero:true}}}
    });
  },
  async screen() {
    const days = getDays('screen');
    const data = await fetch(`/api/trends?metric=screen_time&days=${days}`).then(r=>r.json());
    setStats('screen', statLine([
      {label:'Hours/day', values:data.map(r=>r.hours), fmt:v=>v.toFixed(1)+'h'},
    ]));
    destroyChart('chart-screen');
    chartInstances['chart-screen'] = new Chart(document.getElementById('chart-screen'), {
      type:'bar', data:{
        labels:data.map(r=>r.date),
        datasets:[{label:'Hours', data:data.map(r=>r.hours), backgroundColor:C.screen}]
      }, options:{responsive:true, plugins:{legend:{display:false}}, scales:{x:{ticks:{maxTicksLimit:15}}, y:{beginAtZero:true}}}
    });
  },
  async spend() {
    const days = getDays('spend');
    const data = await fetch(`/api/trends?metric=spending&days=${days}`).then(r=>r.json());
    setStats('spend', statLine([
      {label:'Daily', values:data.map(r=>r.total), fmt:v=>'$'+Math.abs(v).toFixed(2)},
    ]));
    destroyChart('chart-spend');
    let running = 0;
    const runTotals = data.map(r => { running += r.total; return running; });
    chartInstances['chart-spend'] = new Chart(document.getElementById('chart-spend'), {
      type:'bar', data:{
        labels:data.map(r=>r.date),
        datasets:[
          {label:'Daily', data:data.map(r=>r.total), backgroundColor:C.spendDay, order:2},
          {label:'Running Total', data:runTotals, type:'line', borderColor:C.spendDay, backgroundColor:C.spendRun, borderDash:[5,3], fill:true, tension:0.3, pointRadius:0, order:1},
        ]
      }, options:{responsive:true, plugins:{legend:{labels:{usePointStyle:true,pointStyle:'circle'}}}, scales:{x:{ticks:{maxTicksLimit:15}}, y:{ticks:{callback:v=>'$'+v}}}, interaction:{mode:'index',intersect:false}}
    });
  },
  async ai() {
    const days = getDays('ai');
    const data = await fetch(`/api/trends?metric=ai&days=${days}`).then(r=>r.json());
    // Pivot: group by date, split by platform
    const dates = [...new Set(data.map(r=>r.date))].sort();
    const platforms = [...new Set(data.map(r=>r.platform))];
    const byDatePlatform = {};
    data.forEach(r => { byDatePlatform[r.date+'|'+r.platform] = r.count; });

    const colorMap = {claude:C.aiClaude, chatgpt:C.aiChatgpt};
    // Only show platforms with data (dynamic legend)
    const datasets = platforms.map(p => ({
      label: p.charAt(0).toUpperCase()+p.slice(1),
      data: dates.map(d => byDatePlatform[d+'|'+p] || 0),
      backgroundColor: colorMap[p] || '#999',
    }));

    // Stats per platform
    const aiStats = platforms.map(p => ({
      label: p.charAt(0).toUpperCase()+p.slice(1),
      values: dates.map(d => byDatePlatform[d+'|'+p] || 0),
    }));
    setStats('ai', statLine(aiStats));

    destroyChart('chart-ai');
    chartInstances['chart-ai'] = new Chart(document.getElementById('chart-ai'), {
      type:'bar', data:{ labels:dates, datasets },
      options:{responsive:true, plugins:{legend:{labels:{usePointStyle:true,pointStyle:'circle'}}}, scales:{x:{stacked:true, ticks:{display: days <= 14, maxTicksLimit:14}}, y:{stacked:true, beginAtZero:true}}, interaction:{mode:'index',intersect:false}}
    });
  },
};

function loadAllCharts() {
  Object.values(chartLoaders).forEach(fn => fn());
}

function loadSingleChart(chartId) {
  if (chartLoaders[chartId]) chartLoaders[chartId]();
}

// ---------------------------------------------------------------------------
// SPENDING
// ---------------------------------------------------------------------------
async function loadSpending() {
  const start = document.getElementById('spend-start').value || '';
  const end = document.getElementById('spend-end').value || '';
  const search = document.getElementById('spend-search').value || '';
  const params = new URLSearchParams({start, end, search}).toString();
  const res = await fetch('/api/spending?' + params);
  const d = await res.json();

  destroyChart('chart-by-account');
  chartInstances['chart-by-account'] = new Chart(document.getElementById('chart-by-account'), {
    type:'doughnut', data:{
      labels:d.by_account.map(r=>r.account_name||'Unknown'),
      datasets:[{data:d.by_account.map(r=>Math.abs(r.total)), backgroundColor:[C.textsSent,C.spendDay,C.steps,C.aiChatgpt,C.screen]}]
    }, options:{responsive:true}
  });

  let mt = '<table class="w-full text-sm"><thead><tr class="border-b"><th class="text-left py-2 text-gray-500">Month</th><th class="text-right py-2 text-gray-500">Income</th><th class="text-right py-2 text-gray-500">Expenses</th><th class="text-right py-2 text-gray-500">Net</th><th class="text-right py-2 text-gray-500">Txns</th></tr></thead><tbody>';
  d.monthly.forEach(r => {
    const netColor = r.net >= 0 ? 'text-green-600' : 'text-red-600';
    mt += `<tr class="border-b hover:bg-gray-50"><td class="py-2">${r.month}</td><td class="text-right py-2 text-green-600">$${r.income.toFixed(2)}</td><td class="text-right py-2 text-red-600">$${Math.abs(r.expenses).toFixed(2)}</td><td class="text-right py-2 ${netColor}">$${Math.abs(r.net).toFixed(2)}</td><td class="text-right py-2">${r.count}</td></tr>`;
  });
  mt += '</tbody></table>';
  document.getElementById('monthly-table').innerHTML = mt;

  let tt = '<table class="w-full text-sm"><thead><tr class="border-b text-gray-500"><th class="text-left py-2">Date</th><th class="text-left py-2">Description</th><th class="text-right py-2">Amount</th></tr></thead><tbody>';
  d.transactions.slice(0,200).forEach(r => {
    const color = r.amount >= 0 ? 'text-green-600' : 'text-red-600';
    tt += `<tr class="border-b hover:bg-gray-50"><td class="py-1.5 whitespace-nowrap">${r.date}</td><td class="py-1.5 truncate max-w-xs">${r.description}</td><td class="text-right py-1.5 ${color}">$${Math.abs(r.amount).toFixed(2)}</td></tr>`;
  });
  tt += '</tbody></table>';
  if (d.transactions.length > 200) tt += `<p class="text-xs text-gray-400 mt-2">Showing 200 of ${d.transactions.length}</p>`;
  document.getElementById('txn-table').innerHTML = tt;
}

// ---------------------------------------------------------------------------
// PIPELINES
// ---------------------------------------------------------------------------
async function loadPipelines() {
  const data = await fetch('/api/pipelines').then(r=>r.json());
  let html = '<table class="w-full text-sm"><thead><tr class="border-b text-gray-500"><th class="text-left p-3">Pipeline</th><th class="p-3">Status</th><th class="text-right p-3">Records</th><th class="text-left p-3">Last Run</th><th class="text-left p-3">Error</th></tr></thead><tbody>';
  data.forEach(r => {
    const hoursAgo = r.run_at ? (Date.now() - new Date(r.run_at+'Z').getTime())/3600000 : 999;
    let dot = 'dot-green';
    if (r.status === 'error') dot = 'dot-red';
    else if (hoursAgo > 24) dot = 'dot-yellow';
    html += `<tr class="border-b hover:bg-gray-50">
      <td class="p-3 font-medium">${r.pipeline}</td>
      <td class="p-3 text-center"><span class="health-dot ${dot}"></span> ${r.status}</td>
      <td class="p-3 text-right">${r.records_synced}</td>
      <td class="p-3 text-gray-500">${r.run_at || 'never'}</td>
      <td class="p-3 text-red-500 text-xs max-w-xs truncate">${r.error_message || ''}</td>
    </tr>`;
  });
  html += '</tbody></table>';
  document.getElementById('pipeline-table').innerHTML = html;
}

// ---------------------------------------------------------------------------
// SQL CONSOLE
// ---------------------------------------------------------------------------
function loadExample() {
  const sel = document.getElementById('sql-examples');
  if (sel.value) document.getElementById('sql-input').value = sel.value;
  sel.selectedIndex = 0;
}

async function runQuery() {
  const sql = document.getElementById('sql-input').value.trim();
  if (!sql) return;
  document.getElementById('sql-status').textContent = 'Running...';
  const res = await fetch('/api/query', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({sql})});
  const d = await res.json();
  if (d.error) {
    document.getElementById('sql-status').textContent = 'Error';
    const el = document.getElementById('sql-results');
    el.classList.remove('hidden');
    el.innerHTML = `<div class="p-4 text-red-600 text-sm">${d.error}</div>`;
    return;
  }
  document.getElementById('sql-status').textContent = `${d.rows.length} row${d.rows.length!==1?'s':''}`;
  let html = '<div class="overflow-x-auto max-h-96 overflow-y-auto"><table class="w-full text-sm"><thead class="sticky top-0 bg-white"><tr class="border-b">';
  d.columns.forEach(c => html += `<th class="text-left p-2 font-medium text-gray-600">${c}</th>`);
  html += '</tr></thead><tbody>';
  d.rows.forEach(r => {
    html += '<tr class="border-b hover:bg-gray-50">';
    r.forEach(v => html += `<td class="p-2 whitespace-nowrap">${v ?? '<span class=text-gray-300>NULL</span>'}</td>`);
    html += '</tr>';
  });
  html += '</tbody></table></div>';
  const el = document.getElementById('sql-results');
  el.classList.remove('hidden');
  el.innerHTML = html;
  // Save to history
  const hist = JSON.parse(localStorage.getItem('sql_history') || '[]');
  if (hist[0] !== sql) { hist.unshift(sql); if (hist.length > 10) hist.pop(); localStorage.setItem('sql_history', JSON.stringify(hist)); }
}

document.addEventListener('keydown', e => {
  if ((e.metaKey||e.ctrlKey) && e.key === 'Enter' && !document.getElementById('page-sql').classList.contains('hidden')) runQuery();
});

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
(function init() {
  const today = new Date().toISOString().slice(0,10);
  const monthAgo = new Date(Date.now()-30*86400000).toISOString().slice(0,10);
  document.getElementById('spend-start').value = monthAgo;
  document.getElementById('spend-end').value = today;
  loadOverview();
})();
</script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(TEMPLATE)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=DASHBOARD_PORT)
