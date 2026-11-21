#!/usr/bin/env python3
"""Sync iCloud calendar events into life.db via CalDAV."""

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import caldav
import icalendar

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import (
    CALDAV_URL,
    CALENDARS_TO_SYNC,
    DB_PATH,
    ICLOUD_APP_PASSWORD,
    ICLOUD_EMAIL,
)
from scripts.notify import run_pipeline


LOOKBACK_DAYS = 1
LOOKAHEAD_DAYS = 14


def _iso(dt):
    """Normalize date/datetime to ISO-8601 string."""
    if dt is None:
        return None
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)


def _is_all_day(dtstart):
    """A VEVENT is all-day if DTSTART is a date (not datetime)."""
    from datetime import date
    return isinstance(dtstart, date) and not isinstance(dtstart, datetime)


def _extract_event(component):
    """Pull fields from a VEVENT component → dict or None."""
    uid = component.get("UID")
    dtstart = component.get("DTSTART")
    if not uid or not dtstart:
        return None

    dtend = component.get("DTEND")
    summary = component.get("SUMMARY")
    location = component.get("LOCATION")
    description = component.get("DESCRIPTION")

    return {
        "uid": str(uid),
        "title": str(summary) if summary else None,
        "start_time": _iso(dtstart.dt),
        "end_time": _iso(dtend.dt) if dtend else None,
        "all_day": 1 if _is_all_day(dtstart.dt) else 0,
        "location": str(location).strip() if location else None,
        "description": str(description).strip() if description else None,
    }


def sync():
    if not ICLOUD_EMAIL or not ICLOUD_APP_PASSWORD:
        raise RuntimeError("ICLOUD_EMAIL or ICLOUD_APP_PASSWORD not set in .env")

    client = caldav.DAVClient(
        url=CALDAV_URL, username=ICLOUD_EMAIL, password=ICLOUD_APP_PASSWORD,
    )
    principal = client.principal()
    all_calendars = principal.calendars()

    # Whitelist by display name
    chosen = []
    for cal in all_calendars:
        try:
            name = cal.get_display_name()
        except Exception:
            continue
        if name in CALENDARS_TO_SYNC:
            chosen.append((name, cal))

    if not chosen:
        raise RuntimeError(f"No calendars matched {CALENDARS_TO_SYNC}")

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=LOOKBACK_DAYS)
    end = now + timedelta(days=LOOKAHEAD_DAYS)

    conn = sqlite3.connect(DB_PATH)
    total = 0

    for name, cal in chosen:
        try:
            raw_events = cal.search(start=start, end=end, event=True, expand=True)
        except Exception as e:
            print(f"[sync_calendar] search failed for {name}: {e}", file=sys.stderr)
            continue

        for e in raw_events:
            try:
                cal_obj = icalendar.Calendar.from_ical(e.data)
                for component in cal_obj.walk():
                    if component.name != "VEVENT":
                        continue
                    row = _extract_event(component)
                    if not row:
                        continue
                    conn.execute(
                        """
                        INSERT INTO calendar_events
                          (uid, calendar, title, start_time, end_time, all_day, location, description)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(uid, calendar, start_time) DO UPDATE SET
                          title = excluded.title,
                          end_time = excluded.end_time,
                          all_day = excluded.all_day,
                          location = excluded.location,
                          description = excluded.description,
                          ingested_at = datetime('now')
                        """,
                        (
                            row["uid"], name, row["title"], row["start_time"],
                            row["end_time"], row["all_day"], row["location"], row["description"],
                        ),
                    )
                    total += 1
            except Exception as ex:
                print(f"[sync_calendar] parse failed in {name}: {ex}", file=sys.stderr)

    conn.commit()
    conn.close()
    return total


if __name__ == "__main__":
    run_pipeline("sync_calendar", sync)
