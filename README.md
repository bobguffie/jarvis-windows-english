# JARVIS Windows v2.1

Windows JARVIS upgraded from Linux version with new features.

## New Features in v2.1 (ported from Linux)

- **Workspace Dashboard Card** - Hot-swappable left panel with 3 views:
  - **Checklist**: Shared to-do list (local or network share)
  - **Media**: Now-playing detection for Windows media players (Spotify, VLC, etc.)
  - **Smart Home**: Live status of Home Assistant devices
- **MCP Controller** - Central hub for MCP tool discovery and execution
  - HTTP transport for Maton.ai gateway
  - SSE/stdio transport support
  - Client-side search fallback for Gmail
- **Skill Factory** - Test and deploy new Python skills safely:
  - `skill_manager.py` with sandbox testing
  - Isolated venv for dependency testing
  - Auto-promotion to `dynamic_skills/` on success
- **Smart Home Integration** - Control Home Assistant devices:
  - Voice commands for lights, switches, sockets
  - Room-level status checking
  - Brightness and color control
- **Improved Weather** - Open-Meteo API integration:
  - 10-day outlook
  - Tomorrow's forecast
  - Specific weekday forecasts
- **Maton.ai Integration** - Email and app automation:
  - Email search/send/draft via Gmail API
  - Chained list→detail execution
  - OAuth connection discovery

## Quick Start

1. **First run**: Double-click `setup.bat` - creates venv and installs packages
2. **Launch**: Double-click `start.bat` (or run `python main.py` after activating venv)
3. **Configure**: Enter your Gemini API key in the setup UI that appears

## Configuration

Place your API keys in `config/api_keys.json`:
```json
{
    "gemini_api_key": "YOUR_KEY_HERE",
    "youtube_api_key": "YOUR_YOUTUBE_API_KEY",
    "youtube_channel_handle": "@yourchannel",
    "maton_api_key": "YOUR_MATON_KEY_IF_USED"
}
```

Smart home configuration in `config/smarthome.json`:
```json
{
    "ha_url": "http://localhost:8123",
    "ha_token": "YOUR_LONG_LIVED_ACCESS_TOKEN"
}
```

## Directory Structure

```
jarvis-windows-v2.1/
├── main.py              # Core voice assistant (all v2.1 tools)
├── ui.py                # UI with workspace dashboard
├── skill_manager.py     # Skill factory with sandbox testing
├── actions/             # Platform-specific action modules
│   ├── workspace.py     # Workspace card (Windows media detection)
│   ├── smarthome.py     # Smart home intent handling
│   └── maton.py         # Maton gateway wrapper
├── services/            # MCP and smart home services
│   ├── mcp_controller.py # MCP central hub
│   ├── mcp_client.py    # Lightweight MCP client
│   ├── maton_client.py  # Direct Maton REST client
│   └── smarthome.py     # Home Assistant client
├── dynamic_skills/      # Deployed skills (created by Skill Factory)
├── sandbox_stage/       # Temporary test area for skills
├── tools/               # Utility scripts (e.g., smarthome discovery)
├── core/                # Prompt and LM Studio runtime
├── config/              # API keys and settings
├── memory/              # Persistent memory and shared to-do list
├── Fonts/               # Grift font files
├── Icon/                # App icons
└── SFX/                 # Sound effects
```

## New Voice Commands (Tool Declarations)

| Tool | Description |
|------|-------------|
| `switch_workspace_tab` | Switch workspace card between todo/media/smarthome |
| `refresh_workspace` | Force refresh workspace card data |
| `get_todo_content` | Read to-do list contents |
| `add_todo_item` | Add task to to-do list |
| `remove_todo_item` | Remove task from to-do list |
| `control_maton` | Execute actions in connected apps (Gmail, Slack, etc.) |
| `control_smart_home` | Control Home Assistant devices |
| `test_and_deploy_skill` | Test & deploy a new Python skill |
| `execute_dynamic_skill` | Run a previously deployed skill |

## Keyboard Shortcuts

- `F4` - Toggle mute
- `F5` - Toggle pause
- `F9` - Toggle mini window
- `F11` - Toggle fullscreen
- `ESC` - Shutdown

## Credits

- Original: [bobguffie/jarvis-windows-english](https://github.com/bobguffie/jarvis-windows-english)
- Linux source: [bobguffie/jarvis-linux-english](https://github.com/bobguffie/jarvis-linux-english)