# Migrating from your existing JARVIS Windows install to v2.1

Your old install's data is stored in the `memory/` and `config/` folders.
The v2.1 upgrade keeps the same file formats, so you can simply **copy over** your personal data - no conversion needed.

## Step 1 - Get the v2.1 files

- **Option A (Git):**
  ```bat
  git clone https://github.com/bobguffie/jarvis-windows-english.git
  cd jarvis-windows-english
  git checkout jarvis-windows-v2.1
  ```
- **Option B:** Download the `jarvis-windows-v2.1` branch as a ZIP from GitHub and extract it.

## Step 2 - Copy your personal data from the OLD install folder

Copy these files from your **old** JARVIS folder into the **new v2.1** folder at the same paths:

| Old install file            | Copy to (v2.1)              | Contains                                  |
|-----------------------------|-----------------------------|-------------------------------------------|
| `config\api_keys.json`      | `config\api_keys.json`      | Your Gemini & YouTube API keys            |
| `memory\memory.json`        | `memory\memory.json`        | Your saved memories (name, preferences, projects) |
| `memory\phone_book.json`    | `memory\phone_book.json`    | Saved WhatsApp contacts (if you have one) |
| `memory\reminders.json`     | `memory\reminders.json`     | Your existing reminders                   |

> **Tip:** If you don't see `phone_book.json`, it just means you haven't saved any WhatsApp contacts yet - that's fine.

## Step 3 - Install dependencies

Run `setup.bat` once. This:
- Creates a fresh `venv` (you can delete the old one from the old folder)
- Installs all required packages (including the new `fastmcp`, `mcp`, `httpx` for the Skill Factory & MCP controller)

## Step 4 - Launch

Run `start.bat`

Your existing memories, contacts, and reminders will all be there. The v2.1 workspace dashboard, smart home, Maton, and Skill Factory features are ready to use.

---

## Extra: Smart Home (optional)

If you use Home Assistant, edit `config\smarthome.json` with your details:

```json
{
  "ha_url": "http://YOUR_HA_IP:8123",
  "ha_token": "YOUR_LONG_LIVED_ACCESS_TOKEN"
}
```

## Extra: New Skill Factory

Ask JARVIS to "create a skill" and it will test the code in an isolated sandbox (`sandbox_stage\`) before promoting it to `dynamic_skills\` - so a bad skill can never crash the main assistant.

## Note about git

A `.gitignore` is included so these personal files are **never** committed to GitHub:
- `config/api_keys.json`
- `memory/memory.json`
- `memory/reminders.json`
- `credentials.json` / `token.json`

Your data stays local on your machine only.