#!/usr/bin/env python3
"""Generate a short directive insight from the current time + calendar, via Claude."""

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import ANTHROPIC_API_KEY, DB_PATH, INSIGHT_MODEL, LOCAL_TIMEZONE
from scripts.notify import run_pipeline


LOCAL_TZ = ZoneInfo(LOCAL_TIMEZONE)

SYSTEM_PROMPT = (
    "You are Omar's warm, grounded advisor. You see Omar's calendar and the current "
    "time. Produce two versions of a directive, both addressed to Omar by name and "
    "rooted in concrete things on his calendar:\n\n"
    "short: ONE sentence, under 18 words, a single directive for what to do next. "
    "One idea, one clause. No chaining with em dashes, semicolons, or commas.\n\n"
    "long: 2-3 sentences with richer guidance — may reference multiple events, "
    "flag conflicts, or name what to prioritize across the next few hours.\n\n"
    "Both warm, plain, specific. No greetings, no markdown, no emojis. "
    "Ignore any birthday events on the calendar — do not mention them in either version."
)


class Insight(BaseModel):
    short: str
    long: str


def _parse_iso(s):
    """Parse an ISO-8601 string (date or datetime) → tz-aware datetime in local tz.

    All-day events stored as 'YYYY-MM-DD' are treated as local-midnight.
    """
    if not s:
        return None
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return datetime.fromisoformat(s).replace(tzinfo=LOCAL_TZ)
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(LOCAL_TZ)


def _fmt_event(row):
    cal, start_iso, end_iso, title, location, all_day = row
    start = _parse_iso(start_iso)
    if all_day:
        when = "all day"
    else:
        end = _parse_iso(end_iso)
        when = start.strftime("%H:%M")
        if end:
            when = f"{when}–{end.strftime('%H:%M')}"
    loc = f" @ {location}" if location else ""
    return f"  {when}  {title or '(no title)'}{loc}  [{cal}]"


def build_payload():
    now = datetime.now(LOCAL_TZ)
    today = now.date()
    tomorrow = today + timedelta(days=1)
    day_after = today + timedelta(days=2)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = None
    rows = conn.execute(
        """
        SELECT calendar, start_time, end_time, title, location, all_day
        FROM calendar_events
        WHERE start_time >= ? AND start_time < ?
        ORDER BY start_time
        """,
        (today.isoformat(), day_after.isoformat() + "T23:59:59"),
    ).fetchall()
    conn.close()

    today_remaining = []
    tomorrow_all = []
    for r in rows:
        cal, start_iso, _end, _title, _loc, all_day = r
        start = _parse_iso(start_iso)
        if start.date() == today:
            # For timed events, keep only those still upcoming or in-progress this hour.
            if all_day or start >= now - timedelta(minutes=30):
                today_remaining.append(r)
        elif start.date() == tomorrow:
            tomorrow_all.append(r)

    lines = [f"Current time: {now.strftime('%Y-%m-%d %H:%M %Z')} ({now.strftime('%A')})", ""]
    lines.append(f"Today ({today.isoformat()}) — remaining events:")
    if today_remaining:
        lines.extend(_fmt_event(r) for r in today_remaining)
    else:
        lines.append("  (none)")
    lines.append("")
    lines.append(f"Tomorrow ({tomorrow.isoformat()}):")
    if tomorrow_all:
        lines.extend(_fmt_event(r) for r in tomorrow_all[:6])
    else:
        lines.append("  (none)")

    return "\n".join(lines)


def generate():
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set in .env")

    payload = build_payload()
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    response = client.messages.parse(
        model=INSIGHT_MODEL,
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": payload}],
        output_format=Insight,
    )

    insight: Insight = response.parsed_output
    if not insight or not insight.short or not insight.long:
        raise RuntimeError("Claude returned incomplete structured output")

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO insights (message, long_message, model, input_tokens, output_tokens) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            insight.short,
            insight.long,
            response.model,
            response.usage.input_tokens,
            response.usage.output_tokens,
        ),
    )
    conn.commit()
    conn.close()

    print(f"[generate_insight] short: {insight.short}", file=sys.stderr)
    print(f"[generate_insight] long: {insight.long}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    run_pipeline("generate_insight", generate)
