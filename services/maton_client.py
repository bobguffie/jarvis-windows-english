"""
Maton.ai API Client — Direct REST API integration.
Connects JARVIS to the Maton gateway for dynamic tool actions.
Uses native_path routing and supports GET/POST methods.
Forces URL query string encoding for GET requests to guarantee
the Maton Gateway proxy receives the filter parameters.
"""

import json
import requests
from pathlib import Path
from urllib.parse import urlencode


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

GATEWAY_URL = "https://gateway.maton.ai"
CTRL_URL = "https://ctrl.maton.ai"


def _load_maton_key() -> str:
    """Load the Maton API key from the local config file."""
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return str(raw.get("maton_api_key", "") or "").strip()
    except Exception:
        return ""


class MatonClient:
    """Client for the Maton.ai Gateway API with native path passthrough."""

    def __init__(self):
        self.api_key = _load_maton_key()
        self.gateway_url = GATEWAY_URL
        self.ctrl_url = CTRL_URL
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @property
    def ready(self) -> bool:
        """Returns True if a valid API key is configured."""
        return bool(self.api_key) and len(self.api_key) > 10

    def call_action(
        self, app_id: str, native_path: str, params: dict = None, method: str = "POST"
    ) -> dict:
        """Calls the Maton Gateway passing through native API endpoints.

        For GET requests, query parameters are hard-baked into the URL string
        using urlencode to ensure the Maton gateway proxy receives them.
        The params dict passed to requests.get is explicitly kept empty.

        Args:
            app_id: The app identifier (e.g. 'google-mail', 'slack', 'outlook').
            native_path: The exact native API path (e.g. 'gmail/v1/users/me/messages').
            params: Action-specific parameters dict.
            method: HTTP method — 'POST' or 'GET'.

        Returns:
            The response JSON from the Maton gateway.
        """
        if not self.ready:
            return {"error": "Maton API key not configured. Add 'maton_api_key' to config/api_keys.json."}

        clean_params = params or {}
        method_upper = method.upper()

        # --- THE ORIGINAL WORKING URL ENCODER ---
        if method_upper == "GET" and clean_params:
            query_string = urlencode(clean_params)
            url = f"{self.gateway_url}/{app_id}/{native_path.lstrip('/')}?{query_string}"
            # This must be an empty dict so requests.get doesn't append extra junk
            request_params = {}
        else:
            url = f"{self.gateway_url}/{app_id}/{native_path.lstrip('/')}"
            request_params = clean_params

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            if method_upper == "GET":
                # Must pass request_params (which is empty) to keep the URL clean
                r = requests.get(url, headers=headers, params=request_params, timeout=15)
            else:
                r = requests.post(url, headers=headers, json=request_params, timeout=15)

            print(f"\n[MATON DEBUG] {method_upper} {url}")
            print(f"[MATON DEBUG] Params: {clean_params}")
            print(f"[MATON DEBUG] Status: {r.status_code}\n")

            if r.status_code == 404:
                return {"error": "404 Not Found", "details": f"Endpoint {url} does not exist."}

            if r.status_code == 200:
                try:
                    return r.json()
                except Exception:
                    return {"result": r.text}
            else:
                try:
                    err = r.json()
                except Exception:
                    err = {"status": r.status_code, "body": r.text}
                return {"error": f"Maton API error ({r.status_code})", "details": err}

        except requests.exceptions.Timeout:
            return {"error": "Maton API request timed out after 15s."}
        except requests.exceptions.ConnectionError:
            return {"error": f"Could not connect to Maton gateway at {url}."}
        except Exception as e:
            return {"error": f"Maton request failed: {e}"}

    def get_connections(self) -> dict:
        """Fetch active OAuth connections from the control plane.

        Returns:
            List of connected apps.
        """
        if not self.ready:
            return {"error": "Maton API key not configured."}

        try:
            r = requests.get(
                f"{self.ctrl_url}/connections",
                headers=self._headers,
                timeout=10,
            )
            if r.status_code == 200:
                return r.json()
            return {"error": f"Failed to fetch connections: {r.status_code}"}
        except Exception as e:
            return {"error": f"Connection check failed: {e}"}

    def list_actions(self, app_id: str = None) -> dict:
        """List available actions for an app (or all apps if None).

        Args:
            app_id: Optional app identifier to filter by.

        Returns:
            Available action schemas.
        """
        if not self.ready:
            return {"error": "Maton API key not configured."}

        url = f"{self.gateway_url}/actions"
        if app_id:
            url = f"{self.gateway_url}/actions/{app_id}"

        try:
            r = requests.get(url, headers=self._headers, timeout=10)
            if r.status_code == 200:
                return r.json()
            return {"error": f"Failed to list actions: {r.status_code}"}
        except Exception as e:
            return {"error": f"List actions failed: {e}"}