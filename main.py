#!/usr/bin/env python3
"""
JARVIS Windows v2.1 — Real-time voice assistant core
https://github.com/bobguffie/jarvis-windows-english
Adapted workflow for Windows environment
"""

import asyncio
import datetime
import threading
import traceback
import os
import re
import subprocess
import sys
from pathlib import Path

import pyaudio  # type: ignore[reportMissingModuleSource]
from google import genai  # type: ignore[reportMissingImports]
from google.genai import types  # type: ignore[reportMissingImports]

from app_config import get_app_config_value, get_backend
from ui import JarvisUI
from memory.memory_manager import load_memory, update_memory, delete_memory, format_memory_for_prompt
from actions.open_app import open_app
from actions.sys_info  import sys_info
from actions.calendar import get_calendar_events, add_calendar_event, delete_calendar_event
from actions.reminders import get_reminders, add_reminder
from actions.browser   import browser_control
from actions.shell     import shell_run
from actions.whatsapp  import send_whatsapp_message, save_whatsapp_contact
from actions.media     import play_media
from actions.weather   import get_weather_summary
from actions.screen_vision import analyze_screen
from actions.youtube_stats import get_youtube_channel_report
from actions.workspace import get_todo_content, add_todo_item, remove_todo_item
from actions.smarthome import execute_smarthome_intent
from services.mcp_controller import MCPController
from skill_manager import test_and_deploy_skill

# Global MCP controller – initialised during JarvisLive startup
_mcp_controller: MCPController | None = None

# ── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR        = Path(__file__).resolve().parent
PROMPT_PATH     = BASE_DIR / "core" / "prompt.txt"


CONTROL_TOKEN_RE = re.compile(r"<ctrl\d+>", re.IGNORECASE)

# ── Model ───────────────────────────────────────────────────────────────────
LIVE_MODEL = "models/gemini-2.5-flash-native-audio-latest"

# ── Audio ───────────────────────────────────────────────────────────────────
FORMAT           = pyaudio.paInt16
CHANNELS         = 1
SEND_SAMPLE_RATE = 16000
RECV_SAMPLE_RATE = 24000
CHUNK_SIZE       = 1024
pya              = pyaudio.PyAudio()

# ── Tool definitions ──────────────────────────────────────────────────────────
TOOL_DECLARATIONS = [
    {
        "name": "open_app",
        "description": "Opens any application on Windows like Spotify, Chrome, or VS Code.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {
                    "type": "STRING",
                    "description": "Application name (e.g. 'Spotify', 'Chrome', 'Terminal')"
                }
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "sys_info",
        "description": "Retrieves system information like battery, CPU, RAM, and time.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "battery | cpu | ram | disk | time | date | network | all"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_weather",
        "description": (
            "Gets the current weather summary, tomorrow's forecast, or a 10-day outlook for a location. "
            "When the user asks for tomorrow's weather or a 10-day forecast, you must call this tool "
            "and pass the time context (like 'tomorrow' or '10-day') inside the query or location argument, "
            "rather than refusing the request."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "location": {
                    "type": "STRING",
                    "description": "City or location. Leave empty for Grantham."
                },
                "query": {
                    "type": "STRING",
                    "description": "Time context like 'tomorrow', '10 day outlook', or a weekday name"
                }
            }
        }
    },
    {
        "name": "get_calendar_events",
        "description": (
            "Reads the local calendar (JSON file). "
            "Summarises today's, tomorrow's, next events or upcoming agenda. "
            "Use when the user asks about meetings, calendar, agenda, events or daily schedule."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": (
                        "today | tomorrow | next | agenda | week or natural language "
                        "'next 30 days', '2 weeks', 'this month', 'next month'"
                    )
                },
                "limit": {
                    "type": "NUMBER",
                    "description": "Maximum number of events"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "add_calendar_event",
        "description": (
            "Adds a new event to the local calendar (JSON file). "
            "Use when the user wants to add a meeting, appointment, calendar entry or create an event. "
            "Provide the start date as actual date/time; if end is not given, a default duration is used."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {
                    "type": "STRING",
                    "description": "Event title. Example: 'Dentist Appointment'"
                },
                "start_iso": {
                    "type": "STRING",
                    "description": "Start date/time. ISO or yyyy-MM-dd HH:mm format."
                },
                "end_iso": {
                    "type": "STRING",
                    "description": "End date/time. Optional."
                },
                "location": {
                    "type": "STRING",
                    "description": "Event location. Optional."
                },
                "notes": {
                    "type": "STRING",
                    "description": "Event notes. Optional."
                },
                "calendar_name": {
                    "type": "STRING",
                    "description": "Calendar name to add to. Optional."
                },
                "all_day": {
                    "type": "BOOLEAN",
                    "description": "If true, creates an all-day event."
                }
            },
            "required": ["title", "start_iso"]
        }
    },
    {
        "name": "delete_calendar_event",
        "description": (
            "Deletes an event from the local calendar. "
            "Use when the user wants to delete a meeting, appointment or calendar record. "
            "If there are multiple events with the same name, provide the start date as actual date/time to find the correct record."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {
                    "type": "STRING",
                    "description": "Event title to delete. Example: 'Dentist Appointment'"
                },
                "start_iso": {
                    "type": "STRING",
                    "description": "Optional date/time. Used to distinguish between events with the same name."
                },
                "calendar_name": {
                    "type": "STRING",
                    "description": "Optional calendar name"
                },
                "delete_all_matches": {
                    "type": "BOOLEAN",
                    "description": "If true, deletes all matching events"
                }
            },
            "required": ["title"]
        }
    },
    {
        "name": "get_reminders",
        "description": (
            "Reads the reminders list (local JSON). "
            "Summarises today's, upcoming, overdue or all open reminders. "
            "Use when the user asks about reminders, to-do list or tasks."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "today | upcoming | overdue | all | next"
                },
                "limit": {
                    "type": "NUMBER",
                    "description": "Maximum number of reminders"
                },
                "list_name": {
                    "type": "STRING",
                    "description": "Optional specific reminder list name"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "add_reminder",
        "description": (
            "Adds a new reminder (local JSON). "
            "Use when the user says 'remind me', 'add reminder', 'set a reminder'. "
            "Convert relative time expressions to ISO format in the due_iso field based on today's date context."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {
                    "type": "STRING",
                    "description": "Reminder title"
                },
                "due_iso": {
                    "type": "STRING",
                    "description": "Optional date/time. Example: 2026-04-13T09:00 or 2026-04-13 for all day"
                },
                "notes": {
                    "type": "STRING",
                    "description": "Optional notes"
                },
                "list_name": {
                    "type": "STRING",
                    "description": "Optional reminder list"
                },
                "priority": {
                    "type": "STRING",
                    "description": "low | medium | high"
                },
                "all_day": {
                    "type": "BOOLEAN",
                    "description": "If true, creates an all-day reminder"
                }
            },
            "required": ["title"]
        }
    },
    {
        "name": "browser_control",
        "description": "Opens a URL in the browser, searches Google, or plays the first YouTube result directly.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "open_url | search | play_youtube"},
                "url":    {"type": "STRING", "description": "URL to open (for open_url)"},
                "query":  {"type": "STRING", "description": "Search query (for search or play_youtube)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "shell_run",
        "description": "Runs a Windows PowerShell command. File operations, system management.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "command": {
                    "type": "STRING",
                    "description": "Command to execute"
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "play_media",
        "description": (
            "Opens a song, music or video on YouTube, Spotify Desktop or Apple Music Web. "
            "If the user specifies a platform, use that. Otherwise try the appropriate one. "
            "If the user says 'play', 'open', use autoplay=true."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "Song, artist, album or video search term"
                },
                "provider": {
                    "type": "STRING",
                    "description": "auto | youtube | spotify | apple_music"
                },
                "autoplay": {
                    "type": "BOOLEAN",
                    "description": "If true, plays directly when possible"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_youtube_channel_report",
        "description": (
            "Reports public statistics and recent video performance of a YouTube channel. "
            "Use when the user asks about channel statistics, subscriber count, recent videos, "
            "growth rate or YouTube analytics. This tool uses public YouTube Data API data, not Studio."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": (
                        "Natural language analysis request. Example: "
                        "'How are my YouTube stats?', 'analyze my recent videos', "
                        "'summarise my channel growth'"
                    )
                },
                "handle": {
                    "type": "STRING",
                    "description": (
                        "Optional channel handle, channel link or channel ID. "
                        "If left empty, the youtube_channel_handle from settings is used."
                    )
                },
                "video_limit": {
                    "type": "NUMBER",
                    "description": "Number of recent videos to include in analysis. Default 6."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "analyze_screen",
        "description": (
            "Takes a screenshot and analyses it with Gemini vision. "
            "Use when the user asks what is on the screen, an error, visible text, buttons or window content. "
            "This version only supports the active window."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "The user's question about the screen. Example: 'Read this error', 'What's on the screen?'"
                },
                "target": {
                    "type": "STRING",
                    "description": "Currently only active_window is supported."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "save_memory",
        "description": "Saves important information about the user to persistent memory. Call silently when hearing name, preferences, projects etc.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": "identity | preferences | projects | notes"
                },
                "key":   {"type": "STRING", "description": "Short key (e.g. 'name')"},
                "value": {"type": "STRING", "description": "Value (in English)"}
            },
            "required": ["category", "key", "value"]
        }
    },
    {
        "name": "delete_memory",
        "description": (
            "Deletes a record from persistent memory. "
            "Use when the user says 'remove that from your memory', 'forget', 'delete'. "
            "If possible, delete by category and key; if unsure, use match_text to find and remove the relevant record."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": "Category of the record. Example: notes | identity | preferences | projects"
                },
                "key": {
                    "type": "STRING",
                    "description": "Key to delete. Example: claude_limit_refresh"
                },
                "match_text": {
                    "type": "STRING",
                    "description": "Natural language fragment to find the record. Example: 'claude ai limit refresh'"
                }
            }
        }
    },
    {
        "name": "send_whatsapp_message",
        "description": (
            "Opens a message draft or sends a message via WhatsApp Web. "
            "Can work with a contact name or phone number. "
            "If no phone number is given, first search the contact name in saved WhatsApp contacts and imported phone book. "
            "If the user explicitly says 'send', 'forward', 'send now' with a clear sending intent, "
            "use send_now=true without asking for extra confirmation. "
            "If the user only says 'prepare', 'draft', 'write but don't send', use send_now=false."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "recipient_name": {
                    "type": "STRING",
                    "description": "Contact name. E.g.: 'Mom', 'John', 'Ece'"
                },
                "phone_number": {
                    "type": "STRING",
                    "description": "International phone number. E.g.: +905551112233"
                },
                "message": {
                    "type": "STRING",
                    "description": "Message content to send"
                },
                "app_target": {
                    "type": "STRING",
                    "description": "desktop | web | auto. Default auto, prefers desktop."
                },
                "send_now": {
                    "type": "BOOLEAN",
                    "description": "If true, automatically sends the message after opening the chat"
                }
            },
            "required": ["message"]
        }
    },
    {
        "name": "save_whatsapp_contact",
        "description": (
            "Saves a frequently used WhatsApp contact with name and phone number to persistent memory. "
            "Use when the user defines a contact to be reused, like 'my mom', 'Ahmet', 'my work partner'."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "display_name": {
                    "type": "STRING",
                    "description": "Contact name to save. E.g.: 'Mom', 'Ahmet'"
                },
                "phone_number": {
                    "type": "STRING",
                    "description": "International phone number. E.g.: +905551112233"
                },
                "aliases": {
                    "type": "STRING",
                    "description": "Comma-separated alternative names. E.g.: 'mom, mother, anne'"
                }
            },
            "required": ["display_name", "phone_number"]
        }
    },
    {
        "name": "switch_workspace_tab",
        "description": (
            "Switches the workspace dashboard card between the shared to-do list, the now-playing media tracker, "
            "or the smart home status dashboard. "
            "Use when the user says 'show my to-do list', 'show media tracker', 'show smart home', "
            "'switch workspace', 'show what's playing', 'show my checklist', "
            "'switch to media', 'switch to todo', or 'switch to smarthome'."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "tab": {
                    "type": "STRING",
                    "description": "Which workspace view to show: 'todo' for the shared checklist, 'media' for now-playing media info, or 'smarthome' for the smart home status dashboard"
                }
            },
            "required": ["tab"]
        }
    },
    {
        "name": "refresh_workspace",
        "description": (
            "Instantly force-refreshes the workspace card data on the dashboard. "
            "Use when the user says 'refresh the workspace', 'update the dashboard', "
            "'refresh the media info', 'refresh the todo list', 'update now playing', "
            "or any request to force an immediate reload of the workspace panel contents."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "get_todo_content",
        "description": (
            "Reads and returns the complete text lines of the user's workspace to-do list. "
            "Use when the user says 'what's on my list', 'show my todo list', "
            "'read my checklist', 'what tasks do I have', or any request to view the full to-do list contents."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "add_todo_item",
        "description": (
            "Appends a brand new task or bullet point line to the active to-do list file. "
            "Use when the user says 'add to my list', 'add a task', 'add to checklist', "
            "'remember to', 'put this on my list', or any request to create a new todo item."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "task": {
                    "type": "STRING",
                    "description": "The task description to add to the to-do list."
                }
            },
            "required": ["task"]
        }
    },
    {
        "name": "remove_todo_item",
        "description": (
            "Removes a completed task line from the to-do list file by searching for a matching keyword. "
            "Use when the user says 'remove from my list', 'delete task', 'mark complete', "
            "'cross off', 'finish task', or any request to remove a todo item. "
            "It searches case-insensitively and removes any line containing the keyword."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "task_keyword": {
                    "type": "STRING",
                    "description": "A keyword or phrase to match against existing todo items. Lines containing this keyword will be removed."
                }
            },
            "required": ["task_keyword"]
        }
    },
    {
        "name": "control_maton",
        "description": (
            "Sends commands to the Maton.ai gateway to execute actions in connected apps (Google Mail, Outlook, "
            "Slack, Google Calendar, Google Sheets, Google Drive, Notion, etc.). "
            "Use when the user wants to send an email, create a draft, find an email, "
            "send a Slack message, list Slack channels, create a calendar event, add a sheet row, "
            "find files, or any other action in their connected Maton apps. "
            "Each app has specific action names like 'send-email', 'create-draft', 'find-email', "
            "'send-message', 'list-channels', 'create-event', 'list-events', 'create-page', etc."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_id": {
                    "type": "STRING",
                    "description": "The connected app identifier (e.g. 'google-mail', 'outlook', 'slack', 'google-calendar', 'google-sheet', 'google-drive', 'notion')"
                },
                "action_name": {
                    "type": "STRING",
                    "description": "The specific action to perform (e.g. 'send-email', 'create-draft', 'find-email', 'send-message', 'list-channels', 'create-event', 'list-events', 'get-page', 'find-file', 'add-multiple-rows')"
                },
                "params": {
                    "type": "OBJECT",
                    "description": "Action-specific parameters (e.g., query, id, to, subject, body, threadId).",
                    "properties": {
                        "query": {"type": "STRING", "description": "The search term or query string for finding emails."},
                        "id": {"type": "STRING", "description": "The message ID or draft ID for reading or updating items."},
                        "to": {"type": "STRING", "description": "Recipient email address."},
                        "subject": {"type": "STRING", "description": "Email subject line."},
                        "body": {"type": "STRING", "description": "The main text body content of the email or draft."},
                        "threadId": {"type": "STRING", "description": "Optional thread ID to link a reply to an existing conversation."}
                    }
                }
            },
            "required": ["app_id", "action_name"]
        }
    },
    {
        "name": "control_smart_home",
        "description": "Controls and checks the status of smart home devices (lights, switches, sockets) via Home Assistant. Use this tool BOTH to execute changes AND to check if devices or rooms are currently on or off.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "device_keyword": {
                    "type": "STRING",
                    "description": "The specific device name (e.g., 'left light') OR the name of a room/area (e.g., 'bedroom', 'living room') when checking status or controlling groups."
                },
                "action": {
                    "type": "STRING",
                    "description": "The action to perform. Crucial: Use 'check_status' if the user asks a question about whether a specific light, device, or an entire room/area is currently turned on or off.",
                    "enum": ["turn on", "turn off", "toggle", "check_status", "list_devices"]
                },
                "brightness": {"type": "INTEGER", "description": "Optional brightness percentage (1-100)."},
                "color": {"type": "STRING", "description": "Optional color name."}
            },
            "required": ["device_keyword", "action"]
        }
    },
    {
        "name": "test_and_deploy_skill",
        "description": (
            "Safely tests a new Python skill inside an isolated virtual environment "
            "sandbox before integrating it permanently into JARVIS's live dynamic_skills/ "
            "directory. Use THIS tool when the user asks JARVIS to write or create a new "
            "skill, plugin, or automation script. The skill is compile-checked, runtime-tested "
            "inside a sandbox venv, and only promoted to production if all checks pass."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "skill_name": {
                    "type": "STRING",
                    "description": "Human-readable name for the skill (e.g. 'email summarizer', 'weather alert')."
                },
                "python_code": {
                    "type": "STRING",
                    "description": "The full Python source code of the skill."
                },
                "required_pip_packages": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "Optional list of PyPI packages to install (e.g. ['requests', 'beautifulsoup4'])."
                }
            },
            "required": ["skill_name", "python_code"]
        }
    },
    {
        "name": "execute_dynamic_skill",
        "description": (
            "Executes a previously verified skill from the dynamic_skills production "
            "folder. Use this tool when the user asks JARVIS to run a skill that has "
            "already been tested and deployed via test_and_deploy_skill."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "skill_name": {
                    "type": "STRING",
                    "description": "The name of the skill to execute (e.g. 'email summarizer', 'weather alert')."
                },
                "arguments": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "Optional command-line arguments to pass to the skill."
                }
            },
            "required": ["skill_name"]
        }
    }
]


def get_api_key() -> str:
    return str(get_app_config_value("gemini_api_key", "") or "")


def load_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return (
            "You are JARVIS — a personal AI assistant running on Windows. "
            "Speak in English. Give short and clear responses. "
            "Complete tasks by using tools, never simulate or hallucinate."
        )


def execute_dynamic_skill(skill_name: str, arguments: list[str] | None = None) -> str:
    """
    Executes a previously verified skill from the dynamic_skills production folder.
    """
    clean_name = skill_name.strip().lower().replace(" ", "_")
    live_file = os.path.join(".", "dynamic_skills", f"{clean_name}.py")
    
    if not os.path.exists(live_file):
        return f"Execution Error: Skill '{skill_name}' does not exist in production."
        
    try:
        # Run the production skill using the main system interpreter
        cmd = [sys.executable, live_file] + (arguments if arguments else [])
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Runtime Error executing skill '{skill_name}':\nSTDOUT: {e.stdout}\nSTDERR: {e.stderr}"


class JarvisLive:
    def __init__(self, ui: JarvisUI):
        self.ui             = ui
        self.session        = None
        self.audio_in_queue = None
        self.out_queue      = None
        self._loop          = None
        self._is_speaking   = False
        self._speaking_lock = threading.Lock()

        self.ui.on_text_command  = self._on_text_command
        self.ui.on_pause_toggle  = self._on_pause_toggle
        self.ui.on_effects_state_change = self._on_effects_state_change
        self._paused             = False

        # Initialise the MCP controller (lazy session, no connection yet)
        global _mcp_controller
        if _mcp_controller is None:
            # Point at the Maton gateway by default; override via config later
            _mcp_controller = MCPController(
                server_url="https://gateway.maton.ai",
                transport="http",
                app_id="google-mail",
            )

    def _on_pause_toggle(self, paused: bool):
        self._paused = paused

    def _on_effects_state_change(self, enabled: bool):
        pass

    def _focus_ui_section_for_tool(self, tool_name: str, args: dict):
        if tool_name == "sys_info":
            query = str(args.get("query", "")).strip().lower()
            if query in {"time", "date"}:
                self.ui.focus_panel("time", duration_ms=5200)
            else:
                self.ui.focus_panel("system", duration_ms=5200)
        elif tool_name == "get_weather":
            self.ui.focus_panel("weather", duration_ms=5600)
        elif tool_name == "switch_workspace_tab":
            self.ui.focus_panel("workspace", duration_ms=5600)

    def _on_text_command(self, text: str):
        if self._paused:
            return
        self.ui.write_log(f"You: {text}")
        if not self._loop or not self.session:
            self.ui.write_log("ERR: JARVIS connection not ready yet.")
            return
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    async def _interrupt_audio(self):
        try:
            if self.audio_in_queue:
                while not self.audio_in_queue.empty():
                    try:
                        self.audio_in_queue.get_nowait()
                    except Exception:
                        break
            if self.session:
                await self.session.send_realtime_input(audio_stream_end=True)
            self.set_speaking(False)
        except Exception:
            pass


    def set_speaking(self, value: bool):
        with self._speaking_lock:
            self._is_speaking = value
        if value:
            self.ui.set_state("SPEAKING")
        else:
            self.ui.set_state("LISTENING")

    def speak_error(self, tool_name: str, error: str):
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} — {short}")
        self.ui.write_debug(f"{tool_name}: {short}", level="ERROR")
        self.ui.set_state("ERROR")

    @staticmethod
    def _result_looks_like_error(result) -> bool:
        text = str(result or "").strip().lower()
        if not text:
            return False
        error_markers = (
            "error",
            "could not",
            "cannot",
            "not found",
            "could not be opened",
            "could not be completed",
            "invalid",
            "permission required",
            "permission needed",
            "connection",
            "required.",
        )
        return any(marker in text for marker in error_markers)

    @staticmethod
    def _should_play_success_sfx(tool_name: str, args: dict, result) -> bool:
        action_tools = {
            "open_app",
            "add_calendar_event",
            "add_reminder",
            "delete_calendar_event",
            "remove_calendar_event",
        }
        if tool_name in action_tools:
            return True

        if tool_name == "send_whatsapp_message":
            text = str(result or "").lower()
            if bool(args.get("send_now", False)):
                return "sent" in text
            return False

        return False

    @staticmethod
    def _clean_transcript_text(text: str) -> tuple[str, bool]:
        raw = str(text or "")
        had_noise = False
        if CONTROL_TOKEN_RE.search(raw):
            had_noise = True
            raw = CONTROL_TOKEN_RE.sub(" ", raw)
        cleaned = []
        for ch in raw:
            if ch in "\n\r\t" or ord(ch) >= 32:
                cleaned.append(ch)
            else:
                had_noise = True
        normalized = " ".join("".join(cleaned).split())
        return normalized.strip(), had_noise

    def _build_config(self) -> types.LiveConnectConfig:
        memory  = load_memory()
        mem_str = format_memory_for_prompt(memory)
        sys_p   = load_system_prompt()
        now     = datetime.datetime.now()
        time_ctx = f"[CURRENT TIME]\n{now.strftime('%A, %d %B %Y — %H:%M')}\n\n"

        parts = [time_ctx]
        if mem_str:
            parts.append(mem_str + "\n\n")
        parts.append(sys_p)

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction="\n".join(parts),
            tools=[{"function_declarations": TOOL_DECLARATIONS}],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=str(get_app_config_value("voice", "Charon") or "Charon")
                    )
                )
            ),
        )

    async def _execute_tool(self, fc) -> types.FunctionResponse:
        name = fc.name
        args = dict(fc.args or {})
        print(f"[JARVIS] 🔧 {name} {args}")
        self.ui.set_state("THINKING")

        loop   = asyncio.get_event_loop()
        result = "Done."
        had_exception = False

        try:
            if name == "save_memory":
                cat = args.get("category", "notes")
                key = args.get("key", "")
                val = args.get("value", "")
                if key and val:
                    update_memory({cat: {key: {"value": val}}})
                    print(f"[Memory] 💾 {cat}/{key} = {val}")
                result = "ok"

            elif name == "delete_memory":
                result = delete_memory(
                    args.get("category", ""),
                    args.get("key", ""),
                    args.get("match_text", ""),
                )

            elif name == "open_app":
                r = await loop.run_in_executor(
                    None, lambda: open_app(args.get("app_name", "")))
                result = r or f"{args.get('app_name')} opened."

            elif name == "sys_info":
                self._focus_ui_section_for_tool(name, args)
                r = await loop.run_in_executor(
                    None, lambda: sys_info(args.get("query", "all")))
                result = r or "Information retrieved."

            elif name == "get_weather":
                self._focus_ui_section_for_tool(name, args)
                r = await loop.run_in_executor(
                    None, lambda: get_weather_summary(args.get("location") or args.get("query") or "today"))

                # Format the output text cleanly into layout cards
                if r:
                    clean_text = r.replace("Current weather for Grantham: ", "").replace("Weather forecast for Grantham tomorrow: ", "").replace("Here is the 10-day weather outlook for Grantham:", "")
                    self.ui._weather_card["primary"] = "Grantham"
                    # Split by periods to turn each sentence into its own distinct row/bullet point
                    self.ui._weather_card["details"] = [sentence.strip() for sentence in clean_text.split(".") if sentence.strip()]
                else:
                    self.ui._weather_card["primary"] = "Weather"
                    self.ui._weather_card["details"] = ["Offline"]

                result = r or "Weather information retrieved."

            elif name == "get_calendar_events":
                r = await loop.run_in_executor(
                    None,
                    lambda: get_calendar_events(
                        args.get("query", "today"),
                        int(args.get("limit", 6) or 6),
                    ),
                )
                result = r or "Calendar information retrieved."

            elif name == "add_calendar_event":
                r = await loop.run_in_executor(
                    None,
                    lambda: add_calendar_event(
                        args.get("title", ""),
                        args.get("start_iso", ""),
                        args.get("end_iso", ""),
                        args.get("notes", ""),
                        args.get("location", ""),
                        args.get("calendar_name", ""),
                        bool(args.get("all_day", False)),
                    ),
                )
                result = r or "Calendar event added."

            elif name == "delete_calendar_event":
                r = await loop.run_in_executor(
                    None,
                    lambda: delete_calendar_event(
                        args.get("title", ""),
                        args.get("start_iso", ""),
                        args.get("calendar_name", ""),
                        bool(args.get("delete_all_matches", False)),
                    ),
                )
                result = r or "Calendar event deleted."

            elif name == "get_reminders":
                r = await loop.run_in_executor(
                    None,
                    lambda: get_reminders(
                        args.get("query", "upcoming"),
                        int(args.get("limit", 8) or 8),
                        args.get("list_name", ""),
                    ),
                )
                result = r or "Reminder information retrieved."

            elif name == "add_reminder":
                r = await loop.run_in_executor(
                    None,
                    lambda: add_reminder(
                        args.get("title", ""),
                        args.get("due_iso", ""),
                        args.get("notes", ""),
                        args.get("list_name", ""),
                        args.get("priority", ""),
                        bool(args.get("all_day", False)),
                    ),
                )
                result = r or "Reminder added."

            elif name == "browser_control":
                r = await loop.run_in_executor(
                    None, lambda: browser_control(
                        args.get("action"),
                        args.get("url"),
                        args.get("query")
                    ))
                result = r or "Done."

            elif name == "shell_run":
                r = await loop.run_in_executor(
                    None, lambda: shell_run(args.get("command", "")))
                result = r or "Command executed."

            elif name == "play_media":
                r = await loop.run_in_executor(
                    None,
                    lambda: play_media(
                        args.get("query", ""),
                        args.get("provider", "auto"),
                        bool(args.get("autoplay", True)),
                    ),
                )
                result = r or "Media playback started."

            elif name == "get_youtube_channel_report":
                r = await loop.run_in_executor(
                    None,
                    lambda: get_youtube_channel_report(
                        args.get("query", "overview"),
                        args.get("handle", ""),
                        int(args.get("video_limit", 6) or 6),
                    ),
                )
                result = r or "YouTube channel report retrieved."

            elif name == "analyze_screen":
                r = await loop.run_in_executor(
                    None,
                    lambda: analyze_screen(
                        args.get("query", "What's on the screen?"),
                        args.get("target", "active_window"),
                    ),
                )
                result = r or "Screen analysis completed."

            elif name == "send_whatsapp_message":
                r = await loop.run_in_executor(
                    None,
                    lambda: send_whatsapp_message(
                        args.get("message", ""),
                        args.get("phone_number", ""),
                        args.get("recipient_name", ""),
                        bool(args.get("send_now", False)),
                        args.get("app_target", "auto"),
                    ),
                )
                result = r or "WhatsApp operation completed."

            elif name == "save_whatsapp_contact":
                r = await loop.run_in_executor(
                    None,
                    lambda: save_whatsapp_contact(
                        args.get("display_name", ""),
                        args.get("phone_number", ""),
                        args.get("aliases", ""),
                    ),
                )
                result = r or "WhatsApp contact saved."

            elif name == "switch_workspace_tab":
                tab = args.get("tab", "todo")
                self._focus_ui_section_for_tool(name, args)
                result = self.ui.switch_workspace_tab(tab)

            elif name == "refresh_workspace":
                self._focus_ui_section_for_tool("switch_workspace_tab", args)
                result = self.ui.refresh_workspace_data()

            elif name == "get_todo_content":
                self._focus_ui_section_for_tool("switch_workspace_tab", args)
                result = await loop.run_in_executor(None, get_todo_content)

            elif name == "add_todo_item":
                task = args.get("task", "")
                result = await loop.run_in_executor(None, add_todo_item, task)
                # Trigger UI refresh so the new item appears on screen
                if "added" in str(result).lower():
                    self.ui._refresh_workspace_data()

            elif name == "remove_todo_item":
                keyword = args.get("task_keyword", "")
                result = await loop.run_in_executor(None, remove_todo_item, keyword)
                # Trigger UI refresh so the removed item disappears from screen
                if "removed" in str(result).lower() or ":" in str(result):
                    self.ui._refresh_workspace_data()

            elif name == "test_and_deploy_skill":
                skill_name = args.get("skill_name", "")
                python_code = args.get("python_code", "")
                packages = args.get("required_pip_packages", None)
                result = await loop.run_in_executor(
                    None,
                    lambda: test_and_deploy_skill(
                        skill_name=skill_name,
                        python_code=python_code,
                        required_pip_packages=packages,
                    ),
                )

            elif name == "execute_dynamic_skill":
                skill_name = args.get("skill_name", "")
                arguments = args.get("arguments", None)
                result = await loop.run_in_executor(
                    None,
                    lambda: execute_dynamic_skill(
                        skill_name=skill_name,
                        arguments=arguments,
                    ),
                )

            elif name == "control_maton":
                action_name = args.get("action_name", "")
                raw_params = args.get("params", {})

                # ── Intent → native Gmail API path mapping ──────────────
                INTENT_TO_PATH = {
                    "find-email":        "gmail/v1/users/me/messages",
                    "search-emails":     "gmail/v1/users/me/messages",
                    "list-emails":       "gmail/v1/users/me/messages",
                    "search-messages":   "gmail/v1/users/me/messages",
                    "list-messages":     "gmail/v1/users/me/messages",
                    "send-email":        "gmail/v1/users/me/messages/send",
                    "create-draft":      "gmail/v1/users/me/drafts",
                    "update-draft":      "gmail/v1/users/me/drafts",
                    "get-email-detail":  "gmail/v1/users/me/messages/{id}",
                    "read-email":        "gmail/v1/users/me/messages/{id}",
                    "list-folders":      "gmail/v1/users/me/labels",
                    "list-labels":       "gmail/v1/users/me/labels",
                }

                LIST_ACTIONS = {"find-email", "search-emails", "list-emails",
                                "search-messages", "list-messages"}

                native_path = INTENT_TO_PATH.get(action_name, action_name)

                if _mcp_controller is None:
                    result = "Error: MCPController not initialised."
                else:
                    # ── Single-action call ──────────────────────────────
                    if action_name not in LIST_ACTIONS:
                        structured_args = {
                            "path": native_path,
                            "params": raw_params,
                        }
                        result = await _mcp_controller.execute_tool(
                            tool_name=action_name,
                            arguments=structured_args,
                        )
                    else:
                        # ── Chained execution: list → detail for each ──
                        # Step 1: List messages
                        list_args = {
                            "path": native_path,
                            "params": {**raw_params, "maxResults": raw_params.get("maxResults", 5)},
                        }
                        raw_list = await _mcp_controller.execute_tool(
                            tool_name=action_name,
                            arguments=list_args,
                        )

                        messages = raw_list.get("messages", []) if isinstance(raw_list, dict) else (
                            raw_list if isinstance(raw_list, list) else [])
                        if not messages:
                            result = "No emails found."
                        else:
                            # Step 2: Fetch detail for each message (skip if already enriched by fallback)
                            detail_path = "gmail/v1/users/me/messages/{id}"
                            detailed = []
                            for msg in messages[:5]:
                                # Check if message already has subject/from from client-side fallback
                                if msg.get("subject") and msg.get("from"):
                                    detailed.append({
                                        "id": msg.get("id"),
                                        "subject": msg["subject"],
                                        "from": msg["from"],
                                        "snippet": msg.get("snippet_fragment", ""),
                                    })
                                    continue

                                msg_id = msg.get("id")
                                if not msg_id:
                                    continue
                                detail_args = {
                                    "path": detail_path,
                                    "params": {
                                        "id": msg_id,
                                        "format": "metadata",
                                        "metadataHeaders": ["Subject", "From"],
                                    },
                                }
                                detail_res = await _mcp_controller.execute_tool(
                                    tool_name="read-email",
                                    arguments=detail_args,
                                )
                                if isinstance(detail_res, dict) and "error" not in detail_res:
                                    payload = detail_res.get("payload", {})
                                    headers = payload.get("headers", [])
                                    subject = next((h.get("value") for h in headers if h.get("name") == "Subject"), "No Subject")
                                    sender = next((h.get("value") for h in headers if h.get("name") == "From"), "Unknown")
                                    detailed.append({
                                        "id": msg_id,
                                        "subject": subject,
                                        "from": sender,
                                        "snippet": detail_res.get("snippet", ""),
                                    })
                                else:
                                    detailed.append({"id": msg_id, "subject": "?", "from": "?", "error": True})

                            lines = [
                                f"  {d['subject']} — {d['from']}  [ID: {d['id']}]"
                                for d in detailed
                            ]
                            result = (
                                f"I found {len(messages)} email(s). "
                                f"Here are the top {len(detailed)}:\n" + "\n".join(lines)
                            )

            elif name == "control_smart_home":
                device = args.get("device_keyword", "")
                action = args.get("action", "toggle")
                brightness = args.get("brightness", None)
                color = args.get("color", None)
                raw_result = await loop.run_in_executor(
                    None, execute_smarthome_intent, device, action, brightness, color)
                # If the intent handler returned a string (e.g. check_status), use it directly as speech
                if isinstance(raw_result, str):
                    result = raw_result
                elif raw_result:
                    self.ui.switch_workspace_tab("smarthome")
                    result = f"Smart home command '{action}' sent to {device}."
                else:
                    result = f"Could not execute smart home command on {device}. Check Home Assistant connection or device name."

            else:
                result = f"Unknown tool: {name}"

        except Exception as e:
            result = f"Error: {e}"
            had_exception = True
            traceback.print_exc()
            self.speak_error(name, e)

        tool_failed = self._result_looks_like_error(result)
        if tool_failed:
            if not had_exception:
                self.ui.set_state("ERROR")
        elif self._should_play_success_sfx(name, args, result):
            self.ui.play_success_sfx()

        if not tool_failed and not self.ui.muted:
            self.ui.set_state("LISTENING")

        print(f"[JARVIS] 📤 {name} → {str(result)[:80]}")
        return types.FunctionResponse(
            id=fc.id, name=name,
            response={"result": result}
        )

    async def _send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            await self.session.send_realtime_input(media=msg)

    async def _listen_audio(self):
        print("[JARVIS] 🎤 Microphone started")
        stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT, channels=CHANNELS,
            rate=SEND_SAMPLE_RATE, input=True,
            frames_per_buffer=CHUNK_SIZE,
        )
        try:
            while True:
                data = await asyncio.to_thread(
                    stream.read, CHUNK_SIZE, exception_on_overflow=False)
                with self._speaking_lock:
                    jarvis_speaking = self._is_speaking
                if not jarvis_speaking and not self.ui.muted and not self._paused:
                    # Non-blocking put: drop oldest if queue is full to avoid stalls
                    try:
                        self.out_queue.put_nowait({"data": data, "mime_type": "audio/pcm"})
                    except asyncio.QueueFull:
                        try:
                            self.out_queue.get_nowait()
                            self.out_queue.put_nowait({"data": data, "mime_type": "audio/pcm"})
                        except (asyncio.QueueFull, asyncio.QueueEmpty):
                            pass
        except Exception as e:
            print(f"[JARVIS] ❌ Microphone: {e}")
            raise
        finally:
            stream.close()

    async def _receive_audio(self):
        print("[JARVIS] 👂 Receiving started")
        out_buf, in_buf = [], []
        output_noise = False
        output_noise_samples = []
        try:
            while True:
                async for response in self.session.receive():
                    if response.data:
                        self.audio_in_queue.put_nowait(response.data)

                    if response.server_content:
                        sc = response.server_content

                        if sc.output_transcription and sc.output_transcription.text:
                            self.set_speaking(True)
                            raw_txt = sc.output_transcription.text.strip()
                            if raw_txt:
                                txt, had_noise = self._clean_transcript_text(raw_txt)
                                if had_noise:
                                    output_noise = True
                                    if len(output_noise_samples) < 4:
                                        output_noise_samples.append(raw_txt)
                                if txt:
                                    out_buf.append(txt)

                        if sc.input_transcription and sc.input_transcription.text:
                            txt = sc.input_transcription.text.strip()
                            if txt:
                                in_buf.append(txt)
                                self.ui.mark_user_activity(True)

                        if sc.turn_complete:
                            self.set_speaking(False)

                            full_in = " ".join(in_buf).strip()
                            if full_in:
                                self.ui.write_log(f"You: {full_in}")
                            in_buf = []

                            full_out = " ".join(out_buf).strip()
                            if full_out:
                                self.ui.write_log(f"JARVIS: {full_out}")
                                if output_noise_samples:
                                    self.ui.write_debug(
                                        "Partially filtered speech transcript: " + " | ".join(output_noise_samples),
                                        level="WARN",
                                    )
                            elif output_noise:
                                self.ui.write_log("ERR: An error occurred while decoding JARVIS's voice response.")
                                if output_noise_samples:
                                    self.ui.write_debug(
                                        "Filtered raw transcript: " + " | ".join(output_noise_samples),
                                        level="WARN",
                                    )
                                self.ui.set_state("ERROR")
                            out_buf = []
                            output_noise = False
                            output_noise_samples = []

                    if response.tool_call:
                        fn_responses = []
                        for fc in response.tool_call.function_calls:
                            print(f"[JARVIS] 📞 {fc.name}")
                            fr = await self._execute_tool(fc)
                            fn_responses.append(fr)
                        await self.session.send_tool_response(
                            function_responses=fn_responses)

        except Exception as e:
            print(f"[JARVIS] ❌ Receive: {e}")
            traceback.print_exc()
            raise

    async def _play_audio(self):
        print("[JARVIS] 🔊 Audio playback started")
        stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT, channels=CHANNELS,
            rate=RECV_SAMPLE_RATE, output=True,
        )
        try:
            while True:
                chunk = await self.audio_in_queue.get()
                await asyncio.to_thread(stream.write, chunk)
        except Exception as e:
            print(f"[JARVIS] ❌ Audio: {e}")
            raise
        finally:
            stream.close()

    async def run(self):
        client = genai.Client(
            api_key=get_api_key(),
            http_options={"api_version": "v1alpha"}
        )

        while True:
            # If paused, don't connect, wait
            if self._paused:
                await asyncio.sleep(1)
                continue

            try:
                print("[JARVIS] 🔌 Connecting...")
                self.ui.set_state("THINKING")
                config = self._build_config()

                async with (
                    client.aio.live.connect(model=LIVE_MODEL, config=config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session        = session
                    self._loop          = asyncio.get_event_loop()
                    self.audio_in_queue = asyncio.Queue()
                    self.out_queue      = asyncio.Queue(maxsize=10)

                    print("[JARVIS] ✅ Connected.")
                    self.ui.set_state("LISTENING")
                    self.ui.write_log("SYS: JARVIS ready. Listening...")

                    tg.create_task(self._send_realtime())
                    tg.create_task(self._listen_audio())
                    tg.create_task(self._receive_audio())
                    tg.create_task(self._play_audio())

            except (Exception, asyncio.CancelledError, GeneratorExit, KeyboardInterrupt) as e:
                if isinstance(e, (KeyboardInterrupt, GeneratorExit)):
                    raise
                print(f"[JARVIS] ⚠️ {e}")
                traceback.print_exc()
                self.set_speaking(False)
                self.ui.write_log(f"ERR: JARVIS connection lost or no internet — {e}")
                self.ui.set_state("ERROR")
                print("[JARVIS] 🔄 Reconnecting in 3 seconds...")
                await asyncio.sleep(3)


def main():
    if os.environ.get("TERM_PROGRAM") == "vscode":
        print("[JARVIS] Started from VS Code.")

    ui = JarvisUI()

    def runner():
        # User may have selected a backend in Setup; wait for it first.
        ui.wait_for_api_key()
        backend = get_backend()
        if backend == "lmstudio":
            from core.lmstudio_runtime import JarvisLocal, ping_lmstudio
            ok, detail = ping_lmstudio()
            if not ok:
                ui.write_log(f"ERR: Cannot reach LM Studio server ({detail}). "
                             "Start 'Local Server' in the LM Studio app.")
            else:
                ui.write_log(f"SYS: LM Studio ready - models: {detail}")
            jarvis = JarvisLocal(ui, TOOL_DECLARATIONS, load_system_prompt)
        else:
            jarvis = JarvisLive(ui)

        try:
            asyncio.run(jarvis.run())
        except KeyboardInterrupt:
            print("\nShutting down...")

    threading.Thread(target=runner, daemon=True).start()
    ui.root.mainloop()


if __name__ == "__main__":
    main()