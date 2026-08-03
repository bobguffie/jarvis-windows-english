import json
import requests

class SmartHomeClient:
    def __init__(self, config_path='config/smarthome.json'):
        self.config_path = config_path
        self.url = "http://localhost:8123"
        self.token = ""
        self.headers = {}
        self.load_config()

    def load_config(self):
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                self.url = config.get("ha_url", self.url)
                self.token = config.get("ha_token", "")
                self.headers = {
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json"
                }
        except Exception:
            pass

    def get_entity_state(self, entity_id):
        """Fetches the full state machine and attributes of a specific device."""
        try:
            r = requests.get(f"{self.url}/api/states/{entity_id}", headers=self.headers, timeout=2)
            if r.status_code == 200:
                return r.json()
        except Exception:
            return None

    def toggle_device(self, entity_id, domain='switch', action='toggle', brightness=None, color=None):
        """Triggers a local state change with optional brightness and color modifiers."""
        try:
            url = f"{self.url}/api/services/{domain}/{action}"
            payload = {"entity_id": entity_id}
            
            # Home Assistant applies brightness, color names, or color temperature
            if action == "turn_on" and domain == "light":
                if brightness is not None:
                    payload["brightness_pct"] = int(brightness)
                    
                if color is not None:
                    clean_color = str(color).lower().strip()
                    
                    # Intercept shades of white and inject real hardware Kelvin temperatures
                    if clean_color in ["warm white", "warm", "creamy", "cream"]:
                        payload["color_temp_kelvin"] = 2700  # Cozy, golden warm light
                    elif clean_color in ["soft white", "natural white", "daylight"]:
                        payload["color_temp_kelvin"] = 3000  # Balanced, clean white light
                    elif clean_color in ["cool white", "ice white"]:
                        payload["color_temp_kelvin"] = 4500  # Crisp, energetic blue-white
                    else:
                        payload["color_name"] = clean_color  # Fallback to standard color names (red, blue, etc.)
            
            r = requests.post(
                url,
                json=payload,
                headers=self.headers,
                timeout=2
            )
            
            print(f"\n[HA DEBUG] POST {url}")
            print(f"[HA DEBUG] Payload: {payload}")
            print(f"[HA DEBUG] Status Code: {r.status_code}\n")
            
            return r.status_code == 200
        except Exception as e:
            print(f"[HA DEBUG] Exception during request: {e}")
            return False
