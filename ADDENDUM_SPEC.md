# omars-sql-database — Spec Addendum: Dashboard & Financial Import

## 1. Bank CSV Import — `scripts/import_bank_csv.py`

**Purpose:** One-time (or repeatable) backfill of historical bank transactions from a bank's CSV export, since SimpleFIN only provides ~90 days of history.

**Existing data:** A checking-account CSV (e.g. `example_checking.csv`, roughly 2,000 transactions over about 18 months) is available. This should be imported as the initial backfill.

**Usage:**
```bash
python3 scripts/import_bank_csv.py path/to/bank_export.csv
```

**Logic:**
- Read the CSV file (auto-detect encoding, handle BOM if present)
- Map the bank's columns to the `bank_transactions` schema. The CSV has **no header row**. Columns are positional:
  - Column 0: Date (`MM/DD/YYYY`) → convert to `YYYY-MM-DD` for `date`
  - Column 1: Amount (string, negative = debit, positive = credit) → parse to float for `amount`
  - Column 2: Always `*` → ignore
  - Column 3: Always empty → ignore
  - Column 4: Description → `description`
  - Generate a deterministic transaction ID by hashing `date + amount + description` (e.g. `hashlib.md5`) to prevent duplicates on re-import
  - Set `account_name` from a `--account` flag, defaulting to `"Checking"`
  - Set `pending` to 0 (historical transactions are all posted)
  - Set `currency` to `USD`
- INSERT OR IGNORE into `bank_transactions` (dedup on generated ID)
- Print count of new records imported
- Support multiple CSV files in one invocation: `python3 import_bank_csv.py *.csv`

**Column mapping note:** The CSV format may vary between checking/credit. The script should handle both gracefully, or print the detected headers and let the user confirm before importing. Include a `--dry-run` flag that shows what would be imported without writing to the database.

---

## 2. Local Web Dashboard — `scripts/dashboard.py`

**Purpose:** A locally-hosted web dashboard for viewing and querying all life database data, accessible from any device on the local network.

**Framework:** Flask (Python), consistent with the rest of the project
**Bind:** `0.0.0.0` on a configurable port (default `8080`)
**Add to settings.py:** `DASHBOARD_PORT = 8080`

### Design

Clean, modern, somewhere between minimal and polished. Light mode. Use a charting library like Chart.js (via CDN) for visualizations. No external CSS frameworks required, but Tailwind via CDN is fine if it keeps things clean. The dashboard should feel good to open but doesn't need to be flashy.

### Pages / Sections

#### Home — Daily Summary
- Today's stats at a glance: texts sent/received, emails sent/received, phone calls, talk minutes, steps, distance, screen time hours, total spending
- Comparison to yesterday and 7-day average
- A "last synced" indicator for each pipeline

#### Trends
- Time-range selector: 7 days, 30 days, 90 days, custom
- Line/bar charts for:
  - Communication: texts + emails + calls over time (stacked or overlaid)
  - Activity: steps and distance over time
  - Screen time: total hours per day, with top apps breakdown
  - Spending: daily/weekly spend, with running total
- All charts should be interactive (hover for values)

#### Spending
- Spending breakdown by account (pie or donut chart)
- Transaction list with search/filter (date range, amount range, description search)
- Monthly totals table

#### Pipeline Health
- Table showing each pipeline: name, last run time, status (success/error), records synced, error message if any
- Pull from `pipeline_log` table (most recent entry per pipeline)
- Visual indicators: green dot for healthy, red for error, yellow if last run was >24 hours ago

#### SQL Console
- Text area for writing raw SQL queries
- Execute button
- Results displayed as a formatted table below
- Query history (last 10 queries, stored in-memory or localStorage)
- Pre-populated example queries dropdown:
  - "Today's summary" → `SELECT * FROM daily_summary WHERE date = date('now')`
  - "This week's texts" → `SELECT * FROM texts_daily WHERE date >= date('now', '-7 days')`
  - "Top 10 apps by screen time" → `SELECT app_id, SUM(usage_seconds)/3600.0 as hours FROM screen_time GROUP BY app_id ORDER BY hours DESC LIMIT 10`
  - "Recent transactions" → `SELECT * FROM bank_transactions ORDER BY date DESC LIMIT 20`
- **Security note:** This is a local-only dashboard on a private network querying a personal database. Read-only queries only (reject anything starting with INSERT, UPDATE, DELETE, DROP, ALTER, CREATE). This is a safety guardrail, not a security boundary.

### Technical Details

- **Templates:** Use Jinja2 templates (Flask built-in). Either a single-page app with tab navigation, or simple multi-page with a shared nav bar. Either approach is fine.
- **Static assets:** Inline or use Flask's static folder. Chart.js and any CSS framework loaded from CDN.
- **API endpoints:** The dashboard should have JSON API endpoints backing each page so the charts can load data asynchronously:
  - `GET /api/summary?date=YYYY-MM-DD` — daily summary data
  - `GET /api/trends?metric=texts&days=30` — time series data for a metric
  - `GET /api/spending?start=YYYY-MM-DD&end=YYYY-MM-DD` — spending data
  - `GET /api/pipelines` — pipeline health status
  - `POST /api/query` — execute a read-only SQL query, return JSON results
- **Charts:** Chart.js via CDN (`https://cdn.jsdelivr.net/npm/chart.js`). Use `fetch()` to load data from API endpoints and render charts client-side.

### Scheduling

Add a launchd plist (`com.omar.lifedb.dashboard.plist`) to run the dashboard as a persistent background service, same pattern as the health receiver:
- `KeepAlive: true`
- `RunAtLoad: true`
- Bind to `0.0.0.0:8080`

### Access

Accessible from any device on the local network at `http://<mac-local-ip>:8080`. No authentication needed — this is a personal dashboard on a private network.
