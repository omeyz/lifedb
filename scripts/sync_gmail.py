#!/usr/bin/env python3
"""Sync daily email sent/received counts from Gmail API (two accounts)."""

import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import (
    DB_PATH,
    GMAIL_CLIENT_SECRET,
    GMAIL_TOKEN_PERSONAL,
    GMAIL_TOKEN_WORK,
    GMAIL_SCOPES,
)
from scripts.notify import run_pipeline, notify_error

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


ACCOUNTS = {
    "personal": GMAIL_TOKEN_PERSONAL,
    "work": GMAIL_TOKEN_WORK,
}


def get_credentials(account_name, token_path):
    """Load or refresh OAuth credentials. Returns (creds, email) or raises."""
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), GMAIL_SCOPES)

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            token_path.write_text(creds.to_json())
        except Exception:
            creds = None

    if not creds or not creds.valid:
        raise RuntimeError(
            f"Gmail auth expired for {account_name} — re-authenticate by running: "
            f"python3 scripts/sync_gmail.py --auth {account_name}"
        )

    return creds


def authenticate(account_name):
    """Run interactive OAuth flow for an account."""
    token_path = ACCOUNTS[account_name]
    flow = InstalledAppFlow.from_client_secrets_file(str(GMAIL_CLIENT_SECRET), GMAIL_SCOPES)
    creds = flow.run_local_server(port=0)
    token_path.write_text(creds.to_json())
    print(f"Token saved for {account_name} at {token_path}")


def count_messages(service, query):
    """Count messages by paginating through all results."""
    count = 0
    page_token = None
    while True:
        results = service.users().messages().list(
            userId="me", q=query, maxResults=500,
            pageToken=page_token, fields="nextPageToken,messages(id)"
        ).execute()
        msgs = results.get("messages", [])
        count += len(msgs)
        page_token = results.get("nextPageToken")
        if not page_token:
            break
    return count


def sync_day(conn, service, email, target_date):
    """Sync sent/received counts for a single day and account."""
    after = target_date.strftime("%Y/%m/%d")
    before = (target_date + timedelta(days=1)).strftime("%Y/%m/%d")

    sent = count_messages(service, f"in:sent after:{after} before:{before}")
    received = count_messages(service, f"in:inbox after:{after} before:{before}")

    conn.execute(
        "INSERT OR REPLACE INTO emails_daily (date, account, sent_count, received_count) "
        "VALUES (?, ?, ?, ?)",
        (target_date.strftime("%Y-%m-%d"), email, sent, received),
    )
    return 1


def sync():
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)

    # On first run (no data yet), backfill last 7 days
    conn = sqlite3.connect(DB_PATH)
    existing = conn.execute("SELECT COUNT(*) FROM emails_daily").fetchone()[0]
    if existing == 0:
        days_to_sync = [today - timedelta(days=i) for i in range(7)]
    else:
        days_to_sync = [today, yesterday]

    total = 0

    for account_name, token_path in ACCOUNTS.items():
        try:
            creds = get_credentials(account_name, token_path)
        except RuntimeError as e:
            notify_error("sync_gmail", str(e))
            continue

        service = build("gmail", "v1", credentials=creds)

        profile = service.users().getProfile(userId="me").execute()
        email = profile.get("emailAddress", account_name)

        for day in days_to_sync:
            total += sync_day(conn, service, email, day)

    conn.commit()
    conn.close()
    return total


def backfill(days):
    """Backfill the last N days of email data."""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    conn = sqlite3.connect(DB_PATH)
    total = 0

    for account_name, token_path in ACCOUNTS.items():
        try:
            creds = get_credentials(account_name, token_path)
        except RuntimeError as e:
            print(f"Skipping {account_name}: {e}")
            continue

        service = build("gmail", "v1", credentials=creds)
        profile = service.users().getProfile(userId="me").execute()
        email = profile.get("emailAddress", account_name)

        print(f"\nBackfilling {email} — {days} days...")
        for i in range(days):
            day = today - timedelta(days=i)
            sync_day(conn, service, email, day)
            total += 1
            if (i + 1) % 30 == 0:
                conn.commit()
                print(f"  {email}: {i + 1}/{days} days done")

    conn.commit()
    conn.close()
    print(f"\nBackfill complete: {total} day-records synced")
    return total


def main():
    if "--auth" in sys.argv:
        idx = sys.argv.index("--auth")
        if idx + 1 >= len(sys.argv):
            print("Usage: python3 sync_gmail.py --auth {personal|work}")
            sys.exit(1)
        account = sys.argv[idx + 1]
        if account not in ACCOUNTS:
            print(f"Unknown account: {account}. Choose 'personal' or 'work'.")
            sys.exit(1)
        authenticate(account)
        return

    if "--backfill" in sys.argv:
        idx = sys.argv.index("--backfill")
        days = int(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else 730
        backfill(days)
        return

    run_pipeline("sync_gmail", sync)


if __name__ == "__main__":
    main()
