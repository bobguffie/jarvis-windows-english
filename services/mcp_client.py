"""
MCP (Model Context Protocol) Client — Lightweight HTTP/JSON-RPC integration.
Connects JARVIS to any MCP-compatible server for dynamic tool discovery and execution.
"""
import json
import requests
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"


def _load_api_key() -> str:
    """Load the MCP API key from the local config file."""
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return str(raw.get("mcp_api_key", "") or "").strip()
    except Exception:
        return ""


def list_tools(server_url: str) -> dict:
    """Query the MCP server for all available tools.

    Args:
        server_url: The base URL of the MCP server (e.g. 'https://mcp.example.com').

    Returns:
        The JSON-RPC response containing the tool list.
    """
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "params": {},
        "id": 1,
    }
    try:
        r = requests.post(
            server_url.rstrip("/") + "/",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()
        return {"error": f"MCP list_tools failed: {r.status_code}", "details": r.text}
    except Exception as e:
        return {"error": f"MCP list_tools request failed: {e}"}


def call_tool(server_url: str, tool_name: str, arguments: dict = None) -> dict:
    """Call a tool on the MCP server dynamically.

    Args:
        server_url: The base URL of the MCP server.
        tool_name: The name of the tool to invoke.
        arguments: A dict of arguments to pass to the tool.

    Returns:
        The JSON-RPC response from the tool execution.
    """
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments or {},
        },
        "id": 1,
    }
    try:
        api_key = _load_api_key()
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        r = requests.post(
            server_url.rstrip("/") + "/",
            json=payload,
            headers=headers,
            timeout=30,
        )
        if r.status_code == 200:
            return r.json()
        return {"error": f"MCP call_tool failed: {r.status_code}", "details": r.text}
    except Exception as e:
        return {"error": f"MCP call_tool request failed: {e}"}
