import os
import sys
import tinytuya
from phue import Bridge

def init_hue_bridge():
    print("\n--- [Phase 1] Philips Hue Local Link ---")
    print("Instruction: Please press the physical link button on your Hue Bridge NOW.")
    input("Once pressed, press Enter in this terminal to connect...")
    
    try:
        # phue attempts to discover via nupnp local lookup
        b = Bridge() 
        b.connect()
        print(f"[SUCCESS] Connected to Hue Bridge. Target IP: {b.ip}")
        return b.ip
    except Exception as e:
        print(f"\n[NOTE] Auto-discovery hit a snag: {e}")
        print("This is normal if your bridge has local UPnP discovery disabled.")
        ip_input = input("Please type your Hue Bridge's local IP address manually (or press Enter to skip): ").strip()
        if ip_input:
            try:
                b = Bridge(ip_input)
                b.connect()
                print(f"[SUCCESS] Manually linked to Hue Bridge at {ip_input}")
                return ip_input
            except Exception as manual_e:
                print(f"[ERROR] Manual connection failed: {manual_e}")
        return None

def scan_tuya_lan():
    print("\n--- [Phase 1] Tuya / Smart Life Local Scan ---")
    print("Scanning local network for smart plugs/switches...")
    
    # Scans local subnet for broadcast packets
    devices = tinytuya.deviceScan(verbose=False)
    
    if not devices:
        print("[NOTE] No local Tuya devices broadcasting. Ensure devices are on the same subnet.")
        return
        
    print(f"[SUCCESS] Found {len(devices)} local Tuya device(s):")
    for ip, data in devices.items():
        print(f"\n- Device Name/ID: {data['gwId']}")
        print(f"  Local IP: {ip}")
        print(f"  Product Key: {data.get('productKey', 'N/A')}")
        print("  Note: Control requires a 'localKey' extracted via the Tuya Developer platform.")

if __name__ == "__main__":
    hue_ip = init_hue_bridge()
    scan_tuya_lan()
