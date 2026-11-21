# omars-sql-database — Project Specification

## Overview

A personal life-tracking system that consolidates data from multiple sources into a single local SQLite database on macOS. Seven data pipelines feed into the database, orchestrated by macOS launchd, with Discord webhook notifications for errors and reminders.

---

## Tech Stack

- **Language:** Python 3
- **Database:** SQLite (single file, local)
- **Package management:** pip + requirements.txt
- **Scheduling:** macOS launchd (plist files)
- **Notifications:** Discord webhook
- **Health data receiver:** Flask (persistent background service via launchd, bound to 0.0.0.0 for local network access)

---

## Project Structure

```
omars-sql-database/
├── .env                             # Environment variables (SIMPLEFIN_TOKEN)
├── .gitignore                       # Exclude .env, tokens, data/, exports/
├── README.md
├── requirements.txt
├── config/
│   ├── settings.py                  # Central config (paths, constants, webhook URL)
│   ├── gmail_client_secret.json     # Google OAuth client credentials
│   ├── gmail_token_personal.json    # OAuth token for personal Gmail (generated at runtime)
│   └── gmail_token_work.json        # OAuth token for work Gmail (generated at runtime)
├── data/
│   └── life.db                      # SQLite database (created by init_db.py)
├── exports/                         # Drop folder for manual AI conversation exports
├── scripts/
│   ├── init_db.py                   # Creates database and all tables
│   ├── notify.py                    # Discord webhook helper + pipeline run wrapper
│   ├── health_receiver.py           # Flask server for Health Auto Export
│   ├── sync_screen_time.py          # Reads knowledgeC.db
│   ├── sync_texts.py                # Reads chat.db
│   ├── sync_calls.py                # Reads CallHistory.storedata (encrypted)
│   ├── sync_gmail.py                # Gmail API for sent/received counts
│   ├── sync_bank.py                 # SimpleFIN API for transactions
│   ├── parse_ai_exports.py          # Parses Claude/ChatGPT JSON exports
│   └── monthly_reminder.py          # Sends Discord reminder to export AI data
└── launchd/
    ├── com.omar.lifedb.health-receiver.plist
    ├── com.omar.lifedb.sync-screen-time.plist
    ├── com.omar.lifedb.sync-texts.plist
    ├── com.omar.lifedb.sync-calls.plist
    ├── com.omar.lifedb.sync-gmail.plist
    ├── com.omar.lifedb.sync-bank.plist
    └── com.omar.lifedb.monthly-reminder.plist
```

---

## Database Schema

### `bank_transactions`
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PRIMARY KEY | Transaction ID from SimpleFIN |
| account_name | TEXT | |
| description | TEXT | |
| amount | REAL | |
| currency | TEXT | Default 'USD' |
| date | TEXT | YYYY-MM-DD |
| category | TEXT | |
| pending | INTEGER | 0 or 1 |
| ingested_at | TEXT | Auto-set datetime('now') |

### `health_metrics`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PRIMARY KEY | Auto-increment |
| metric_name | TEXT NOT NULL | e.g. 'steps', 'walking_running_distance' |
| value | REAL | |
| unit | TEXT | e.g. 'count', 'km' |
| date | TEXT NOT NULL | YYYY-MM-DD |
| source | TEXT | Default 'apple_health' |
| ingested_at | TEXT | Auto-set |
| | | UNIQUE(metric_name, date, source) |

### `screen_time`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PRIMARY KEY | Auto-increment |
| app_id | TEXT NOT NULL | Bundle identifier |
| usage_seconds | REAL | |
| device_model | TEXT | Apple model identifier, e.g. 'iPhoneNN,N' |
| date | TEXT NOT NULL | YYYY-MM-DD |
| ingested_at | TEXT | Auto-set |
| | | UNIQUE(app_id, date, device_model) |

### `texts_daily`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PRIMARY KEY | Auto-increment |
| date | TEXT NOT NULL UNIQUE | YYYY-MM-DD |
| sent_count | INTEGER | Default 0 |
| received_count | INTEGER | Default 0 |
| ingested_at | TEXT | Auto-set |

### `emails_daily`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PRIMARY KEY | Auto-increment |
| date | TEXT NOT NULL | YYYY-MM-DD |
| account | TEXT NOT NULL | Email address |
| sent_count | INTEGER | Default 0 |
| received_count | INTEGER | Default 0 |
| ingested_at | TEXT | Auto-set |
| | | UNIQUE(date, account) |

### `phone_calls`
| Column | Type | Notes |
|--------|------|-------|
| id INTEGER PRIMARY KEY | Auto-increment |
| date | TEXT NOT NULL | YYYY-MM-DD HH:MM:SS |
| direction | TEXT | 'incoming', 'outgoing', 'missed' |
| duration_seconds | REAL | Default 0 |
| call_type | TEXT | 'regular', 'facetime_audio', 'facetime_video' |
| answered | INTEGER | 0 or 1 |
| ingested_at | TEXT | Auto-set |

### `ai_conversations`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PRIMARY KEY | Auto-increment |
| platform | TEXT NOT NULL | 'claude' or 'chatgpt' |
| conversation_id | TEXT | From export JSON |
| title | TEXT | |
| date | TEXT NOT NULL | YYYY-MM-DD |
| message_count | INTEGER | Default 0 |
| ingested_at | TEXT | Auto-set |
| | | UNIQUE(platform, conversation_id) |

### `pipeline_log`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PRIMARY KEY | Auto-increment |
| pipeline | TEXT NOT NULL | Pipeline name |
| status | TEXT NOT NULL | 'success' or 'error' |
| records_synced | INTEGER | Default 0 |
| error_message | TEXT | Null on success |
| run_at | TEXT | Auto-set |

### `daily_summary` (VIEW)
A convenience view that joins across tables by date to give a single-row-per-day overview: texts sent/received, emails sent/received, phone calls, talk minutes, steps, distance, and screen time hours.

---

## Configuration — `config/settings.py`

Central configuration file containing:

- **DB_PATH:** Path to `data/life.db`
- **DISCORD_WEBHOOK_URL:** read from `.env` (`DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/<id>/<token>`)
- **SIMPLEFIN_TOKEN:** Read from `.env` file in project root (see `.env.example`)
- **Gmail OAuth paths:** Paths to client secret and per-account token files
- **HEALTH_RECEIVER_PORT:** `8765`
- **macOS database paths:**
  - `~/Library/Application Support/Knowledge/knowledgeC.db`
  - `~/Library/Messages/chat.db`
  - `~/Library/Application Support/CallHistoryDB/CallHistory.storedata`
- **APPLE_EPOCH_OFFSET:** `978307200` (seconds between 1970-01-01 and 2001-01-01)

---

## Pipeline Details

### 1. Bank Transactions — `sync_bank.py`

**Source:** SimpleFIN API
**Schedule:** Daily
**Auth:** SimpleFIN token stored in `.env` file in project root (use `python-dotenv` to load)

**Logic:**
- Call SimpleFIN API with the stored token to fetch recent transactions
- Parse response JSON for transaction ID, account name, description, amount, date, pending status
- INSERT OR IGNORE into `bank_transactions` (deduplicate on transaction ID)
- Return count of new records inserted

**Error handling:** If SimpleFIN returns non-200, raise with status code and body.

---

### 2. Health Metrics — `health_receiver.py`

**Source:** Health Auto Export iOS app
**Schedule:** Persistent Flask server (launchd keeps it alive)
**Bind:** `0.0.0.0:8765` (accessible from iPhone on local network)

**Endpoint:** `POST /health`

**Logic:**
- Receive JSON payload from Health Auto Export
- The app sends data structured as `{"data": {"metrics": [...]}}` where each metric has `name`, `units`, and a `data` array of `{date, qty}` entries
- Normalize metric names to lowercase/snake_case
- Normalize dates to YYYY-MM-DD
- INSERT OR REPLACE into `health_metrics` (upsert on metric_name + date + source)
- Return JSON response with count of records inserted

**Additional endpoint:** `GET /health` — simple health check returning `{"status": "running"}`

**User setup:** In Health Auto Export app, set the REST API automation URL to `http://<mac-local-ip>:8765/health`, format JSON. The user has already selected steps + walking/running distance.

---

### 3. Screen Time — `sync_screen_time.py`

**Source:** `~/Library/Application Support/Knowledge/knowledgeC.db`
**Schedule:** Daily
**Auth:** Requires Full Disk Access for Terminal (already enabled)

**Logic:**
- Open `knowledgeC.db` in read-only mode
- Query the ZOBJECT table where `ZSTREAMNAME = '/app/usage'`
- Join with ZSOURCE and ZSYNCPEER for device info
- Convert Apple epoch timestamps: `ZSTARTDATE + 978307200` → Unix timestamp → YYYY-MM-DD
- Calculate usage duration: `ZENDDATE - ZSTARTDATE` (seconds)
- Aggregate by app_id + date + device_model
- INSERT OR REPLACE into `screen_time`
- Return count of records synced

**Key query pattern:**
```sql
SELECT
    ZOBJECT.ZVALUESTRING AS app_id,
    (ZOBJECT.ZENDDATE - ZOBJECT.ZSTARTDATE) AS usage_seconds,
    DATETIME(ZOBJECT.ZSTARTDATE + 978307200, 'unixepoch', 'localtime') AS start_time,
    ZMODEL AS device_model
FROM ZOBJECT
LEFT JOIN ZSTRUCTUREDMETADATA ON ZOBJECT.ZSTRUCTUREDMETADATA = ZSTRUCTUREDMETADATA.Z_PK
LEFT JOIN ZSOURCE ON ZOBJECT.ZSOURCE = ZSOURCE.Z_PK
LEFT JOIN ZSYNCPEER ON ZSOURCE.ZDEVICEID = ZSYNCPEER.ZDEVICEID
WHERE ZSTREAMNAME = '/app/usage'
```

**Note:** On macOS 13+ (Ventura), some data may have moved to the Biome database. The script should check if `knowledgeC.db` returns data and warn if it appears empty. If iCloud sync is enabled for Screen Time, this database includes data from all linked devices (iPhone, iPad).

---

### 4. Texts Sent/Received — `sync_texts.py`

**Source:** `~/Library/Messages/chat.db`
**Schedule:** Daily
**Auth:** Requires Full Disk Access (already enabled)

**Logic:**
- Open `chat.db` in read-only mode
- Query the `message` table, counting messages grouped by date and `is_from_me` flag
- Convert Apple epoch timestamps: `date/1000000000 + 978307200` → Unix → YYYY-MM-DD (note: iMessage timestamps are in nanoseconds since 2001-01-01)
- No message content is stored — only daily sent/received counts
- INSERT OR REPLACE into `texts_daily`
- Return count of days synced

**Key query pattern:**
```sql
SELECT
    DATE(DATETIME(message.date / 1000000000 + 978307200, 'unixepoch', 'localtime')) AS msg_date,
    SUM(CASE WHEN is_from_me = 1 THEN 1 ELSE 0 END) AS sent,
    SUM(CASE WHEN is_from_me = 0 THEN 1 ELSE 0 END) AS received
FROM message
WHERE message.date > 0
GROUP BY msg_date
```

**Note:** iCloud Messages sync must be enabled (user confirmed it is). The `text` column is NOT read — only `is_from_me`, `date`, and row counts.

---

### 5. Emails Sent/Received — `sync_gmail.py`

**Source:** Gmail API (two accounts — personal and work)
**Schedule:** Daily
**Auth:** OAuth 2.0 Desktop app flow

**Credentials:**
- Client secret: `config/gmail_client_secret.json` (client_id: `<your-client-id>`, project: `<your-gcp-project>`)
- Token files: `config/gmail_token_personal.json` and `config/gmail_token_work.json`
- Scopes needed: `https://www.googleapis.com/auth/gmail.readonly`

**Logic:**
- For each account (personal, work):
  - Load or refresh OAuth token from the token file
  - If token is expired or revoked (HTTP 400/401), send a Discord notification: "Gmail auth expired for {account} — re-authenticate by running: `python3 sync_gmail.py --auth {personal|work}`"
  - Query Gmail API for messages sent yesterday: `in:sent after:YYYY/MM/DD before:YYYY/MM/DD`
  - Query Gmail API for messages received yesterday: `in:inbox after:YYYY/MM/DD before:YYYY/MM/DD`
  - Use `resultSizeEstimate` or iterate `messages[]` for counts
  - INSERT OR REPLACE into `emails_daily` with the account email address
- Return total count of day-records synced

**First-time auth flow:** Running `python3 sync_gmail.py --auth personal` (or `--auth work`) should open a browser for OAuth consent, then save the token file. This only needs to happen once per account (and again after password changes).

**Important:** Password changes on either Gmail account will revoke OAuth tokens. The script must catch 400/401 errors gracefully and notify via Discord rather than silently failing.

---

### 6. Phone Calls — `sync_calls.py`

**Source:** `~/Library/Application Support/CallHistoryDB/CallHistory.storedata`
**Schedule:** Daily
**Auth:** Requires Full Disk Access (already enabled)

**Encryption:** NOT required on the user's macOS version. The database is a standard SQLite file readable directly. The `ZCALLRECORD` table is confirmed present.

**Logic:**
- Open `CallHistory.storedata` in read-only mode
- Map fields:
  - `ZDATE + 978307200` → Unix timestamp → formatted datetime
  - `ZDURATION` → duration in seconds
  - `ZORIGINATED`: 1 = outgoing, 0 = incoming
  - `ZANSWERED`: 1 = answered, 0 = missed (when incoming + not answered)
  - `ZCALLTYPE`: determine regular vs FaceTime
  - Direction logic: if `ZORIGINATED=1` → 'outgoing'; elif `ZANSWERED=1` → 'incoming'; else → 'missed'
- INSERT into `phone_calls` (deduplicate on date + direction + duration to avoid re-inserting known calls)
- Return count of new records inserted

**Note:** The call history database only retains the last several hundred records. The daily cron schedule ensures records are captured before they age out.

---

### 7. AI Conversations — `parse_ai_exports.py`

**Source:** Manual JSON exports from Claude and ChatGPT, dropped into `exports/` folder
**Schedule:** Manual (run after placing export files in `exports/`)

**Claude export format:** The export is a `.dms` file (renamed ZIP). Inside is JSON with conversation objects containing `uuid`, `name`, `created_at`, and a `chat_messages` array.

**ChatGPT export format:** The export is a ZIP containing `conversations.json` — an array of objects with `id`, `title`, `create_time`, and a `mapping` object whose entries represent messages.

**Logic:**
- Scan `exports/` folder for new export files (ZIP, .dms, or JSON)
- Detect platform by file structure
- For Claude: extract conversation_id, title, date, and count messages in `chat_messages`
- For ChatGPT: extract conversation id, title, date from `create_time`, and count user/assistant messages in `mapping`
- INSERT OR IGNORE into `ai_conversations` (deduplicate on platform + conversation_id)
- Return count of new conversations imported

**Note:** This is the only non-automated pipeline. The monthly reminder handles prompting the user to do exports.

---

### Monthly Reminder — `monthly_reminder.py`

**Schedule:** 1st of every month
**Logic:** Send a Discord message via the webhook reminding the user to export AI conversation data from Claude and ChatGPT and drop the files in the `exports/` folder.

---

## Notifications — `notify.py`

Utility module used by all pipelines.

**Functions:**
- `send_discord(message, title, color)` — Posts an embed to the Discord webhook. Uses `urllib.request` (no external dependency).
- `notify_error(pipeline_name, error_msg)` — Red embed with error details.
- `notify_success(pipeline_name, records_synced)` — Green embed with record count.
- `notify_reminder(message)` — Blue embed for reminders.
- `log_pipeline(pipeline_name, status, records_synced, error_message)` — Writes to `pipeline_log` table.
- `run_pipeline(pipeline_name, func)` — Wrapper that calls a pipeline function, logs the result, sends Discord notification on success or failure.

---

## Scheduling — launchd

All plist files go in `~/Library/LaunchAgents/` and are loaded with `launchctl load <plist>`.

### Schedule Summary

| Pipeline | Plist | Schedule |
|----------|-------|----------|
| Health receiver | `com.omar.lifedb.health-receiver.plist` | KeepAlive (persistent) |
| Screen time sync | `com.omar.lifedb.sync-screen-time.plist` | Daily at 11:55 PM |
| Texts sync | `com.omar.lifedb.sync-texts.plist` | Daily at 11:55 PM |
| Calls sync | `com.omar.lifedb.sync-calls.plist` | Daily at 11:55 PM |
| Gmail sync | `com.omar.lifedb.sync-gmail.plist` | Daily at 11:55 PM |
| Bank sync | `com.omar.lifedb.sync-bank.plist` | Daily at 11:55 PM |
| Monthly reminder | `com.omar.lifedb.monthly-reminder.plist` | 1st of each month, 10:00 AM |

**Health receiver plist** should use `KeepAlive: true` and `RunAtLoad: true` so it starts on login and restarts if it crashes.

**All sync plists** should include `StandardOutPath` and `StandardErrorPath` pointing to a `logs/` directory for debugging.

---

## Error Handling

Every pipeline script follows the same pattern via `run_pipeline()`:

1. Execute the sync logic
2. On success: log to `pipeline_log`, send green Discord embed with record count
3. On failure: log to `pipeline_log` with error message, send red Discord embed with error details, re-raise exception (so launchd sees non-zero exit)

**Gmail-specific:** On HTTP 400/401, the Discord notification should include the re-auth command: `python3 sync_gmail.py --auth {account}`

---

## Dependencies — `requirements.txt`

```
flask
google-auth
google-auth-oauthlib
google-auth-httplib2
google-api-python-client
requests
python-dotenv
```

Note: `sqlite3` and `urllib.request` are stdlib — no install needed. The `security` command for Keychain access is a macOS system binary.

---

## Setup Steps (for README.md)

1. Clone repo
2. `pip install -r requirements.txt`
3. Run `python3 scripts/init_db.py` to create the database
4. Place `gmail_client_secret.json` in `config/`
5. Run `python3 scripts/sync_gmail.py --auth personal` and `--auth work` to authenticate both Gmail accounts
6. Verify `.env` file exists in project root with `SIMPLEFIN_TOKEN=<your-token>`
7. Configure Health Auto Export iOS app to POST to `http://<mac-local-ip>:8765/health`
8. Copy all launchd plists to `~/Library/LaunchAgents/`
9. Load all plists: `launchctl load ~/Library/LaunchAgents/com.omar.lifedb.*.plist`
10. Verify health receiver is running: `curl http://localhost:8765/health`

---

## Future Considerations (not in v1)

- Local web dashboard (Flask/Node) for querying and visualization
- Correlational analyses (HRV vs screen time, sleep vs activity, spending vs calendar)
- Garmin watch integration for biometrics
- Location history tracking
- iMessage content analysis (currently counts only)
- Migration from SQLite to PostgreSQL if needed at scale
