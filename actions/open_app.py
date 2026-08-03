"""
Open applications — Windows version.
Works via Windows 'start' command, AppsFolder, and PATH.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import winreg


APP_ALIASES = {
    "edge":         "msedge",
    "chrome":       "chrome",
    "firefox":      "firefox",
    "brave":        "brave",
    "opera":        "opera",
    "safari":       "msedge",  # macOS analog
    "terminal":     "wt",       # Windows Terminal
    "powershell":   "powershell",
    "cmd":          "cmd",
    "command prompt": "cmd",
    "explorer":     "explorer",
    "finder":       "explorer",
    "file explorer": "explorer",
    "spotify":      "spotify",
    "vscode":       "code",
    "vs code":      "code",
    "code":         "code",
    "visual studio code": "code",
    "xcode":        "code",
    "notion":       "notion",
    "slack":        "slack",
    "discord":      "discord",
    "whatsapp":     "whatsapp",
    "telegram":     "telegram",
    "zoom":         "zoom",
    "mail":         "outlook",
    "outlook":      "outlook",
    "calendar":     "outlookcal:",
    "notes":        "notepad",
    "notepad":      "notepad",
    "music":        "ms-windows-store://pdp/?ProductId=9wzdncrfj3pt",
    "media player": "wmplayer",
    "photos":       "ms-photos:",
    "maps":         "bingmaps:",
    "calculator":   "calc",
    "settings":     "ms-settings:",
    "system settings": "ms-settings:",
    "task manager": "taskmgr",
    "control panel": "control",
    "preview":      "mspaint",
    "textedit":     "notepad",
    "figma":        "figma",
    "postman":      "postman",
    "docker":       "Docker Desktop",
}


# Local installation extensions — also recognizes URI schemes for start command
_URI_PREFIXES = (
    "ms-settings:", "ms-photos:", "bingmaps:", "outlookcal:",
    "ms-windows-store:", "shell:", "spotify:",
)


def _start_uri(uri: str) -> bool:
    try:
        os.startfile(uri)
        return True
    except OSError:
        return False


def _start_command(name: str) -> bool:
    """Attempts to open an app by name using the Windows 'start' command."""
    try:
        result = subprocess.run(
            ["cmd", "/c", "start", "", "/B", name],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def _registry_app_paths(name: str) -> str | None:
    """Search for exe under HKLM/HKCU App Paths."""
    candidates = [name, name + ".exe"]
    roots = (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
    )
    for root, sub in roots:
        for cand in candidates:
            try:
                with winreg.OpenKey(root, sub + "\\" + cand) as key:
                    val, _ = winreg.QueryValueEx(key, None)
                    if val and os.path.exists(val):
                        return val
            except OSError:
                continue
    return None


def open_app(app_name: str) -> str:
    if not app_name:
        return "No application name specified."

    normalized = app_name.lower().strip()
    resolved = APP_ALIASES.get(normalized, app_name)

    # 1. URI scheme (ms-settings, spotify:, etc.)
    if any(resolved.startswith(p) for p in _URI_PREFIXES):
        if _start_uri(resolved):
            return f"{app_name} opened."

    # 2. If exe is in PATH, open directly
    exe = shutil.which(resolved) or shutil.which(resolved + ".exe")
    if exe:
        try:
            subprocess.Popen([exe], close_fds=True)
            return f"{resolved} opened."
        except Exception:
            pass

    # 3. Registry App Paths
    reg_exe = _registry_app_paths(resolved)
    if reg_exe:
        try:
            subprocess.Popen([reg_exe], close_fds=True)
            return f"{resolved} opened."
        except Exception:
            pass

    # 4. start "" command (Start Menu name matching)
    if _start_command(resolved):
        return f"{resolved} opened."

    # 5. os.startfile fallback (file/url)
    try:
        os.startfile(resolved)
        return f"{app_name} opened."
    except OSError:
        pass

    return f"'{app_name}' not found or could not be opened."
