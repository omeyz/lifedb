#!/usr/bin/env python3
"""Send a monthly Discord reminder to export AI conversation data."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.notify import notify_reminder


def main():
    notify_reminder(
        "**Monthly AI Export Reminder**\n\n"
        "Time to export your AI conversation data:\n\n"
        "1. **Claude** — Go to Settings → Export Data → download the `.dms` file\n"
        "2. **ChatGPT** — Go to Settings → Data Controls → Export Data → download the ZIP\n\n"
        "Drop the files into the `exports/` folder, then run:\n"
        "```\npython3 scripts/parse_ai_exports.py\n```"
    )
    print("Monthly reminder sent.")


if __name__ == "__main__":
    main()
