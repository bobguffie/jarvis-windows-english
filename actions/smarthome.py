from services.smarthome import SmartHomeClient

# Initialize the client at module level
ha_client = SmartHomeClient()

# Comprehensive Home Inventory Map — module-level so all functions can share it
DEVICE_MAP = {
    # --- Climate & Appliance Sockets ---
    "aircon": ("switch.aircon_socket", "switch"),
    "plug": ("switch.aircon_socket", "switch"),
    "fan": ("switch.fan_socket_1", "switch"),
    "climate": ("switch.fan_socket_1", "switch"),
    
    # --- Living Room Lighting ---
    "living room": ("light.living_room", "light"),
    "light": ("light.living_room", "light"),
    "front light": ("light.living_room_front", "light"),
    "living room front": ("light.living_room_front", "light"),
    "backlight": ("light.living_room_back", "light"),
    "backlights": ("light.living_room_back", "light"),
    "living room back": ("light.living_room_back", "light"),
    "lamp": ("switch.lamp_socket", "switch"),       # Maps your living room lamp socket
    "living room lamp": ("switch.lamp_socket", "switch"),
    
    # --- Bedroom Lighting ---
    "bedroom": ("light.bedroom", "light"),
    "bedroom light": ("light.bedroom", "light"),
    "left": ("light.left", "light"),                  # Left bedside light
    "left light": ("light.left", "light"),            # Left bedside configuration
    "right": ("light.right", "light"),                # Right bedside light
    "right light": ("light.right", "light"),          # Right bedside configuration
    "main bedroom light": ("light.bedroom", "light"),
    "tv backlights": ("switch.tv_back_lights", "switch"),
    "tv backlight": ("switch.tv_back_lights", "switch"),
    "tv back light": ("switch.tv_back_lights", "switch"),
    
    # --- Hallway Lighting ---
    "hall": ("light.hall", "light"),
    "hall light": ("light.hall", "light"),
    "hallway": ("light.hall", "light"),
    "hall 2": ("light.hall_2", "light"),
    "hall light 2": ("light.hall_2", "light"),
    "hallway 2": ("light.hall_2", "light"),
    
    # --- Entertainment ---
    "shield": ("media_player.shield", "media_player"),
    "nvidia": ("media_player.shield", "media_player")
}


def get_known_devices():
    """Returns a natural language list of all devices JARVIS can control."""
    devices = list(DEVICE_MAP.keys())
    return f"I can control the following: {', '.join(devices)}."


def execute_smarthome_intent(device_keyword, action="toggle", brightness=None, color=None):
    """
    Maps spoken keywords ('aircon', 'fan', 'light') to actual Home Assistant entity IDs
    and executes native hardware commands with optional brightness and color modifiers.
    """
    # Clean and normalize the input text strings
    device_keyword = device_keyword.lower().strip()
    action = action.lower().strip()
    
    if action == "list_devices":
        return get_known_devices()
    
    if action == "check_status":
        return check_device_states(device_keyword)
    
    if device_keyword in DEVICE_MAP:
        entity_id, domain = DEVICE_MAP[device_keyword]
        
        # Translate conversational English into exact Home Assistant API service parameters
        if action in ["on", "turn on", "start"]:
            ha_action = "turn_on"
        elif action in ["off", "turn off", "stop"]:
            ha_action = "turn_off"
        else:
            ha_action = "toggle"
            
        return ha_client.toggle_device(
            entity_id,
            domain=domain,
            action=ha_action,
            brightness=brightness,
            color=color
        )
        
    return False


def check_device_states(device_keyword=None):
    """Queries live Home Assistant states, prioritizing room breakdown lists."""
    from services.smarthome import SmartHomeClient
    ha_client = SmartHomeClient()
    
    clean_keyword = str(device_keyword).lower().strip() if device_keyword else ""
    
    active_devices = []
    target_entities = []
    is_group_query = False
    
    # 1. PRIORITY: Check for room group matches first
    if clean_keyword in ["bedroom", "bedroom lights", "bed room"]:
        is_group_query = True
        target_entities = [
            ("Left Light", "light.left"), 
            ("Right Light", "light.right"),
            ("TV Backlights", "switch.tv_back_lights"), # Corrected ID from image_ed8962.jpg
            ("Main Bedroom Light", "light.bedroom")
        ]
    elif clean_keyword in ["living room", "living room lights", "livingroom"]:
        is_group_query = True
        target_entities = [
            ("Living Room Front Light", "light.living_room_front"), 
            ("Living Room Backlight", "light.living_room_back"), 
            ("Lamp Socket", "switch.lamp_socket")
        ]

    # 2. If it is a room group, scan the live child states
    if is_group_query:
        seen_ids = set()
        for friendly_name, entity_id in target_entities:
            if entity_id in seen_ids:
                continue
            seen_ids.add(entity_id)
            
            state_data = ha_client.get_entity_state(entity_id)
            if state_data and state_data.get("state") == "on":
                active_devices.append(friendly_name)
                
        if active_devices:
            if len(active_devices) == 1:
                return f"The {active_devices[0]} is currently on."
            return f"The following specific lights are currently on: {', '.join(active_devices)}."
        return "Everything in that area is currently switched off."

    # 3. FALLBACK: If it wasn't a room, look it up as a single device keyword
    if device_keyword in DEVICE_MAP:
        entity_id, domain = DEVICE_MAP[device_keyword]
        state_data = ha_client.get_entity_state(entity_id)
        if state_data:
            return f"The {device_keyword} is currently {state_data.get('state', 'unknown')}."
        return f"I couldn't reach the {device_keyword} right now."
        
    return "I couldn't find that device or room in my configuration."
