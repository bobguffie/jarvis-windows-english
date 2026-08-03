"""
Workspace — Dynamic workspace card for JARVIS.
Provides a hot-swappable dashboard section that displays either:
  - Currently playing media (Windows media process detection)
  - Shared network to-do list (local or network path, auto-detected)

Media tab auto-switches back to "todo" when all players are idle/stopped for >10s.
"""

from __future__ import annotations

import os
import time
import subprocess
from pathlib import Path
from services.smarthome import SmartHomeClient
from actions.smarthome import DEVICE_MAP


BASE_DIR = Path(__file__).resolve().parent.parent

# Smart todo path: use the network share if it exists, otherwise fall back to
# a local file inside the repository so it works out of the box on any machine.
_NETWORK_TODO = Path("//MEDION/Jarvis-shared/todo.txt")
_LOCAL_TODO   = BASE_DIR / "memory" / "todo.txt"

TODO_PATH = _NETWORK_TODO if _NETWORK_TODO.exists() else _LOCAL_TODO

# ── Known media player processes (Windows) ────────────────────────────────
KNOWN_MEDIA_PROCESSES = [
    "spotify.exe",
    "vlc.exe",
    "wmplayer.exe",       # Windows Media Player
    "chrome.exe",         # YouTube etc.
    "msedge.exe",
    "firefox.exe",
    "mpc-hc.exe",
    "potplayer.exe",
    "itunes.exe",
    "foobar2000.exe",
    "winamp.exe",
    "music.ui.exe",       # Microsoft Groove Music
]

# ── Idle tracking ────────────────────────────────────────────────────────────
_media_last_active_time: float | None = None  # last time we saw a Playing player
_media_last_stopped_lines: list[str] = ["No media player detected."]


def _get_running_media_players() -> list[str]:
    """Return a list of running media player process names (lowercase)."""
    try:
        result = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=5,
        )
        running = []
        for line in result.stdout.splitlines():
            parts = line.strip().strip('"').split('","')
            if not parts:
                continue
            proc_name = parts[0].strip('"').strip().lower()
            if proc_name in KNOWN_MEDIA_PROCESSES:
                running.append(proc_name)
        return running
    except Exception:
        return []


def _get_player_metadata(player_name: str) -> dict:
    """
    Fetch metadata for a specific player process.
    On Windows v2.1, we detect running media player processes via tasklist.
    Full metadata (title/artist) extraction would require Windows Media
    Session API / SMTC integration.
    """
    meta = {
        "name": player_name,
        "title": "",
        "artist": "",
        "status": "running",
    }
    return meta


def _player_display_name(player_id: str) -> str:
    """Convert a process name to a friendly display name."""
    base = os.path.splitext(player_id)[0]
    return base.replace("-", " ").replace("_", " ").title()


def get_now_playing() -> tuple[list[str], bool]:
    """Return (lines, is_active) describing the currently playing media.

    Scans running media player processes on Windows.
    `is_active` is True only if a media player process was found running.

    Updates internal idle timer used by `check_media_idle_timeout()`.
    """
    global _media_last_active_time, _media_last_stopped_lines

    try:
        players = _get_running_media_players()
        if not players:
            _media_last_stopped_lines = ["No media player detected."]
            return (_media_last_stopped_lines, False)

        # Fetch metadata for every player
        all_players = [_get_player_metadata(pid) for pid in players]

        # Prefer Spotify/VLC/MPC over browsers if multiple are running
        priority_order = [
            "spotify.exe", "vlc.exe", "mpc-hc.exe", "potplayer.exe",
            "wmplayer.exe", "itunes.exe", "foobar2000.exe",
        ]
        chosen = None
        for prefs in priority_order:
            for p in all_players:
                if p["name"].lower() == prefs:
                    chosen = p
                    break
            if chosen:
                break
        if chosen is None:
            chosen = all_players[0]

        source = _player_display_name(chosen["name"])
        title = chosen.get("title", "")
        artist = chosen.get("artist", "")

        lines = [f"Source: {source}"]
        if title:
            display_title = title if len(title) <= 40 else title[:37] + "..."
            lines.append(f"Playing: {display_title}")
        if artist:
            display_artist = artist if len(artist) <= 35 else artist[:32] + "..."
            lines.append(f"Artist: {display_artist}")
        lines.append("Status: ▶ Running")

        # Update active timer
        _media_last_active_time = time.time()

        _media_last_stopped_lines = lines[:4]
        return (_media_last_stopped_lines, True)

    except FileNotFoundError:
        _media_last_stopped_lines = ["tasklist not available."]
        return (_media_last_stopped_lines, False)
    except subprocess.TimeoutExpired:
        return (["Media query timed out."], False)
    except Exception as e:
        return ([f"Media error: {str(e)[:40]}"], False)


def check_media_idle_timeout(idle_threshold: float = 10.0) -> bool:
    """Return True if media tab has been idle for longer than idle_threshold seconds.

    Scans all currently running media players. If ANY known media process is
    running, the idle timer is reset. Returns True only if no known players are
    running AND no media was seen for longer than idle_threshold.
    """
    # First, scan current players - any running resets the timer
    try:
        players = _get_running_media_players()
        if players:
            global _media_last_active_time
            _media_last_active_time = time.time()
            return False
    except Exception:
        pass

    # If _media_last_active_time never set, not idle
    if _media_last_active_time is None:
        return False

    # No media players running - check elapsed time since last seen
    return time.time() - _media_last_active_time > idle_threshold


def refresh_workspace() -> str:
    """Force-refresh the workspace data by resetting the idle timer and re-scanning.

    Returns a confirmation message. Call this via voice action or UI button
    to immediately update the workspace card contents.
    """
    global _media_last_active_time
    # Brief re-scan to update cached data
    get_now_playing()
    _media_last_active_time = time.time()
    return "Workspace data refreshed."


# ── Shared To-Do List ────────────────────────────────────────────────────────

def read_todo_list() -> list[str]:
    """Read the first few lines from the shared network to-do list.

    Creates the file with an empty placeholder if it does not exist.
    Returns a list of up to 4 todo items (or a placeholder).
    """
    try:
        if not TODO_PATH.exists():
            TODO_PATH.parent.mkdir(parents=True, exist_ok=True)
            TODO_PATH.write_text("Shared to-do list — edit this file\n", encoding="utf-8")
            return ["Empty — add items to todo.txt"]

        lines = TODO_PATH.read_text(encoding="utf-8").splitlines()
        items = [l.strip() for l in lines if l.strip()]
        if not items:
            return ["No items in to-do list."]
        return items[:4]

    except PermissionError:
        return ["Todo file not accessible."]
    except OSError as e:
        return [f"Todo error: {str(e)[:40]}"]


# ── Todo read/write operations ───────────────────────────────────────────────

def get_todo_content() -> str:
    """Reads and returns the complete text lines of the user's workspace to-do list.

    Returns:
        The full file content as a string, one line per item.
    """
    try:
        if not TODO_PATH.exists():
            TODO_PATH.parent.mkdir(parents=True, exist_ok=True)
            TODO_PATH.write_text("Shared to-do list — edit this file\n", encoding="utf-8")
            return "To-do list is empty."

        lines = TODO_PATH.read_text(encoding="utf-8").splitlines()
        items = [l.strip() for l in lines if l.strip()]
        if not items:
            return "To-do list is empty."
        return "\n".join(items)
    except PermissionError:
        return "Todo file not accessible."
    except OSError as e:
        return f"Todo error: {str(e)[:60]}"


def add_todo_item(task: str) -> str:
    """Appends a brand new task or bullet point line to the active to-do list file.

    Args:
        task: The task description to add.

    Returns:
        A confirmation message.
    """
    if not task or not task.strip():
        return "Task cannot be empty."
    try:
        # Ensure parent directory exists
        TODO_PATH.parent.mkdir(parents=True, exist_ok=True)
        # Append the task with a bullet prefix
        with open(str(TODO_PATH), "a", encoding="utf-8") as f:
            f.write(f"• {task.strip()}\n")
        return f"Task added: {task.strip()}"
    except PermissionError:
        return "Todo file not accessible."
    except OSError as e:
        return f"Todo error: {str(e)[:60]}"


def remove_todo_item(task_keyword: str) -> str:
    """Removes a completed task line from the to-do list file by searching for a keyword.

    Args:
        task_keyword: A keyword or phrase to match against existing todo items.
                      Lines containing this keyword (case-insensitive) will be removed.

    Returns:
        A confirmation message listing what was removed.
    """
    if not task_keyword or not task_keyword.strip():
        return "Keyword cannot be empty."
    try:
        if not TODO_PATH.exists():
            return "To-do list is empty — nothing to remove."

        lines = TODO_PATH.read_text(encoding="utf-8").splitlines()
        keyword_lower = task_keyword.strip().lower()
        kept = []
        removed = []

        for line in lines:
            if keyword_lower in line.strip().lower():
                removed.append(line.strip())
            else:
                kept.append(line)

        if not removed:
            return f"No items matching '{task_keyword}' found."

        # Overwrite the file with remaining lines
        TODO_PATH.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")

        if len(removed) == 1:
            return f"Removed: {removed[0]}"
        return f"Removed {len(removed)} items matching '{task_keyword}'."

    except PermissionError:
        return "Todo file not accessible."
    except OSError as e:
        return f"Todo error: {str(e)[:60]}"


# ── Smart Home client ─────────────────────────────────────────────────────────
ha_client = SmartHomeClient()


# ── Tab switching helper ─────────────────────────────────────────────────────

def get_workspace_lines(tab: str) -> list[str]:
    """Return the appropriate lines for the given workspace tab.

    Args:
        tab: "media", "todo", or "smarthome"

    Returns:
        A list of display lines (strings).
    """
    norm = tab.strip().lower()
    if norm == "media":
        lines, _ = get_now_playing()
        return lines
    elif norm == "smarthome":
        lines = ["POWER GRID ACTIVE"]

        # Dynamically query every unique entity from DEVICE_MAP
        seen_ids = set()
        for keyword, (entity_id, domain) in DEVICE_MAP.items():
            if entity_id in seen_ids:
                continue
            seen_ids.add(entity_id)
            state_data = ha_client.get_entity_state(entity_id)
            state_str = state_data['state'].upper() if state_data else 'OFFLINE'
            lines.append(f"• {keyword.title()}: {state_str}")

        return lines[:5]
    # Default to todo
    return read_todo_list()