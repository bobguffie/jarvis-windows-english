"""
LM Studio (local) runtime — uses an OpenAI-compatible local model instead of Gemini Live.

Flow:
  Microphone -> SpeechRecognition (Whisper or Google) -> text
        -> LM Studio /v1/chat/completions (tool calling)
        -> Tool results feedback -> final text
        -> Windows SAPI TTS (actions.tts.speak_text)

JarvisLocal class interface is compatible with JarvisLive: uses the same
ui.on_text_command, ui.on_pause_toggle etc. callbacks, started with
asyncio.run(jarvis.run()).
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import threading
import time
import traceback
from typing import Any, Callable

import requests

from app_config import get_app_config_value
from memory.memory_manager import (
    load_memory,
    update_memory,
    delete_memory,
    format_memory_for_prompt,
)
from actions.open_app import open_app
from actions.sys_info import sys_info
from actions.calendar import (
    get_calendar_events,
    add_calendar_event,
    delete_calendar_event,
)
from actions.reminders import get_reminders, add_reminder
from actions.browser import browser_control
from actions.shell import shell_run
from actions.whatsapp import send_whatsapp_message, save_whatsapp_contact
from actions.media import play_media
from actions.weather import get_weather_summary
from actions.screen_vision import analyze_screen
from actions.youtube_stats import get_youtube_channel_report
from actions.tts import speak_text


# ── Tool registry ────────────────────────────────────────────────────────────

def _save_memory_tool(category: str, key: str, value: str) -> str:
    if not key or not value:
        return "Missing parameter."
    update_memory({category or "notes": {key: {"value": value}}})
    return "ok"


TOOL_HANDLERS: dict[str, Callable[..., Any]] = {
    "open_app": lambda app_name="": open_app(app_name),
    "sys_info": lambda query="all": sys_info(query),
    "get_weather": lambda location=None: get_weather_summary(location or None),
    "get_calendar_events": lambda query="today", limit=6: get_calendar_events(query, int(limit or 6)),
    "add_calendar_event": lambda title="", start_iso="", end_iso="", notes="", location="", calendar_name="", all_day=False: add_calendar_event(title, start_iso, end_iso, notes, location, calendar_name, bool(all_day)),
    "delete_calendar_event": lambda title="", start_iso="", calendar_name="", delete_all_matches=False: delete_calendar_event(title, start_iso, calendar_name, bool(delete_all_matches)),
    "get_reminders": lambda query="upcoming", limit=8, list_name="": get_reminders(query, int(limit or 8), list_name),
    "add_reminder": lambda title="", due_iso="", notes="", list_name="", priority="", all_day=False: add_reminder(title, due_iso, notes, list_name, priority, bool(all_day)),
    "browser_control": lambda action="open_url", url=None, query=None: browser_control(action, url, query),
    "shell_run": lambda command="": shell_run(command),
    "play_media": lambda query="", provider="auto", autoplay=True: play_media(query, provider, bool(autoplay)),
    "get_youtube_channel_report": lambda query="overview", handle="", video_limit=6: get_youtube_channel_report(query, handle, int(video_limit or 6)),
    "analyze_screen": lambda query="What's on the screen?", target="active_window": analyze_screen(query, target),
    "save_memory": lambda category="notes", key="", value="": _save_memory_tool(category, key, value),
    "delete_memory": lambda category="", key="", match_text="": delete_memory(category, key, match_text),
    "send_whatsapp_message": lambda message="", phone_number="", recipient_name="", send_now=False, app_target="auto": send_whatsapp_message(message, phone_number, recipient_name, bool(send_now), app_target),
    "save_whatsapp_contact": lambda display_name="", phone_number="", aliases="": save_whatsapp_contact(display_name, phone_number, aliases),
}


def _gemini_tool_to_openai(decl: dict) -> dict:
    """Converts a Gemini tool declaration to OpenAI tool spec."""
    name = decl["name"]
    description = decl.get("description", "")
    params = decl.get("parameters", {"type": "OBJECT", "properties": {}})

    def _to_openai_schema(node: dict) -> dict:
        if not isinstance(node, dict):
            return node
        out = {}
        for k, v in node.items():
            if k == "type" and isinstance(v, str):
                out["type"] = v.lower() if v.upper() in {"OBJECT", "STRING", "NUMBER", "BOOLEAN", "ARRAY", "INTEGER"} else v
            elif k == "properties" and isinstance(v, dict):
                out["properties"] = {pk: _to_openai_schema(pv) for pk, pv in v.items()}
            elif k == "items" and isinstance(v, dict):
                out["items"] = _to_openai_schema(v)
            else:
                out[k] = v
        return out

    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": _to_openai_schema(params),
        },
    }


# ── STT ──────────────────────────────────────────────────────────────────────

class _SttEngine:
    def __init__(self, language: str = "en-GB", engine: str = "whisper"):
        self.language = language
        self.engine = (engine or "whisper").lower()
        self._sr = None
        self._mic = None
        self._recognizer = None
        self._init_ok = False
        self._init_error = ""
        self._init()

    def _init(self):
        try:
            import speech_recognition as sr  # type: ignore
        except Exception as exc:
            self._init_error = f"SpeechRecognition not installed: {exc}"
            return
        self._sr = sr
        try:
            self._recognizer = sr.Recognizer()
            self._recognizer.pause_threshold = 0.9
            self._recognizer.dynamic_energy_threshold = True
            self._mic = sr.Microphone()
            with self._mic as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=0.6)
            self._init_ok = True
        except Exception as exc:
            self._init_error = f"Microphone could not be initialized: {exc}"

    def listen_once(self, phrase_time_limit: float = 12.0, timeout: float = 6.0) -> tuple[bool, str]:
        if not self._init_ok:
            return False, self._init_error or "STT not ready."
        sr = self._sr
        try:
            with self._mic as source:
                audio = self._recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
        except sr.WaitTimeoutError:
            return False, "timeout"
        except Exception as exc:
            return False, f"Listening error: {exc}"

        try:
            if self.engine == "whisper":
                lang = (self.language or "en").split("-")[0].lower()
                text = self._recognizer.recognize_whisper(audio, language=lang)
            else:
                text = self._recognizer.recognize_google(audio, language=self.language)
            return True, (text or "").strip()
        except sr.UnknownValueError:
            return False, ""
        except Exception as exc:
            # Fall back to Google if Whisper is not installed
            if self.engine == "whisper":
                try:
                    text = self._recognizer.recognize_google(audio, language=self.language)
                    return True, (text or "").strip()
                except Exception as exc2:
                    return False, f"Transcription error: {exc2}"
            return False, f"Transcription error: {exc}"


# ── JarvisLocal ──────────────────────────────────────────────────────────────

class JarvisLocal:
    def __init__(self, ui, tool_declarations: list[dict], system_prompt_loader):
        self.ui = ui
        self._loop: asyncio.AbstractEventLoop | None = None
        self._paused = False
        self._is_speaking = False
        self._speaking_lock = threading.Lock()
        self._tool_declarations = tool_declarations
        self._openai_tools = [_gemini_tool_to_openai(d) for d in tool_declarations]
        self._load_system_prompt = system_prompt_loader
        self._pending_text_queue: asyncio.Queue | None = None
        self._messages: list[dict] = []
        self._max_history = 24

        self.ui.on_text_command = self._on_text_command
        self.ui.on_pause_toggle = self._on_pause_toggle
        self.ui.on_effects_state_change = lambda _e: None

    # ── UI callbacks ─────────────────────────────────────────────────────────
    def _on_pause_toggle(self, paused: bool):
        self._paused = paused

    def _on_text_command(self, text: str):
        if self._paused or not text.strip():
            return
        self.ui.write_log(f"You: {text}")
        if self._loop and self._pending_text_queue is not None:
            asyncio.run_coroutine_threadsafe(self._pending_text_queue.put(text.strip()), self._loop)

    def set_speaking(self, value: bool):
        with self._speaking_lock:
            self._is_speaking = value
        self.ui.set_state("SPEAKING" if value else "LISTENING")

    # ── System prompt ────────────────────────────────────────────────────────
    def _build_system_message(self) -> str:
        memory = load_memory()
        mem_str = format_memory_for_prompt(memory)
        sys_p = self._load_system_prompt()
        now = dt.datetime.now()
        time_ctx = f"[CURRENT TIME]\n{now.strftime('%A, %d %B %Y - %H:%M')}\n\n"
        parts = [time_ctx]
        if mem_str:
            parts.append(mem_str + "\n\n")
        parts.append(sys_p)
        parts.append(
            "\n\nNote: You are running in local mode (LM Studio). Give the user short, "
            "clear responses in English. Make tool calls when needed."
        )
        return "\n".join(parts)

    def _ensure_system_message(self):
        sys_msg = {"role": "system", "content": self._build_system_message()}
        if self._messages and self._messages[0].get("role") == "system":
            self._messages[0] = sys_msg
        else:
            self._messages.insert(0, sys_msg)

    def _trim_history(self):
        if len(self._messages) <= self._max_history + 1:
            return
        head = self._messages[:1] if self._messages and self._messages[0].get("role") == "system" else []
        tail = self._messages[-self._max_history:]
        self._messages = head + tail

    # ── LM Studio call ───────────────────────────────────────────────────────
    def _chat_completion(self) -> dict:
        base = str(get_app_config_value("lmstudio_base_url", "http://127.0.0.1:1234/v1") or "").rstrip("/")
        model = str(get_app_config_value("lmstudio_model", "local-model") or "local-model")
        api_key = str(get_app_config_value("lmstudio_api_key", "lm-studio") or "lm-studio")

        payload = {
            "model": model,
            "messages": self._messages,
            "temperature": 0.4,
            "stream": False,
        }
        if self._openai_tools:
            payload["tools"] = self._openai_tools
            payload["tool_choice"] = "auto"

        resp = requests.post(
            f"{base}/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            data=json.dumps(payload),
            timeout=180,
        )
        if not resp.ok:
            raise RuntimeError(f"LM Studio {resp.status_code}: {resp.text[:300]}")
        return resp.json()

    def _execute_tool(self, name: str, raw_args: str) -> str:
        try:
            args = json.loads(raw_args) if raw_args else {}
        except Exception:
            args = {}
        handler = TOOL_HANDLERS.get(name)
        if handler is None:
            return f"Unknown tool: {name}"
        try:
            self.ui.set_state("THINKING")
            result = handler(**args)
            return str(result if result is not None else "ok")
        except Exception as exc:
            traceback.print_exc()
            return f"Error: {exc}"

    async def _handle_turn(self, user_text: str):
        self._ensure_system_message()
        self._messages.append({"role": "user", "content": user_text})
        self.ui.set_state("THINKING")

        for _ in range(6):  # max tool-call chain
            loop = asyncio.get_event_loop()
            try:
                data = await loop.run_in_executor(None, self._chat_completion)
            except Exception as exc:
                self.ui.write_log(f"ERR: LM Studio did not respond - {exc}")
                self.ui.set_state("ERROR")
                # Remove user message so they can retry
                self._messages.pop()
                return

            choice = (data.get("choices") or [{}])[0]
            msg = choice.get("message", {}) or {}
            tool_calls = msg.get("tool_calls") or []
            content = (msg.get("content") or "").strip()

            if tool_calls:
                # Add assistant message (with tool_calls)
                self._messages.append({
                    "role": "assistant",
                    "content": content or None,
                    "tool_calls": tool_calls,
                })
                for call in tool_calls:
                    fn = call.get("function", {}) or {}
                    name = fn.get("name", "")
                    raw_args = fn.get("arguments", "") or ""
                    self.ui.write_debug(f"tool -> {name} {raw_args[:120]}", level="INFO")
                    result = await loop.run_in_executor(None, self._execute_tool, name, raw_args)
                    self._messages.append({
                        "role": "tool",
                        "tool_call_id": call.get("id", ""),
                        "name": name,
                        "content": result,
                    })
                # Call model again with tool results
                continue

            # No tool calls — final response
            if content:
                self._messages.append({"role": "assistant", "content": content})
                self.ui.write_log(f"JARVIS: {content}")
                self._speak_blocking(content)
            else:
                self.ui.write_log("JARVIS: (empty response)")
            self._trim_history()
            self.ui.set_state("LISTENING")
            return

        self.ui.write_log("ERR: Tool call chain too long, stopped.")
        self.ui.set_state("ERROR")

    def _speak_blocking(self, text: str):
        if self.ui.muted:
            return
        self.set_speaking(True)
        done = threading.Event()

        def _on_done():
            self.set_speaking(False)
            done.set()

        try:
            speak_text(text, on_done=_on_done, blocking=False)
            done.wait(timeout=60)
        except Exception:
            self.set_speaking(False)

    # ── STT listening loop ───────────────────────────────────────────────────
    def _stt_loop_thread(self, stt: _SttEngine, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop, stop_event: threading.Event):
        while not stop_event.is_set():
            if self._paused or self.ui.muted:
                time.sleep(0.3)
                continue
            with self._speaking_lock:
                if self._is_speaking:
                    time.sleep(0.2)
                    continue
            ok, text = stt.listen_once(phrase_time_limit=14.0, timeout=5.0)
            if not ok:
                if text and text != "timeout":
                    self.ui.write_debug(f"STT: {text}", level="WARN")
                continue
            if not text:
                continue
            self.ui.write_log(f"You: {text}")
            asyncio.run_coroutine_threadsafe(queue.put(text), loop)

    # ── Main loop ────────────────────────────────────────────────────────────
    async def run(self):
        self._loop = asyncio.get_event_loop()
        self._pending_text_queue = asyncio.Queue()
        self.ui.write_log("SYS: Local mode (LM Studio) started.")
        self.ui.set_state("LISTENING")

        # Start STT in background
        language = str(get_app_config_value("stt_language", "en-GB") or "en-GB")
        engine = str(get_app_config_value("stt_engine", "whisper") or "whisper")
        stt = _SttEngine(language=language, engine=engine)
        if not stt._init_ok:
            self.ui.write_log(f"ERR: STT not started — {stt._init_error}. You can still use the text input box.")

        stop_event = threading.Event()
        if stt._init_ok:
            threading.Thread(
                target=self._stt_loop_thread,
                args=(stt, self._pending_text_queue, self._loop, stop_event),
                daemon=True,
            ).start()

        try:
            while True:
                if self._paused:
                    await asyncio.sleep(0.5)
                    continue
                try:
                    text = await asyncio.wait_for(self._pending_text_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                if not text:
                    continue
                try:
                    await self._handle_turn(text)
                except Exception as exc:
                    self.ui.write_log(f"ERR: Local mode error — {exc}")
                    self.ui.set_state("ERROR")
                    traceback.print_exc()
        finally:
            stop_event.set()


# ── Connectivity test ────────────────────────────────────────────────────────

def ping_lmstudio(base_url: str | None = None, timeout: float = 5.0) -> tuple[bool, str]:
    """Tests connectivity to the LM Studio server."""
    base = (base_url or str(get_app_config_value("lmstudio_base_url", "http://127.0.0.1:1234/v1") or "")).rstrip("/")
    try:
        resp = requests.get(f"{base}/models", timeout=timeout)
        if resp.ok:
            data = resp.json()
            models = [m.get("id", "?") for m in (data.get("data") or [])]
            return True, ", ".join(models) if models else "OK"
        return False, f"HTTP {resp.status_code}"
    except Exception as exc:
        return False, str(exc)
