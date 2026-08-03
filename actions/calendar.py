"""
Calendar — Windows version.

If Outlook is installed, reads/writes via Outlook COM; otherwise maintains a local
calendar in memory/calendar.json. Calendar APIs have the same signatures as the
original macOS version.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import uuid
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
LOCAL_CAL_FILE = BASE_DIR / "memory" / "calendar.json"

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

DEFAULT_DURATION_MIN = 60


# ── Outlook ─────────────────────────────────────────────────────────────────

def _try_outlook():
    try:
        import win32com.client  # type: ignore
        import pythoncom  # type: ignore
        pythoncom.CoInitialize()
        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        return outlook, namespace
    except Exception:
        return None, None


def _outlook_calendar_folder(namespace, name: str = ""):
    cal = namespace.GetDefaultFolder(9)  # olFolderCalendar
    if name:
        try:
            for item in namespace.Folders.Item(1).Folders:
                if item.Name.lower() == name.lower():
                    return item
        except Exception:
            pass
    return cal


def _outlook_events_in_range(start: dt.datetime, end: dt.datetime, calendar_name: str = "") -> list[dict]:
    outlook, namespace = _try_outlook()
    if not outlook:
        return []
    try:
        folder = _outlook_calendar_folder(namespace, calendar_name)
        items = folder.Items
        items.IncludeRecurrences = True
        items.Sort("[Start]")
        restriction = "[Start] >= '{0}' AND [Start] < '{1}'".format(
            start.strftime("%m/%d/%Y %H:%M %p"),
            end.strftime("%m/%d/%Y %H:%M %p"),
        )
        try:
            filtered = items.Restrict(restriction)
        except Exception:
            filtered = items

        events = []
        for it in filtered:
            try:
                s = it.Start
                e = it.End
                if hasattr(s, "timestamp"):
                    s_ts = int(s.timestamp())
                    e_ts = int(e.timestamp())
                else:
                    s_dt = dt.datetime.strptime(str(s)[:19], "%Y-%m-%d %H:%M:%S")
                    e_dt = dt.datetime.strptime(str(e)[:19], "%Y-%m-%d %H:%M:%S")
                    s_ts = int(s_dt.timestamp())
                    e_ts = int(e_dt.timestamp())
                events.append({
                    "start_ts": s_ts,
                    "end_ts": e_ts,
                    "title": str(getattr(it, "Subject", "") or "Unnamed event"),
                    "calendar": calendar_name or "Outlook",
                    "location": str(getattr(it, "Location", "") or ""),
                    "all_day": bool(getattr(it, "AllDayEvent", False)),
                })
            except Exception:
                continue
        return events
    except Exception:
        return []


def _outlook_add(title: str, start: dt.datetime, end: dt.datetime, location: str, notes: str, all_day: bool, calendar_name: str) -> dict | None:
    outlook, namespace = _try_outlook()
    if not outlook:
        return None
    try:
        appt = outlook.CreateItem(1)  # olAppointmentItem
        appt.Subject = title
        appt.Start = start.strftime("%Y-%m-%d %H:%M")
        if all_day:
            appt.AllDayEvent = True
        else:
            appt.End = end.strftime("%Y-%m-%d %H:%M")
        if location:
            appt.Location = location
        if notes:
            appt.Body = notes
        appt.Save()
        return {
            "start_ts": int(start.timestamp()),
            "end_ts": int(end.timestamp()),
            "title": title,
            "calendar": calendar_name or "Outlook",
            "location": location,
            "all_day": all_day,
        }
    except Exception:
        return None


def _outlook_delete(title: str, start: dt.datetime | None, calendar_name: str, delete_all: bool) -> tuple[bool, dict | None]:
    outlook, namespace = _try_outlook()
    if not outlook:
        return False, None
    try:
        folder = _outlook_calendar_folder(namespace, calendar_name)
        items = folder.Items
        items.IncludeRecurrences = True
        items.Sort("[Start]")
        deleted = None
        for it in list(items):
            try:
                if str(getattr(it, "Subject", "")).strip().lower() != title.strip().lower():
                    continue
                if start is not None:
                    try:
                        s = it.Start
                        s_dt = dt.datetime.strptime(str(s)[:16], "%Y-%m-%d %H:%M")
                        if abs((s_dt - start).total_seconds()) > 60:
                            continue
                    except Exception:
                        continue
                ev = {
                    "start_ts": int(dt.datetime.strptime(str(it.Start)[:19], "%Y-%m-%d %H:%M:%S").timestamp()),
                    "end_ts": int(dt.datetime.strptime(str(it.End)[:19], "%Y-%m-%d %H:%M:%S").timestamp()),
                    "title": str(getattr(it, "Subject", "")),
                    "calendar": calendar_name or "Outlook",
                    "location": str(getattr(it, "Location", "") or ""),
                    "all_day": bool(getattr(it, "AllDayEvent", False)),
                }
                it.Delete()
                deleted = ev
                if not delete_all:
                    break
            except Exception:
                continue
        return (deleted is not None), deleted
    except Exception:
        return False, None


# ── Local JSON ──────────────────────────────────────────────────────────────

def _load_local() -> list[dict]:
    if not LOCAL_CAL_FILE.exists():
        return []
    try:
        return json.loads(LOCAL_CAL_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_local(events: list[dict]) -> None:
    LOCAL_CAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_CAL_FILE.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")


def _local_events_in_range(start: dt.datetime, end: dt.datetime, calendar_name: str = "") -> list[dict]:
    s_ts = int(start.timestamp())
    e_ts = int(end.timestamp())
    out = []
    for ev in _load_local():
        try:
            if ev["start_ts"] >= s_ts and ev["start_ts"] < e_ts:
                if calendar_name and ev.get("calendar", "").lower() != calendar_name.lower():
                    continue
                out.append(ev)
        except Exception:
            continue
    return out


# ── Parse / queries ─────────────────────────────────────────────────────────

def _month_start(value: dt.datetime) -> dt.datetime:
    return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _add_months(value: dt.datetime, months: int) -> dt.datetime:
    total = (value.year * 12 + (value.month - 1)) + months
    year = total // 12
    month = total % 12 + 1
    return value.replace(year=year, month=month, day=1)


def _parse_iso(value: str) -> dt.datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw.replace("Z", "+00:00")
    for fmt in (
        "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
        "%d.%m.%Y %H:%M", "%Y-%m-%d", "%d.%m.%Y",
    ):
        try:
            return dt.datetime.strptime(raw, fmt)
        except ValueError:
            continue
    try:
        return dt.datetime.fromisoformat(raw)
    except Exception:
        return None


def _normalize_query(query: str) -> dict:
    q = (query or "today").strip().lower()
    now = dt.datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    month_match = re.search(r"(\d+)\s*(ay|month|months)", q)
    if any(t in q for t in ("next month", "gelecek ay", "onumuzdeki ay", "önümüzdeki ay")):
        start = _add_months(_month_start(now), 1)
        end = _add_months(start, 1)
        return {"start": start, "end": end, "default_limit": 24,
                "kind": "next_month",
                "header": "Found {count} events for next month:",
                "empty": "No events on the calendar for next month."}
    if "this month" in q or "bu ay" in q:
        start = _month_start(now)
        end = _add_months(start, 1)
        return {"start": start, "end": end, "default_limit": 24,
                "kind": "this_month",
                "header": "Found {count} events for this month:",
                "empty": "No events on the calendar for this month."}
    if month_match:
        months = max(1, min(12, int(month_match.group(1))))
        return {"start": today_start, "end": _add_months(_month_start(now), months),
                "default_limit": min(60, max(12, months * 12)), "kind": "months",
                "header": f"Found {{count}} events for the next {months} months:",
                "empty": f"No events on the calendar for the next {months} months."}
    week_match = re.search(r"(\d+)\s*(hafta|week|weeks)", q)
    if week_match:
        weeks = max(1, min(12, int(week_match.group(1))))
        return {"start": today_start, "end": today_start + dt.timedelta(days=weeks * 7),
                "default_limit": min(60, max(8, weeks * 8)), "kind": "weeks",
                "header": f"Found {{count}} events for the next {weeks} weeks:",
                "empty": f"No events on the calendar for the next {weeks} weeks."}
    day_match = re.search(r"(\d+)\s*(g[uü]n|gun|day|days)", q)
    if day_match:
        days = max(1, min(365, int(day_match.group(1))))
        return {"start": today_start, "end": today_start + dt.timedelta(days=days),
                "default_limit": min(60, max(8, days * 2)), "kind": "days",
                "header": f"Found {{count}} events for the next {days} days:",
                "empty": f"No events on the calendar for the next {days} days."}
    if "tomorrow" in q or "yarin" in q or "yarın" in q:
        start = today_start + dt.timedelta(days=1)
        return {"start": start, "end": start + dt.timedelta(days=1),
                "default_limit": 6, "kind": "tomorrow",
                "header": "Found {count} events for tomorrow:",
                "empty": "No events on the calendar for tomorrow."}
    if any(t in q for t in ("week", "hafta", "7 gun")):
        return {"start": today_start, "end": today_start + dt.timedelta(days=7),
                "default_limit": 10, "kind": "week",
                "header": "Found {count} events for the next 7 days:",
                "empty": "No events on the calendar for the next 7 days."}
    if any(t in q for t in ("next", "siradaki", "sıradaki", "sonraki")):
        return {"start": now, "end": now + dt.timedelta(days=365),
                "default_limit": 1, "kind": "next", "header": "",
                "empty": "Could not find the next calendar event."}
    if any(t in q for t in ("agenda", "ajanda", "upcoming", "yaklasan", "yaklaşan")):
        return {"start": now, "end": now + dt.timedelta(days=30),
                "default_limit": 8, "kind": "agenda",
                "header": "Found {count} events in your upcoming agenda:",
                "empty": "No upcoming calendar events."}
    return {"start": today_start, "end": today_start + dt.timedelta(days=1),
            "default_limit": 6, "kind": "today",
            "header": "Found {count} events for today:",
            "empty": "No events on the calendar for today."}


def _day_label(when: dt.datetime, now: dt.datetime) -> str:
    today = now.date()
    target = when.date()
    if target == today:
        return "today"
    if target == today + dt.timedelta(days=1):
        return "tomorrow"
    return f"{when.day} {MONTHS[when.month]} {WEEKDAYS[when.weekday()]}"


def _format_event_line(event: dict, now: dt.datetime) -> str:
    start = dt.datetime.fromtimestamp(event["start_ts"])
    end = dt.datetime.fromtimestamp(event["end_ts"])
    prefix = _day_label(start, now)
    if event.get("all_day"):
        timing = f"{prefix} all day"
    else:
        timing = f"{prefix} {start.strftime('%H:%M')}-{end.strftime('%H:%M')}"
    pieces = [f"{timing} - {event['title']}"]
    if event.get("calendar"):
        pieces.append(f"[{event['calendar']}]")
    if event.get("location"):
        pieces.append(f"@ {event['location']}")
    return " ".join(pieces)


# ── Public API ──────────────────────────────────────────────────────────────

def get_calendar_events(query: str = "today", limit: int = 6) -> str:
    window = _normalize_query(query)
    limit = max(1, min(60, int(limit or window["default_limit"])))

    events = _outlook_events_in_range(window["start"], window["end"])
    events.extend(_local_events_in_range(window["start"], window["end"]))
    events.sort(key=lambda e: (e["start_ts"], e["title"].lower()))

    now = dt.datetime.now()
    if window["kind"] in {"next", "agenda"}:
        events = [e for e in events if e["end_ts"] >= int(now.timestamp())]

    if not events:
        return window["empty"]

    if window["kind"] == "next":
        return f"Next event: {_format_event_line(events[0], now)}."

    selected = events[:limit]
    header = str(window["header"]).format(count=len(selected))
    lines = [header]
    for ev in selected:
        lines.append(f"- {_format_event_line(ev, now)}")
    return "\n".join(lines)


def add_calendar_event(
    title: str,
    start_iso: str,
    end_iso: str = "",
    notes: str = "",
    location: str = "",
    calendar_name: str = "",
    all_day: bool = False,
) -> str:
    title = (title or "").strip()
    if not title:
        return "An event title is required to add to the calendar."
    start = _parse_iso(start_iso)
    if not start:
        return "A valid start date is required to add to the calendar."
    end = _parse_iso(end_iso) or start + dt.timedelta(minutes=DEFAULT_DURATION_MIN)

    result = _outlook_add(title, start, end, location, notes, all_day, calendar_name)
    if result is None:
        ev = {
            "id": uuid.uuid4().hex,
            "start_ts": int(start.timestamp()),
            "end_ts": int(end.timestamp()),
            "title": title,
            "calendar": calendar_name or "Local",
            "location": location or "",
            "notes": notes or "",
            "all_day": bool(all_day),
        }
        events = _load_local()
        events.append(ev)
        _save_local(events)
        result = ev

    now = dt.datetime.now()
    return f"Added to calendar: {_format_event_line(result, now)}."


def delete_calendar_event(
    title: str,
    start_iso: str = "",
    calendar_name: str = "",
    delete_all_matches: bool = False,
) -> str:
    title = (title or "").strip()
    if not title:
        return "An event title is required to delete from the calendar."

    start = _parse_iso(start_iso) if start_iso else None
    now = dt.datetime.now()

    ok, ev = _outlook_delete(title, start, calendar_name, delete_all_matches)
    if ok and ev:
        return f"Deleted from calendar: {_format_event_line(ev, now)}."

    # Local
    events = _load_local()
    deleted: list[dict] = []
    remaining = []
    for ev in events:
        if ev["title"].strip().lower() != title.lower():
            remaining.append(ev)
            continue
        if start is not None and abs(ev["start_ts"] - int(start.timestamp())) > 60:
            remaining.append(ev)
            continue
        if calendar_name and ev.get("calendar", "").lower() != calendar_name.lower():
            remaining.append(ev)
            continue
        deleted.append(ev)
        if not delete_all_matches:
            # Delete only one
            remaining.extend(events[events.index(ev) + 1:])
            break

    if not deleted:
        return f"Event titled '{title}' not found."

    _save_local(remaining)
    last = deleted[-1]
    return f"Deleted from calendar: {_format_event_line(last, now)}."
