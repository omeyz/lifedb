#!/usr/bin/env python3
"""Import headerless bank CSV exports (date, amount, *, blank, description) into bank_transactions."""

import argparse
import csv
import hashlib
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import DB_PATH


def parse_date(date_str):
    """Convert MM/DD/YYYY to YYYY-MM-DD."""
    return datetime.strptime(date_str.strip(), "%m/%d/%Y").strftime("%Y-%m-%d")


def make_id(date, amount, description):
    """Generate a deterministic transaction ID."""
    raw = f"{date}|{amount}|{description}"
    return hashlib.md5(raw.encode()).hexdigest()


def import_csv(csv_path, account_name, dry_run=False):
    """Import a single CSV file. Returns count of new records."""
    path = Path(csv_path)
    if not path.exists():
        print(f"File not found: {csv_path}")
        return 0

    # Read with auto-detect encoding, handle BOM
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = path.read_text(encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        print(f"Could not decode {csv_path}")
        return 0

    reader = csv.reader(text.splitlines())
    rows = list(reader)

    if not rows:
        print(f"Empty file: {csv_path}")
        return 0

    # Detect if first row is a header (non-date in column 0)
    try:
        parse_date(rows[0][0])
    except (ValueError, IndexError):
        print(f"Skipping header row: {rows[0]}")
        rows = rows[1:]

    transactions = []
    for i, row in enumerate(rows):
        if len(row) < 5:
            print(f"Skipping short row {i + 1}: {row}")
            continue

        try:
            date = parse_date(row[0])
            amount = float(row[1].strip().replace(",", ""))
            description = row[4].strip()
        except (ValueError, IndexError) as e:
            print(f"Skipping malformed row {i + 1}: {e}")
            continue

        txn_id = make_id(date, amount, description)
        transactions.append((txn_id, account_name, description, amount, "USD", date, 0))

    if dry_run:
        print(f"\n[DRY RUN] {path.name}: {len(transactions)} transactions parsed")
        for txn in transactions[:10]:
            print(f"  {txn[5]}  {txn[3]:>10.2f}  {txn[2][:60]}")
        if len(transactions) > 10:
            print(f"  ... and {len(transactions) - 10} more")
        return len(transactions)

    conn = sqlite3.connect(DB_PATH)
    inserted = 0
    for txn in transactions:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO bank_transactions "
            "(id, account_name, description, amount, currency, date, pending) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            txn,
        )
        inserted += cursor.rowcount

    conn.commit()
    conn.close()
    return inserted


def main():
    parser = argparse.ArgumentParser(description="Import a bank CSV into bank_transactions")
    parser.add_argument("files", nargs="+", help="CSV file(s) to import")
    parser.add_argument("--account", default="Checking", help="Account name (default: Checking)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to database")
    args = parser.parse_args()

    total = 0
    for f in args.files:
        count = import_csv(f, args.account, dry_run=args.dry_run)
        total += count
        action = "would import" if args.dry_run else "imported"
        print(f"{Path(f).name}: {count} records {action}")

    print(f"\nTotal: {total} records")


if __name__ == "__main__":
    main()
