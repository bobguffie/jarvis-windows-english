"""
MCP Controller — central hub for interacting with any MCP server.

Supports three transport modes:
  - ``http``   – REST‑style HTTP transport for gateways such as Maton.
  - ``sse``    – official MCP over SSE transport.
  - ``stdio``  – sub‑process stdin/stdout transport for local MCP servers.

Provides two main async methods: ``list_tools()`` and ``execute_tool()``.
"""
from __future__ import annotations

import asyncio
import json
import sys
from typing import Any, Literal

import httpx

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    _MCP_AVAILABLE = True
except ImportError:  # pragma: no cover
    _MCP_AVAILABLE = False
    ClientSession = None  # type: ignore[assignment]
    stdio_client = None  # type: ignore[assignment]
    StdioServerParameters = None  # type: ignore[assignment]


CTRL_URL = "https://ctrl.maton.ai"


def _load_maton_key() -> str:
    """Load the Maton API key from the local config file."""
    try:
        from pathlib import Path
        p = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
        raw = json.loads(p.read_text(encoding="utf-8"))
        return str(raw.get("maton_api_key", "") or "").strip()
    except Exception:
        return ""


def _mask_key(key: str) -> str:
    """Return a masked version of the API key for safe logging."""
    if len(key) > 8:
        return key[:4] + "…" + key[-4:]
    return "****"


class MCPController:
    """Async central hub for MCP tool discovery and execution.

    The controller lazily opens a transport session on the first call and
    reuses it for subsequent requests.

    Args:
        server_url: Base URL of the remote server.
        transport: ``"http"`` (default) for REST‑style JSON‑RPC,
                   ``"sse"`` for native MCP over SSE, or
                   ``"stdio"`` for a local sub‑process MCP server.
        app_id: App identifier (e.g. ``"google-mail"``) used by
                the Maton gateway to scope requests.
        server_command: Shell command for the stdio transport.
        server_args: Additional args for the stdio sub‑process.
        headers: Optional extra HTTP headers.
    """

    def __init__(
        self,
        server_url: str | None = None,
        transport: Literal["http", "sse", "stdio"] = "http",
        app_id: str | None = None,
        server_command: str | None = None,
        server_args: list[str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.server_url = (server_url or "https://gateway.maton.ai").rstrip("/")
        self.transport = transport
        self.app_id = app_id
        self.server_command = server_command or sys.executable
        self.server_args = server_args or []

        # Base HTTP headers
        self._base_headers = {"Content-Type": "application/json"}
        if headers:
            self._base_headers.update(headers)
        elif self.transport == "http":
            key = _load_maton_key()
            if key:
                self._base_headers["Authorization"] = f"Bearer {key}"

        # Lazy‑initialised session / client
        self._session: ClientSession | None = None
        self._transport_ctx: Any = None
        self._http_client: httpx.AsyncClient | None = None
        # Cached tool definitions (populated on first list_tools call)
        self._tool_defs: list[dict] | None = None
        # Cached pagination token from the last list call
        self.last_page_token: str | None = None

    # ── public API ────────────────────────────────────────────────────────

    async def list_tools(self) -> list[dict] | dict:
        """Query the connected server for all available tools.

        For the ``http`` transport this calls ``GET /actions`` (or
        ``GET /actions/{app_id}`` if an ``app_id`` was provided).

        Returns:
            A list of tool definitions (cached for subsequent calls).
        """
        if self._tool_defs is not None:
            return self._tool_defs

        if self.transport == "http":
            # The Maton gateway does NOT expose a tool-discovery endpoint.
            # Attempt both possible discovery paths for forward compat:
            for discover_url in (
                f"{CTRL_URL}/connections/{self.app_id}" if self.app_id else f"{CTRL_URL}/connections",
                f"{self.server_url}/actions/{self.app_id}" if self.app_id else f"{self.server_url}/actions",
            ):
                try:
                    data = await self._http_get_url(discover_url)
                    items = None
                    if isinstance(data, list):
                        items = data
                    elif isinstance(data, dict):
                        items = data.get("actions") or data.get("tools") or data.get("connections")
                    if items:
                        self._tool_defs = items
                        print(f"[MATON DEBUG] Discovery OK – {len(self._tool_defs)} tool(s) via {discover_url}")
                        return self._tool_defs
                except Exception:
                    pass

            # No discovery endpoint available – return empty list.
            # The caller can still use execute_tool() with tool_name as the
            # native path (e.g. "gmail/v1/users/me/messages").
            print("[MATON DEBUG] No discovery endpoint available on this gateway.")
            self._tool_defs = []
            return self._tool_defs

        session = await self._ensure_session()
        result = await session.list_tools()
        if hasattr(result, "model_dump"):
            result = result.model_dump()
        if isinstance(result, dict):
            result = result.get("tools", result)
        self._tool_defs = result if isinstance(result, list) else [result]
        return self._tool_defs

    async def execute_tool(
        self, tool_name: str, arguments: dict[str, Any] | None = None
    ) -> dict:
        """Call a tool on the server.

        For the ``http`` transport, this looks up the tool definition
        (cached from ``list_tools``) to find the native path and HTTP
        method, then makes the appropriate request to the gateway.

        Args:
            tool_name: The name of the tool to invoke.
            arguments: Key‑value arguments for the tool.

        Returns:
            The tool execution result.
        """
        if self.transport == "http":
            return await self._execute_via_http(tool_name, arguments or {})

        session = await self._ensure_session()
        result = await session.call_tool(tool_name, arguments or {})
        if hasattr(result, "model_dump"):
            result = result.model_dump()
        return result

    async def close(self) -> None:
        """Tear down the transport and session."""
        if self._session is not None:
            await self._session.__aexit__(None, None, None)
            self._session = None
        if self._transport_ctx is not None:
            await self._transport_ctx.__aexit__(None, None, None)
            self._transport_ctx = None
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    # ── internal helpers ───────────────────────────────────────────────────

    def _infer_method(self, tool_name: str, native_path: str) -> str:
        """Infer the HTTP method from the tool name or native path.

        Actions containing ``send``, ``create``, ``update``, ``delete``,
        or ``add`` are treated as state‑changing (POST). Everything else
        defaults to GET (read‑only).
        """
        write_keywords = ("send", "create", "update", "delete", "remove", "add", "post")
        for kw in write_keywords:
            if kw in tool_name.lower() or kw in native_path.lower():
                if kw == "add":
                    # "add-multiple-rows" → POST
                    return "POST"
                return "POST"
        return "GET"

    def _build_auth_headers(self) -> dict[str, str]:
        """Return headers with Authorization and Content-Type set.

        Falls back to loading the API key from the config file if not
        already present in ``self._base_headers``.
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": self._base_headers.get("Authorization", ""),
        }
        if not headers["Authorization"]:
            key = _load_maton_key()
            if key:
                headers["Authorization"] = f"Bearer {key}"
        return headers

    def _log_request(self, method: str, url: str, headers: dict, body: Any = None):
        """Log the full request details (API key masked) for debugging."""
        safe_headers = {
            k: (_mask_key(v) if k.lower() == "authorization" else v)
            for k, v in headers.items()
        }
        print(f"\n[MATON DEBUG] {method} {url}")
        print(f"[MATON DEBUG] Headers: {json.dumps(safe_headers, indent=2)}")
        if body is not None:
            print(f"[MATON DEBUG] Body: {json.dumps(body, indent=2)}")
        print("")

    async def _execute_via_http(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict:
        """Execute a tool using the Maton gateway's REST API.

        Supports two argument formats:

        1. **Structured** (recommended):
           ``{"path": "gmail/v1/users/me/messages", "params": {"maxResults": 5}}``
           The *path* is the native API path; *params* are the HTTP
           query parameters (for GET) or JSON body (for POST/PUT).

        2. **Flat** (legacy fallback):
           ``{"maxResults": 5}``
           The *tool_name* is used as the native path; the whole dict
           is sent as query parameters or JSON body.
        """
        # Extract native path and HTTP parameters from arguments
        if isinstance(arguments, dict) and "path" in arguments:
            native_path = arguments["path"].lstrip("/")
            params = arguments.get("params", {}).copy() if isinstance(arguments.get("params"), dict) else {}
        else:
            native_path = tool_name.replace("_", "-")
            params = (arguments or {}).copy()

        # Substitue {id} placeholder in the path with an id from params
        if "{id}" in native_path or "{}" in native_path:
            msg_id = params.pop("id", None) or params.pop("messageId", None) or params.pop("msg_id", None)
            if msg_id:
                native_path = native_path.replace("{id}", str(msg_id)).replace("{}", str(msg_id))

        # Map page_token → pageToken for Gmail pagination
        if "page_token" in params:
            params["pageToken"] = params.pop("page_token")

        # Infer request method
        method = self._infer_method(tool_name, native_path)

        # Build URL: {gateway}/{app_id}/{native_path}
        parts = [self.server_url]
        if self.app_id:
            parts.append(self.app_id)
        parts.append(native_path)
        url = "/".join(parts)

        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30)

        headers = self._build_auth_headers()
        self._log_request(method, url, headers, params)

        if method == "GET":
            resp = await self._http_client.get(
                url, headers=headers, params=params, timeout=30
            )
        else:
            resp = await self._http_client.post(
                url, json=params, headers=headers, timeout=30
            )
        resp.raise_for_status()
        data = resp.json()
        # Cache pagination token for chained "next page" calls
        if isinstance(data, dict):
            token = data.get("nextPageToken")
            if token:
                self.last_page_token = token

        # ── Client‑side search fallback ─────────────────────────────
        # If the gateway search (with q param) returned empty results,
        # fall back to fetching recent messages and filtering locally.
        if (
            method == "GET"
            and "{id}" not in native_path
            and isinstance(data, dict)
            and "q" in params
            and (
                ("messages" in data and not data["messages"])
                or ("resultSizeEstimate" in data and data.get("resultSizeEstimate", 0) == 0)
            )
        ):
            original_q = params.get("q", "")
            if original_q:
                print(f"[MATON DEBUG] Gateway search returned 0 results for q={original_q!r}")
                print(f"[MATON DEBUG] Falling back to client‑side filtering on last 20 messages")
                fallback = await self._client_side_search_fallback(original_q)
                if fallback:
                    return fallback

        return data


    async def _client_side_search_fallback(self, original_q: str) -> dict | None:
        """Fetch the 50 most recent messages and filter them locally.

        Called when the gateway search returned zero results.  This method:
          1. Re‑fetches ``gmail/v1/users/me/messages`` *without* the ``q``
             parameter, asking for 50 results.
          2. For each message ID, calls
             ``gmail/v1/users/me/messages/{id}?format=metadata`` to obtain
             the Subject and From headers.
          3. Filters the enriched list locally using Python string matching
             on the original query terms.

        Returns:
            A dict with the same ``{"messages": [...]}`` structure as the
            gateway list response, but enriched with ``subject``, ``from``,
            and ``snippet_fragment`` keys on each message.
        """
        # 1) Fetch the 50 most recent messages (no q param)
        list_url = f"{self.server_url}/{self.app_id}/gmail/v1/users/me/messages"
        headers = self._build_auth_headers()

        resp = await self._http_client.get(
            list_url,
            headers=headers,
            params={"maxResults": 20},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        raw_messages = data.get("messages", [])
        if not raw_messages:
            return None

        print(f"[MATON DEBUG] Fetching metadata for {len(raw_messages)} messages...")

        # 2) Enrich each message with Subject & From (concurrent, rate‑limited)
        enriched = []
        semaphore = asyncio.Semaphore(3)  # max 3 concurrent requests

        async def _fetch_detail(mid: str) -> dict | None:
            async with semaphore:
                try:
                    await asyncio.sleep(0.1)  # small gap between requests
                    detail_url = f"{self.server_url}/{self.app_id}/gmail/v1/users/me/messages/{mid}"
                    det_resp = await self._http_client.get(
                        detail_url,
                        headers=headers,
                        params={"format": "metadata", "metadataHeaders": ["Subject", "From"]},
                        timeout=30,
                    )
                    det_resp.raise_for_status()
                    det = det_resp.json()
                    payload = det.get("payload", {})
                    hdrs = payload.get("headers", [])
                    subject = next((h.get("value", "") for h in hdrs if h.get("name") == "Subject"), "")
                    sender = next((h.get("value", "") for h in hdrs if h.get("name") == "From"), "")
                    snippet = det.get("snippet", "")
                    return {
                        "id": mid,
                        "threadId": next((m.get("threadId", "") for m in raw_messages if m.get("id") == mid), ""),
                        "subject": subject,
                        "from": sender,
                        "snippet_fragment": (snippet or "")[:120],
                    }
                except Exception as exc:
                    print(f"[MATON DEBUG] Failed to fetch detail for {mid}: {exc}")
                    return None

        tasks = [_fetch_detail(msg.get("id")) for msg in raw_messages if msg.get("id")]
        results = await asyncio.gather(*tasks)
        enriched = [r for r in results if r is not None]

        # 3) Filter locally using the original query terms
        search_terms = [
            w.strip().lower() for w in original_q.replace('"', "").split()
            if len(w.strip()) > 2
            and w.strip().lower() not in ("is:unread", "in:inbox", "inbox", "category:primary", "is:read", "label:inbox")
        ]

        if search_terms:
            matched = []
            for msg in enriched:
                text_to_search = f"{msg['subject']} {msg['from']} {msg['snippet_fragment']}".lower()
                if any(term in text_to_search for term in search_terms):
                    matched.append(msg)
            if matched:
                print(f"[MATON DEBUG] Client‑side filter matched {len(matched)} of {len(enriched)} messages")
                enriched = matched

        return {"messages": enriched, "resultSizeEstimate": len(enriched)}


    async def _http_get_url(self, url: str) -> Any:
        """Perform a GET request to an arbitrary URL (used for ctrl‑domain calls)."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30)
        headers = self._build_auth_headers()
        print(f"[MATON DEBUG] GET {url}")
        print(f"[MATON DEBUG] Headers: {json.dumps({k: (_mask_key(v) if k.lower() == 'authorization' else v) for k, v in headers.items()}, indent=2)}")
        resp = await self._http_client.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()

    async def _http_get(self, path: str) -> Any:
        """Perform a GET request against the Maton gateway."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30)
        url = f"{self.server_url}/{path.lstrip('/')}"
        headers = self._build_auth_headers()
        self._log_request("GET", url, headers)
        resp = await self._http_client.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()

    async def _ensure_session(self) -> ClientSession:
        """Return an initialised MCP ``ClientSession`` for SSE/stdio transports."""
        if self._session is not None:
            return self._session

        if self.transport == "sse":
            from mcp.client.sse import sse_client
            self._transport_ctx = sse_client(url=self.server_url)
        else:
            params = StdioServerParameters(
                command=self.server_command, args=self.server_args
            )
            self._transport_ctx = stdio_client(params)

        read, write = await self._transport_ctx.__aenter__()
        self._session = await ClientSession(read, write).__aenter__()
        await self._session.initialize()
        return self._session

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

