import os
from pathlib import Path
from dotenv import load_dotenv

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load .env from project root (override shell env so .env is canonical)
load_dotenv(PROJECT_ROOT / ".env", override=True)

# Database
DB_PATH = PROJECT_ROOT / "data" / "life.db"

# Discord (set DISCORD_WEBHOOK_URL in .env)
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# SimpleFIN
SIMPLEFIN_TOKEN = os.getenv("SIMPLEFIN_TOKEN", "")
SIMPLEFIN_SETUP_TOKEN = os.getenv("SIMPLEFIN_SETUP_TOKEN", "")

# iCloud CalDAV
ICLOUD_EMAIL = os.getenv("ICLOUD_EMAIL", "")
ICLOUD_APP_PASSWORD = os.getenv("ICLOUD_APP_PASSWORD", "")
CALDAV_URL = "https://caldav.icloud.com/"
# Comma-separated calendar display names, e.g. CALENDARS_TO_SYNC=Personal,Work
CALENDARS_TO_SYNC = [c.strip() for c in os.getenv("CALENDARS_TO_SYNC", "").split(",") if c.strip()]

# Anthropic (for the daily insight generator)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
INSIGHT_MODEL = os.getenv("INSIGHT_MODEL", "claude-opus-4-7")

# Local timezone used by the insight generator (IANA name)
LOCAL_TIMEZONE = os.getenv("LOCAL_TIMEZONE", "America/Los_Angeles")

# Gmail OAuth
GMAIL_CLIENT_SECRET = PROJECT_ROOT / "config" / "gmail_client_secret.json"
GMAIL_TOKEN_PERSONAL = PROJECT_ROOT / "config" / "gmail_token_personal.json"
GMAIL_TOKEN_WORK = PROJECT_ROOT / "config" / "gmail_token_work.json"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Health receiver
HEALTH_RECEIVER_PORT = 8765

# Dashboard
DASHBOARD_PORT = 8080

# macOS database paths
KNOWLEDGE_DB = Path.home() / "Library" / "Application Support" / "Knowledge" / "knowledgeC.db"
CHAT_DB = Path.home() / "Library" / "Messages" / "chat.db"
CALL_HISTORY_DB = Path.home() / "Library" / "Application Support" / "CallHistoryDB" / "CallHistory.storedata"

# Apple epoch offset (seconds between 1970-01-01 and 2001-01-01)
APPLE_EPOCH_OFFSET = 978307200

# Exports folder
EXPORTS_DIR = PROJECT_ROOT / "exports"
