#!/usr/bin/env python3
"""Sync bank transactions from SimpleFIN API."""

import base64
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import DB_PATH, SIMPLEFIN_TOKEN, SIMPLEFIN_SETUP_TOKEN
from scripts.notify import run_pipeline

# If no access token exists yet, the setup token must be claimed first.
# Run: python3 scripts/sync_bank.py --claim


def claim_setup_token(setup_token):
    """Claim a SimpleFIN setup token to get an access URL."""
    claim_url = base64.b64decode(setup_token).decode("utf-8")
    resp = requests.post(claim_url, timeout=30)
    resp.raise_for_status()
    return resp.text.strip()


def sync():
    token = SIMPLEFIN_TOKEN
    if not token:
        raise RuntimeError(
            "SIMPLEFIN_TOKEN not set in .env. "
            "Run `python3 scripts/sync_bank.py --claim` first."
        )

    # Token is the access URL: https://user:pass@bridge.simplefin.org/simplefin
    parsed = urlparse(token)
    base_url = f"{parsed.scheme}://{parsed.hostname}{parsed.path}"

    # Fetch accounts/transactions for the last 30 days
    start = datetime.now() - timedelta(days=30)
    start_ts = int(start.timestamp())

    url = f"{base_url}/accounts?start-date={start_ts}"
    resp = requests.get(url, auth=(parsed.username, parsed.password), timeout=30)
    resp.raise_for_status()

    data = resp.json()

    conn = sqlite3.connect(DB_PATH)
    inserted = 0

    for account in data.get("accounts", []):
        account_name = account.get("name", "Unknown")
        currency = account.get("currency", "USD")

        for txn in account.get("transactions", []):
            txn_id = txn.get("id", "")
            description = txn.get("description", "")
            amount = txn.get("amount", 0)
            posted = txn.get("posted", 0)
            date = datetime.fromtimestamp(posted).strftime("%Y-%m-%d") if posted else ""
            pending = 1 if txn.get("pending", False) else 0

            cursor = conn.execute(
                "INSERT OR IGNORE INTO bank_transactions "
                "(id, account_name, description, amount, currency, date, pending) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (txn_id, account_name, description, amount, currency, date, pending),
            )
            inserted += cursor.rowcount

    conn.commit()
    conn.close()
    return inserted


def main():
    if "--claim" in sys.argv:
        if not SIMPLEFIN_SETUP_TOKEN:
            print("No SIMPLEFIN_SETUP_TOKEN found in .env")
            sys.exit(1)

        print("Claiming SimpleFIN setup token...")
        access_url = claim_setup_token(SIMPLEFIN_SETUP_TOKEN)
        print(f"Access URL obtained. Add this to your .env file:")
        print(f"SIMPLEFIN_TOKEN={access_url}")

        # Auto-write to .env
        env_path = Path(__file__).resolve().parent.parent / ".env"
        content = env_path.read_text()
        if "SIMPLEFIN_TOKEN=" not in content:
            content += f"\nSIMPLEFIN_TOKEN={access_url}\n"
        else:
            lines = content.splitlines()
            lines = [
                f"SIMPLEFIN_TOKEN={access_url}" if l.startswith("SIMPLEFIN_TOKEN=") else l
                for l in lines
            ]
            content = "\n".join(lines) + "\n"
        env_path.write_text(content)
        print("Saved to .env")
        return

    run_pipeline("sync_bank", sync)


if __name__ == "__main__":
    main()
