"""
Health — Windows version.

Provides health-related information and reminders.
Uses local memory for health data storage.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
HEALTH_FILE = BASE_DIR / "memory" / "health.json"

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def _load_health() -> dict:
    if not HEALTH_FILE.exists():
        return {}
    try:
        return json.loads(HEALTH_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_health(data: dict) -> None:
    HEALTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    HEALTH_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _day_label(when: dt.datetime, now: dt.datetime) -> str:
    today = now.date()
    target = when.date()
    if target == today:
        return "today"
    if target == today + dt.timedelta(days=1):
        return "tomorrow"
    return f"{when.day} {MONTHS[when.month]} {WEEKDAYS[when.weekday()]}"


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


def _parse_iso_ts(value: str) -> int:
    parsed = _parse_iso(value)
    if parsed:
        return int(parsed.timestamp())
    return 0


def _format_ts(ts: int) -> str:
    if ts <= 0:
        return "no date set"
    return dt.datetime.fromtimestamp(ts).strftime("%d %B %Y")


def _format_ts_short(ts: int) -> str:
    if ts <= 0:
        return ""
    return dt.datetime.fromtimestamp(ts).strftime("%d %B %Y")


def _format_ts_relative(ts: int, now: dt.datetime) -> str:
    if ts <= 0:
        return "no date set"
    when = dt.datetime.fromtimestamp(ts)
    return _day_label(when, now)


# ── Water tracking ──────────────────────────────────────────────────────────

def log_water(amount_ml: int = 250) -> str:
    if amount_ml <= 0:
        return "Water amount must be greater than 0."
    data = _load_health()
    today = dt.date.today().isoformat()
    water = data.setdefault("water", {})
    water[today] = water.get(today, 0) + amount_ml
    _save_health(data)
    total = water[today]
    return f"Logged {amount_ml} ml of water. Total today: {total} ml."


def get_water_summary() -> str:
    data = _load_health()
    water = data.get("water", {})
    if not water:
        return "No water intake data recorded yet."
    today = dt.date.today().isoformat()
    today_amount = water.get(today, 0)
    recent = sorted(water.items(), reverse=True)[:7]
    lines = [f"Water intake today: {today_amount} ml."]
    if len(recent) > 1:
        lines.append("Recent days:")
        for date_str, amount in recent:
            lines.append(f"  {date_str}: {amount} ml")
    return "\n".join(lines)


# ── Step tracking ───────────────────────────────────────────────────────────

def log_steps(count: int = 1000) -> str:
    if count <= 0:
        return "Step count must be greater than 0."
    data = _load_health()
    today = dt.date.today().isoformat()
    steps = data.setdefault("steps", {})
    steps[today] = steps.get(today, 0) + count
    _save_health(data)
    total = steps[today]
    return f"Logged {count} steps. Total today: {total} steps."


def get_step_summary() -> str:
    data = _load_health()
    steps = data.get("steps", {})
    if not steps:
        return "No step data recorded yet."
    today = dt.date.today().isoformat()
    today_amount = steps.get(today, 0)
    recent = sorted(steps.items(), reverse=True)[:7]
    lines = [f"Steps today: {today_amount}."]
    if len(recent) > 1:
        lines.append("Recent days:")
        for date_str, amount in recent:
            lines.append(f"  {date_str}: {amount} steps")
    return "\n".join(lines)


# ── Sleep tracking ──────────────────────────────────────────────────────────

def log_sleep(hours: float = 8.0) -> str:
    if hours <= 0 or hours > 24:
        return "Sleep duration must be between 0 and 24 hours."
    data = _load_health()
    today = dt.date.today().isoformat()
    sleep = data.setdefault("sleep", {})
    sleep[today] = sleep.get(today, 0) + hours
    _save_health(data)
    total = sleep[today]
    return f"Logged {hours} hours of sleep. Total today: {total} hours."


def get_sleep_summary() -> str:
    data = _load_health()
    sleep = data.get("sleep", {})
    if not sleep:
        return "No sleep data recorded yet."
    today = dt.date.today().isoformat()
    today_amount = sleep.get(today, 0)
    recent = sorted(sleep.items(), reverse=True)[:7]
    lines = [f"Sleep today: {today_amount} hours."]
    if len(recent) > 1:
        lines.append("Recent days:")
        for date_str, amount in recent:
            lines.append(f"  {date_str}: {amount} hours")
    return "\n".join(lines)


# ── Weight tracking ─────────────────────────────────────────────────────────

def log_weight(kg: float) -> str:
    if kg <= 0 or kg > 500:
        return "Weight must be between 0 and 500 kg."
    data = _load_health()
    today = dt.date.today().isoformat()
    weight = data.setdefault("weight", {})
    weight[today] = kg
    _save_health(data)
    return f"Weight logged: {kg} kg ({today})."


def get_weight_summary() -> str:
    data = _load_health()
    weight = data.get("weight", {})
    if not weight:
        return "No weight data recorded yet."
    recent = sorted(weight.items(), reverse=True)[:7]
    lines = ["Weight records:"]
    for date_str, kg in recent:
        lines.append(f"  {date_str}: {kg} kg")
    return "\n".join(lines)


# ── Medication reminders ────────────────────────────────────────────────────

def add_medication(name: str, dosage: str = "", schedule: str = "", notes: str = "") -> str:
    if not name or not name.strip():
        return "Medication name is required."
    data = _load_health()
    meds = data.setdefault("medications", [])
    entry = {
        "name": name.strip(),
        "dosage": dosage.strip(),
        "schedule": schedule.strip(),
        "notes": notes.strip(),
        "created_at": dt.datetime.now().isoformat(),
    }
    meds.append(entry)
    _save_health(data)
    return f"Medication added: {name.strip()}."


def get_medications() -> str:
    data = _load_health()
    meds = data.get("medications", [])
    if not meds:
        return "No medications recorded."
    lines = ["Medications:"]
    for med in meds:
        parts = [med.get("name", "Unnamed")]
        if med.get("dosage"):
            parts.append(f"({med['dosage']})")
        if med.get("schedule"):
            parts.append(f"- {med['schedule']}")
        lines.append("  " + " ".join(parts))
    return "\n".join(lines)


# ── General health summary ──────────────────────────────────────────────────

def get_health_summary() -> str:
    data = _load_health()
    parts = []

    water = data.get("water", {})
    if water:
        today = dt.date.today().isoformat()
        parts.append(f"Water: {water.get(today, 0)} ml today.")

    steps = data.get("steps", {})
    if steps:
        today = dt.date.today().isoformat()
        parts.append(f"Steps: {steps.get(today, 0)} today.")

    sleep = data.get("sleep", {})
    if sleep:
        today = dt.date.today().isoformat()
        parts.append(f"Sleep: {sleep.get(today, 0)} hours today.")

    weight = data.get("weight", {})
    if weight:
        recent = sorted(weight.items(), reverse=True)
        latest_date, latest_kg = recent[0]
        parts.append(f"Weight: {latest_kg} kg ({latest_date}).")

    meds = data.get("medications", [])
    if meds:
        parts.append(f"Medications: {len(meds)} recorded.")

    if not parts:
        return "No health data recorded yet. Log water, steps, sleep, weight, or medications."

    return "Health summary:\n" + "\n".join(parts)


def get_health_card_lines() -> list[str]:
    """Return a short list of health summary lines for the UI health card."""
    data = _load_health()
    lines = []

    water = data.get("water", {})
    if water:
        today = dt.date.today().isoformat()
        lines.append(f"Water: {water.get(today, 0)} ml today")

    steps = data.get("steps", {})
    if steps:
        today = dt.date.today().isoformat()
        lines.append(f"Steps: {steps.get(today, 0)} today")

    sleep = data.get("sleep", {})
    if sleep:
        today = dt.date.today().isoformat()
        lines.append(f"Sleep: {sleep.get(today, 0)} hrs today")

    weight = data.get("weight", {})
    if weight:
        recent = sorted(weight.items(), reverse=True)
        latest_date, latest_kg = recent[0]
        lines.append(f"Weight: {latest_kg} kg")

    meds = data.get("medications", [])
    if meds:
        lines.append(f"Medications: {len(meds)}")

    if not lines:
        lines.append("No health data yet")

    return lines
