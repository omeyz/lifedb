#!/usr/bin/env python3
"""Generate a PDF reference guide for Omar's Life Database commands."""

from pathlib import Path

from fpdf import FPDF

FONT_DIR = "/System/Library/Fonts/Supplemental/"

class PDF(FPDF):
    def setup_fonts(self):
        self.add_font("Arial", "", FONT_DIR + "Arial.ttf")
        self.add_font("Arial", "B", FONT_DIR + "Arial Bold.ttf")
        self.add_font("Arial", "I", FONT_DIR + "Arial Italic.ttf")
        self.add_font("Arial", "BI", FONT_DIR + "Arial Bold Italic.ttf")
        self.add_font("CourierNew", "", FONT_DIR + "Courier New.ttf")
        self.add_font("CourierNew", "B", FONT_DIR + "Courier New Bold.ttf")

    def header(self):
        if self.page_no() > 1:
            self.set_font("Arial", "I", 8)
            self.set_text_color(120, 120, 120)
            self.cell(0, 8, "Omar's SQL - Command Reference", align="R")
            self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def section_title(self, title):
        self.set_font("Arial", "B", 16)
        self.set_text_color(30, 30, 30)
        self.ln(4)
        self.cell(0, 10, title)
        self.ln(8)
        # Underline
        self.set_draw_color(55, 138, 221)
        self.set_line_width(0.6)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(6)

    def sub_title(self, title):
        self.set_font("Arial", "B", 12)
        self.set_text_color(55, 100, 160)
        self.ln(2)
        self.cell(0, 8, title)
        self.ln(8)

    def body_text(self, text):
        self.set_font("Arial", "", 10)
        self.set_text_color(50, 50, 50)
        self.multi_cell(0, 5.5, text)
        self.ln(2)

    def code_block(self, code):
        self.set_font("CourierNew", "", 9)
        self.set_fill_color(243, 244, 246)
        self.set_text_color(40, 40, 40)
        x = self.get_x()
        w = self.w - self.l_margin - self.r_margin
        lines = code.strip().split("\n")
        block_h = len(lines) * 5.5 + 6
        # Check if we need a page break
        if self.get_y() + block_h > self.h - 20:
            self.add_page()
        y_start = self.get_y()
        self.rect(x, y_start, w, block_h, "F")
        self.set_xy(x + 4, y_start + 3)
        for i, line in enumerate(lines):
            self.cell(0, 5.5, line)
            if i < len(lines) - 1:
                self.ln(5.5)
                self.set_x(x + 4)
        self.ln(5.5 + 3)
        self.set_font("Arial", "", 10)

    def bullet(self, text, bold_prefix=""):
        self.set_font("Arial", "", 10)
        self.set_text_color(50, 50, 50)
        x = self.l_margin
        self.set_x(x + 4)
        self.cell(4, 5.5, chr(8226))
        if bold_prefix:
            self.set_font("Arial", "B", 10)
            self.cell(self.get_string_width(bold_prefix) + 1, 5.5, bold_prefix)
            self.set_font("Arial", "", 10)
        self.multi_cell(0, 5.5, text)
        self.ln(1)

    def table_row(self, cols, widths, bold=False, fill=False):
        self.set_font("Arial", "B" if bold else "", 9)
        if fill:
            self.set_fill_color(235, 240, 250)
        self.set_text_color(40, 40, 40)
        h = 7
        for i, col in enumerate(cols):
            self.cell(widths[i], h, str(col), border=1, fill=fill)
        self.ln(h)


def build_pdf():
    pdf = PDF()
    pdf.setup_fonts()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_left_margin(15)
    pdf.set_right_margin(15)

    # ---- Cover Page ----
    pdf.add_page()
    pdf.ln(50)
    pdf.set_font("Helvetica", "B", 32)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 15, "Omar's SQL", align="C")
    pdf.ln(16)
    pdf.set_font("Helvetica", "", 16)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 10, "Command Reference Guide", align="C")
    pdf.ln(30)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 7, "Personal Life Database", align="C")
    pdf.ln(7)
    pdf.cell(0, 7, "Dashboard  |  Data Pipelines  |  Launchd Services", align="C")
    pdf.ln(7)
    pdf.cell(0, 7, "http://localhost:8080", align="C")

    # ---- Quick Start ----
    pdf.add_page()
    pdf.section_title("Quick Start")
    pdf.body_text("Initial setup commands to get everything running:")
    pdf.code_block(
        "# 1. Install dependencies\n"
        "python3 -m pip install -r requirements.txt\n"
        "\n"
        "# 2. Initialize the database\n"
        "python3 scripts/init_db.py\n"
        "\n"
        "# 3. Set up Gmail authentication\n"
        "python3 scripts/sync_gmail.py --auth personal\n"
        "python3 scripts/sync_gmail.py --auth work\n"
        "\n"
        "# 4. Set up SimpleFIN bank access\n"
        "python3 scripts/sync_bank.py --claim\n"
        "\n"
        "# 5. Install & load launchd services\n"
        "cp launchd/*.plist ~/Library/LaunchAgents/\n"
        "launchctl load ~/Library/LaunchAgents/com.omar.lifedb.*.plist\n"
        "\n"
        "# 6. Verify services\n"
        "curl http://localhost:8765/health\n"
        "curl http://localhost:8080/api/summary"
    )

    # ---- Data Pipelines ----
    pdf.add_page()
    pdf.section_title("Data Pipelines")
    pdf.body_text("All pipelines run automatically via launchd at 23:55 daily (except where noted). "
                  "Each sends a Discord notification on success or failure.")

    # sync_bank
    pdf.sub_title("1. Bank Transactions (sync_bank.py)")
    pdf.body_text("Fetches last 30 days of transactions from SimpleFIN API.")
    pdf.code_block(
        "# Run manually\n"
        "python3 scripts/sync_bank.py\n"
        "\n"
        "# First-time setup: claim access token\n"
        "python3 scripts/sync_bank.py --claim"
    )

    # sync_gmail
    pdf.sub_title("2. Email Counts (sync_gmail.py)")
    pdf.body_text("Counts sent/received emails per day for personal and work Gmail accounts.")
    pdf.code_block(
        "# Run manually\n"
        "python3 scripts/sync_gmail.py\n"
        "\n"
        "# Authenticate (interactive OAuth)\n"
        "python3 scripts/sync_gmail.py --auth personal\n"
        "python3 scripts/sync_gmail.py --auth work\n"
        "\n"
        "# Backfill historical data\n"
        "python3 scripts/sync_gmail.py --backfill 365"
    )

    # sync_screen_time
    pdf.sub_title("3. Screen Time (sync_screen_time.py)")
    pdf.body_text("Reads macOS knowledgeC.db for per-app screen time data.")
    pdf.code_block("python3 scripts/sync_screen_time.py")

    # sync_texts
    pdf.sub_title("4. Text Messages (sync_texts.py)")
    pdf.body_text("Counts sent/received iMessages from macOS chat.db.")
    pdf.code_block("python3 scripts/sync_texts.py")

    # sync_calls
    pdf.sub_title("5. Phone Calls (sync_calls.py)")
    pdf.body_text("Syncs call history with direction, duration, and type (regular/FaceTime).")
    pdf.code_block("python3 scripts/sync_calls.py")

    # health_receiver
    pdf.sub_title("6. Health Metrics (health_receiver.py)")
    pdf.body_text("Always-on Flask server on port 8765. Receives POST data from the iOS "
                  "\"Health Auto Export\" app. Configure the app to POST to http://<mac-ip>:8765/health.")
    pdf.code_block(
        "# Run manually\n"
        "python3 scripts/health_receiver.py\n"
        "\n"
        "# Test endpoint\n"
        "curl http://localhost:8765/health"
    )

    # parse_ai_exports
    pdf.sub_title("7. AI Conversations (parse_ai_exports.py)")
    pdf.body_text("Parses Claude (.dms) and ChatGPT (.zip) exports. "
                  "Drop export files into the exports/ folder, then run:")
    pdf.code_block("python3 scripts/parse_ai_exports.py")

    # import_bank_csv
    pdf.sub_title("8. CSV Bank Import (import_bank_csv.py)")
    pdf.body_text("Imports bank CSV exports manually.")
    pdf.code_block(
        "# Preview (dry run)\n"
        "python3 scripts/import_bank_csv.py file.csv --account \"Checking\" --dry-run\n"
        "\n"
        "# Import for real\n"
        "python3 scripts/import_bank_csv.py file.csv --account \"Checking\""
    )

    # monthly_reminder
    pdf.sub_title("9. Monthly Reminder (monthly_reminder.py)")
    pdf.body_text("Sends a Discord reminder on the 1st of each month to export AI data.")
    pdf.code_block("python3 scripts/monthly_reminder.py")

    # ---- Launchd Services ----
    pdf.add_page()
    pdf.section_title("Launchd Service Management")

    pdf.sub_title("Installed Services")
    widths = [55, 28, 40, 57]
    pdf.table_row(["Service", "Type", "Schedule", "Label Suffix"], widths, bold=True, fill=True)
    services = [
        ("Dashboard", "Always-on", "-", "dashboard"),
        ("Health Receiver", "Always-on", "-", "health-receiver"),
        ("Sync Bank", "Scheduled", "Daily 23:55", "sync-bank"),
        ("Sync Gmail", "Scheduled", "Daily 23:55", "sync-gmail"),
        ("Sync Screen Time", "Scheduled", "Daily 23:55", "sync-screen-time"),
        ("Sync Texts", "Scheduled", "Daily 23:55", "sync-texts"),
        ("Sync Calls", "Scheduled", "Daily 23:55", "sync-calls"),
        ("Monthly Reminder", "Scheduled", "1st @ 10:00", "monthly-reminder"),
        ("Open Dashboard", "Startup", "On login", "open-dashboard"),
    ]
    for s in services:
        pdf.table_row(s, widths)

    pdf.ln(4)
    pdf.sub_title("Common Commands")
    pdf.body_text("Replace SERVICENAME with the label suffix from the table above.")
    pdf.code_block(
        "# Start/enable a service\n"
        "launchctl load ~/Library/LaunchAgents/com.omar.lifedb.SERVICENAME.plist\n"
        "\n"
        "# Stop/disable a service\n"
        "launchctl unload ~/Library/LaunchAgents/com.omar.lifedb.SERVICENAME.plist\n"
        "\n"
        "# Restart a service\n"
        "launchctl stop com.omar.lifedb.SERVICENAME\n"
        "launchctl start com.omar.lifedb.SERVICENAME\n"
        "\n"
        "# Check which services are loaded\n"
        "launchctl list | grep com.omar.lifedb\n"
        "\n"
        "# Force-run a scheduled job now\n"
        "launchctl start com.omar.lifedb.SERVICENAME\n"
        "\n"
        "# View logs\n"
        "tail -f logs/SERVICENAME.log\n"
        "tail -f logs/SERVICENAME_error.log"
    )

    # ---- Dashboard ----
    pdf.add_page()
    pdf.section_title("Dashboard")
    pdf.body_text("Web interface at http://localhost:8080 with four tabs:")
    pdf.bullet("Overview — Summary cards and charts for all metrics", "Overview: ")
    pdf.bullet("Spending — Transaction list, account breakdown, monthly totals", "Spending: ")
    pdf.bullet("Pipelines — Status of all data sync jobs", "Pipelines: ")
    pdf.bullet("SQL Console — Write and run custom read-only queries", "SQL Console: ")

    pdf.sub_title("API Endpoints")

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(0, 6, "GET /api/summary")
    pdf.ln(6)
    pdf.body_text("Aggregated metrics for summary cards.")
    pdf.code_block(
        "# Parameters: date (YYYY-MM-DD), days (int)\n"
        "curl \"http://localhost:8080/api/summary?days=30\""
    )

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "GET /api/trends")
    pdf.ln(6)
    pdf.body_text("Time-series data for charts.")
    pdf.code_block(
        "# Parameters: metric, days (int), end (YYYY-MM-DD)\n"
        "# Metrics: texts, emails, calls, steps, distance,\n"
        "#          screen_time, screen_time_apps, spending,\n"
        "#          spending_count, ai\n"
        "curl \"http://localhost:8080/api/trends?metric=steps&days=30\""
    )

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "GET /api/spending")
    pdf.ln(6)
    pdf.body_text("Detailed spending data with transaction list.")
    pdf.code_block(
        "# Parameters: start, end (YYYY-MM-DD), search (text)\n"
        "curl \"http://localhost:8080/api/spending?start=2026-03-01&end=2026-03-23\""
    )

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "GET /api/pipelines")
    pdf.ln(6)
    pdf.body_text("Latest run status for all pipelines.")
    pdf.code_block("curl http://localhost:8080/api/pipelines")

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "POST /api/query")
    pdf.ln(6)
    pdf.body_text("Execute read-only SQL queries (blocks INSERT/UPDATE/DELETE/DROP).")
    pdf.code_block(
        "curl -X POST http://localhost:8080/api/query \\\n"
        "  -H \"Content-Type: application/json\" \\\n"
        "  -d '{\"sql\": \"SELECT * FROM daily_summary LIMIT 5\"}'"
    )

    # ---- Database Schema ----
    pdf.add_page()
    pdf.section_title("Database Tables")

    tables = [
        ("bank_transactions", "Spending data from SimpleFIN",
         "id, account_name, description, amount, currency, date, category, pending"),
        ("health_metrics", "Fitness data from Apple Health",
         "metric_name, value, unit, date, source"),
        ("screen_time", "App usage from macOS",
         "app_id, usage_seconds, device_model, date"),
        ("texts_daily", "iMessage daily counts",
         "date, sent_count, received_count"),
        ("emails_daily", "Gmail daily counts",
         "date, account, sent_count, received_count"),
        ("phone_calls", "Call history",
         "date, direction, duration_seconds, call_type, answered"),
        ("ai_conversations", "AI conversation exports",
         "platform, conversation_id, title, date, message_count"),
        ("pipeline_log", "Sync run history",
         "pipeline, status, records_synced, error_message, run_at"),
        ("daily_summary (view)", "Aggregated daily metrics",
         "date, texts_sent/received, emails_sent/received, phone_calls, talk_minutes, steps, distance_km, screen_time_hours"),
    ]

    for name, desc, cols in tables:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(55, 100, 160)
        pdf.cell(0, 7, name)
        pdf.ln(7)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 5.5, desc)
        pdf.ln(6)
        pdf.set_font("Courier", "", 8.5)
        pdf.set_text_color(100, 100, 100)
        pdf.multi_cell(0, 5, cols)
        pdf.ln(4)

    # ---- Example SQL Queries ----
    pdf.add_page()
    pdf.section_title("Example SQL Queries")

    pdf.sub_title("Daily Summary")
    pdf.code_block("SELECT * FROM daily_summary\nWHERE date >= date('now', '-7 days')\nORDER BY date DESC;")

    pdf.sub_title("Top Apps by Screen Time (Last 7 Days)")
    pdf.code_block(
        "SELECT app_id, ROUND(SUM(usage_seconds)/3600.0, 2) AS hours\n"
        "FROM screen_time\n"
        "WHERE date >= date('now', '-7 days')\n"
        "GROUP BY app_id ORDER BY hours DESC LIMIT 10;"
    )

    pdf.sub_title("Monthly Spending Breakdown")
    pdf.code_block(
        "SELECT strftime('%Y-%m', date) AS month,\n"
        "  ROUND(SUM(CASE WHEN amount >= 0 THEN amount ELSE 0 END), 2) AS income,\n"
        "  ROUND(SUM(CASE WHEN amount < 0 THEN amount ELSE 0 END), 2) AS expenses\n"
        "FROM bank_transactions\n"
        "GROUP BY month ORDER BY month DESC;"
    )

    pdf.sub_title("AI Usage by Platform")
    pdf.code_block(
        "SELECT platform, COUNT(*) AS conversations,\n"
        "  SUM(message_count) AS total_messages,\n"
        "  ROUND(AVG(message_count), 1) AS avg_messages\n"
        "FROM ai_conversations GROUP BY platform;"
    )

    pdf.sub_title("Most Frequent Transactions")
    pdf.code_block(
        "SELECT description, COUNT(*) AS times,\n"
        "  ROUND(AVG(amount), 2) AS avg_amount\n"
        "FROM bank_transactions\n"
        "GROUP BY description ORDER BY times DESC LIMIT 15;"
    )

    # ---- Troubleshooting ----
    pdf.add_page()
    pdf.section_title("Troubleshooting")

    pdf.sub_title("Service not running?")
    pdf.code_block("launchctl list | grep com.omar.lifedb")

    pdf.sub_title("Check logs for errors")
    pdf.code_block("tail -20 logs/SERVICENAME_error.log")

    pdf.sub_title("Gmail token expired?")
    pdf.code_block("python3 scripts/sync_gmail.py --auth personal")

    pdf.sub_title("SimpleFIN token expired?")
    pdf.code_block("python3 scripts/sync_bank.py --claim")

    pdf.sub_title("Health receiver not accessible?")
    pdf.code_block("curl http://localhost:8765/health")

    pdf.sub_title("Re-initialize database (caution: clears all data)")
    pdf.code_block(
        "rm data/life.db\n"
        "python3 scripts/init_db.py"
    )

    # ---- File Locations ----
    pdf.section_title("Key File Locations")
    locs = [
        ("Database", "data/life.db"),
        ("Configuration", "config/settings.py"),
        ("Environment vars", ".env"),
        ("AI export drop folder", "exports/"),
        ("Service logs", "logs/"),
        ("Launchd plists", "launchd/"),
        ("Installed services", "~/Library/LaunchAgents/com.omar.lifedb.*.plist"),
    ]
    widths = [50, 130]
    pdf.table_row(["Item", "Path"], widths, bold=True, fill=True)
    for label, path in locs:
        pdf.table_row([label, path], widths)

    # ---- Output ----
    out_path = str(Path(__file__).resolve().parent.parent / "Omars_SQL_Command_Reference.pdf")
    pdf.output(out_path)
    return out_path


if __name__ == "__main__":
    path = build_pdf()
    print(f"PDF generated: {path}")
