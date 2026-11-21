#!/usr/bin/env python3
"""Parse AI conversation exports from Claude and ChatGPT into the database."""

import json
import os
import sqlite3
import sys
import zipfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import DB_PATH, EXPORTS_DIR
from scripts.notify import run_pipeline


def parse_claude_conversations(data):
    """Parse Claude export JSON (list of conversation objects)."""
    conversations = []
    for conv in data:
        conv_id = conv.get("uuid", "")
        title = conv.get("name", "")
        created = conv.get("created_at", "")
        date = created[:10] if created else ""
        messages = conv.get("chat_messages", [])
        message_count = len(messages)

        if conv_id:
            conversations.append(("claude", conv_id, title, date, message_count))

    return conversations


def parse_chatgpt_conversations(data):
    """Parse ChatGPT export JSON (list of conversation objects with mapping)."""
    conversations = []
    for conv in data:
        conv_id = conv.get("id", "")
        title = conv.get("title", "")
        create_time = conv.get("create_time", 0)

        if create_time:
            date = datetime.fromtimestamp(create_time).strftime("%Y-%m-%d")
        else:
            date = ""

        # Count messages in the mapping
        mapping = conv.get("mapping", {})
        message_count = 0
        for node in mapping.values():
            msg = node.get("message")
            if msg and msg.get("author", {}).get("role") in ("user", "assistant"):
                message_count += 1

        if conv_id:
            conversations.append(("chatgpt", conv_id, title, date, message_count))

    return conversations


def detect_and_parse(file_path):
    """Detect platform and parse the export file."""
    path = Path(file_path)
    conversations = []

    if path.suffix == ".dms" or (path.suffix == ".zip" and "claude" in path.name.lower()):
        # Claude .dms export (renamed ZIP)
        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                if name.endswith(".json"):
                    with zf.open(name) as f:
                        data = json.load(f)
                        if isinstance(data, list) and data and "uuid" in data[0]:
                            conversations.extend(parse_claude_conversations(data))
                        elif isinstance(data, list) and data and "id" in data[0]:
                            conversations.extend(parse_chatgpt_conversations(data))

    elif path.suffix == ".zip":
        # ChatGPT ZIP export
        with zipfile.ZipFile(path) as zf:
            if "conversations.json" in zf.namelist():
                with zf.open("conversations.json") as f:
                    data = json.load(f)
                    conversations.extend(parse_chatgpt_conversations(data))
            else:
                # Try all JSON files
                for name in zf.namelist():
                    if name.endswith(".json"):
                        with zf.open(name) as f:
                            data = json.load(f)
                            if isinstance(data, list) and data:
                                if "uuid" in data[0]:
                                    conversations.extend(parse_claude_conversations(data))
                                elif "id" in data[0]:
                                    conversations.extend(parse_chatgpt_conversations(data))

    elif path.suffix == ".json":
        with open(path) as f:
            data = json.load(f)
        if isinstance(data, list) and data:
            if "uuid" in data[0]:
                conversations.extend(parse_claude_conversations(data))
            elif "id" in data[0]:
                conversations.extend(parse_chatgpt_conversations(data))

    return conversations


def sync():
    EXPORTS_DIR.mkdir(exist_ok=True)

    # Also scan any subdirectories in exports/ (like "Claude AI Data/")
    scan_dirs = [EXPORTS_DIR]
    # Include the "Claude AI Data" directory at project root if present
    claude_data_dir = EXPORTS_DIR.parent / "Claude AI Data"
    if claude_data_dir.exists():
        scan_dirs.append(claude_data_dir)

    all_files = []
    for scan_dir in scan_dirs:
        for root, dirs, files in os.walk(scan_dir):
            for fname in files:
                if fname.endswith((".json", ".zip", ".dms")):
                    all_files.append(Path(root) / fname)

    conn = sqlite3.connect(DB_PATH)
    total_inserted = 0

    for fpath in all_files:
        conversations = detect_and_parse(fpath)
        for platform, conv_id, title, date, msg_count in conversations:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO ai_conversations "
                "(platform, conversation_id, title, date, message_count) "
                "VALUES (?, ?, ?, ?, ?)",
                (platform, conv_id, title, date, msg_count),
            )
            total_inserted += cursor.rowcount

    conn.commit()
    conn.close()
    return total_inserted


if __name__ == "__main__":
    run_pipeline("parse_ai_exports", sync)
