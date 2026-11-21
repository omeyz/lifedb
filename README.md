# Omar's Life Database

A personal life-tracking system that consolidates data from multiple sources into a single local SQLite database on macOS.

## Pipelines

| Pipeline | Source | Schedule |
|----------|--------|----------|
| Bank Transactions | SimpleFIN API | Daily 11:55 PM |
| Health Metrics | Health Auto Export iOS app → Flask server | Persistent |
| Screen Time | macOS knowledgeC.db | Daily 11:55 PM |
| Texts | macOS chat.db (iMessage) | Daily 11:55 PM |
| Phone Calls | macOS CallHistory.storedata | Daily 11:55 PM |
| Emails | Gmail API (2 accounts) | Daily 11:55 PM |
| AI Conversations | Manual Claude/ChatGPT exports | Manual |
| Calendar | iCloud CalDAV | Every 90 min, 6:55 AM-9:55 PM |
| Daily Insight | Claude API over the calendar | Every 90 min, 7 AM-10 PM |

## Setup

Everything personal lives outside the repo: `.env`, `config/*.json`, `data/`, `exports/` and `logs/` are gitignored.

### Configuration

1. `cp .env.example .env` and fill in:
   - `SIMPLEFIN_SETUP_TOKEN` (then `--claim` writes `SIMPLEFIN_TOKEN`, the access URL)
   - `ICLOUD_EMAIL`, `ICLOUD_APP_PASSWORD` (app-specific password), `CALENDARS_TO_SYNC` (comma-separated calendar names)
   - `DISCORD_WEBHOOK_URL` (leave blank to turn notifications off)
   - `ANTHROPIC_API_KEY`, optional `INSIGHT_MODEL`, `LOCAL_TIMEZONE`
2. Create a Google Cloud OAuth client (Desktop app) with the Gmail API enabled and save it as `config/gmail_client_secret.json`. Token files are created by `--auth`.
3. The launchd plists use `__PROJECT_DIR__` as a placeholder. Replace it with your clone path before copying them:
   `sed -i '' "s|__PROJECT_DIR__|$PWD|g" launchd/*.plist`
   They call `/opt/homebrew/bin/python3`; change that if your Python lives elsewhere.
4. The screen time, texts and calls pipelines need Full Disk Access for the Python/Terminal that runs them.

### Install

1. `python3 -m pip install -r requirements.txt`
2. `python3 scripts/init_db.py`
3. Place `gmail_client_secret.json` in `config/`
4. `python3 scripts/sync_gmail.py --auth personal`
5. `python3 scripts/sync_gmail.py --auth work`
6. Ensure `.env` has `SIMPLEFIN_TOKEN=<access-url>` (run `python3 scripts/sync_bank.py --claim` if needed)
7. Configure Health Auto Export app to POST to `http://<mac-ip>:8765/health`
8. Copy launchd plists: `cp launchd/*.plist ~/Library/LaunchAgents/`
9. Load all: `launchctl load ~/Library/LaunchAgents/com.omar.lifedb.*.plist`
10. Verify: `curl http://localhost:8765/health`

## Manual Operations

- **AI exports:** Drop `.dms`/`.zip`/`.json` files in `exports/`, then run `python3 scripts/parse_ai_exports.py`
- **Re-auth Gmail:** `python3 scripts/sync_gmail.py --auth {personal|work}`
- **Claim SimpleFIN:** `python3 scripts/sync_bank.py --claim`

## Query Examples

```sql
-- Daily summary
SELECT * FROM daily_summary WHERE date >= '2026-03-01';

-- Top apps by screen time this week
SELECT app_id, SUM(usage_seconds)/3600.0 AS hours
FROM screen_time WHERE date >= date('now', '-7 days')
GROUP BY app_id ORDER BY hours DESC LIMIT 10;

-- Monthly spending
SELECT strftime('%Y-%m', date) AS month, SUM(amount) AS total
FROM bank_transactions GROUP BY month ORDER BY month DESC;
```
