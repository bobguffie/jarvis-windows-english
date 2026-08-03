"""
Media playback — Windows version.
- Spotify Desktop: opens via spotify: URI scheme; optionally plays with pyautogui.
- YouTube: plays in browser.
- Apple Music: not available on Windows; opens web page.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
import urllib.parse

from actions.browser import browser_control


def _spotify_installed() -> bool:
    # Registry / PATH or AppData check
    for env_var in ("APPDATA", "LOCALAPPDATA"):
        base = os.environ.get(env_var, "")
        if base and os.path.exists(os.path.join(base, "Spotify", "Spotify.exe")):
            return True
    return shutil.which("spotify") is not None


def _play_youtube(query: str) -> str:
    return browser_control("play_youtube", query=query)


def _press_keys_via_pyautogui(keys: list[str]) -> tuple[bool, str]:
    try:
        import pyautogui  # type: ignore
    except Exception as exc:
        return False, f"pyautogui not found: {exc}"
    try:
        for key in keys:
            pyautogui.press(key)
            time.sleep(0.18)
        return True, "ok"
    except Exception as exc:
        return False, f"pyautogui error: {exc}"


def _play_spotify(query: str, autoplay: bool = True) -> str:
    if not _spotify_installed():
        return "Spotify does not appear to be installed."

    encoded_query = urllib.parse.quote(query.strip())
    search_uri = f"spotify:search:{encoded_query}"

    try:
        os.startfile(search_uri)
    except OSError as exc:
        return f"Could not open Spotify: {exc}"

    if not autoplay:
        return f"Spotify search opened for '{query}'."

    time.sleep(2.0)
    ok, detail = _press_keys_via_pyautogui(["tab", "down", "enter", "space"])
    if ok:
        return f"Playing on Spotify: {query}"
    return (
        f"Spotify search opened but auto-play could not complete: {detail}. "
        "pyautogui must be installed and Spotify must be in the foreground."
    )


def _play_apple_music_web(query: str) -> str:
    encoded = urllib.parse.quote(query.strip())
    url = f"https://music.apple.com/search?term={encoded}"
    return browser_control("open_url", url=url)


def play_media(query: str, provider: str = "auto", autoplay: bool = True) -> str:
    if not query or not query.strip():
        return "No content specified to play."

    normalized_provider = (provider or "auto").strip().lower()
    if normalized_provider in {"yt", "youtube music"}:
        normalized_provider = "youtube"
    elif normalized_provider in {"apple music", "music", "apple_music"}:
        normalized_provider = "apple_music"

    if normalized_provider == "spotify":
        return _play_spotify(query, autoplay=autoplay)
    if normalized_provider == "apple_music":
        return _play_apple_music_web(query)
    if normalized_provider == "youtube":
        return _play_youtube(query)

    # auto
    if _spotify_installed():
        result = _play_spotify(query, autoplay=autoplay)
        if "does not appear" not in result and "Could not open" not in result:
            return result
    return _play_youtube(query)
