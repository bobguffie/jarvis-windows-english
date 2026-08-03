"""
Browser control — Windows version.
Opens the default browser via os.startfile / webbrowser.
"""

from __future__ import annotations

import os
import re
import urllib.parse
import webbrowser

import requests

_VIDEO_ID_RE = re.compile(r'"videoId":"([A-Za-z0-9_-]{11})"')


def _open(url: str) -> None:
    try:
        os.startfile(url)
    except OSError:
        webbrowser.open(url, new=2)


def _find_first_youtube_video(query: str) -> str | None:
    encoded = urllib.parse.quote_plus(query)
    response = requests.get(
        f"https://www.youtube.com/results?search_query={encoded}",
        headers={"User-Agent": "JARVIS/1.0"},
        timeout=10,
    )
    response.raise_for_status()

    seen: set[str] = set()
    for video_id in _VIDEO_ID_RE.findall(response.text):
        if video_id not in seen:
            seen.add(video_id)
            return video_id
    return None


def browser_control(action: str, url: str = None, query: str = None) -> str:
    if action == "open_url":
        if not url:
            return "No URL specified."
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        _open(url)
        return f"Opened: {url}"

    elif action == "search":
        if not query:
            return "No search query specified."
        encoded = urllib.parse.quote(query)
        search_url = f"https://www.google.com/search?q={encoded}"
        _open(search_url)
        return f"Search opened for '{query}'."

    elif action in ("play_youtube", "youtube_play", "play_music"):
        if not query:
            return "No search query specified for YouTube."

        try:
            video_id = _find_first_youtube_video(query)
        except Exception as exc:
            encoded = urllib.parse.quote(query)
            fallback_url = f"https://www.youtube.com/results?search_query={encoded}"
            _open(fallback_url)
            return (
                f"Could not get first YouTube result ({exc}). "
                f"Search results opened: {query}"
            )

        if not video_id:
            encoded = urllib.parse.quote(query)
            fallback_url = f"https://www.youtube.com/results?search_query={encoded}"
            _open(fallback_url)
            return f"No direct video found on YouTube. Search results opened: {query}"

        watch_url = f"https://www.youtube.com/watch?v={video_id}&autoplay=1"
        _open(watch_url)
        return f"Playing on YouTube: {query}"

    return f"Unknown action: {action}"
