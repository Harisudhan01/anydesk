import os
import json
import random
import socket

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".mydesk_config.json")
DEFAULT_RELAY_HOST = "127.0.0.1"  # Default fallback, can be changed in UI
DEFAULT_RELAY_PORT = 8765
DIRECT_CONNECT_PORT = 8766
DEFAULT_JPEG_QUALITY = 60
DEFAULT_FPS_TARGET = 30

def get_or_create_device_id():
    """Generates or loads a persistent 9-digit ID for this machine (like AnyDesk)"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                if "device_id" in data:
                    return data["device_id"]
        except Exception:
            pass
    
    # Generate random 9-digit ID formatted like 123 456 789
    part1 = random.randint(100, 999)
    part2 = random.randint(100, 999)
    part3 = random.randint(100, 999)
    device_id = f"{part1} {part2} {part3}"
    
    try:
        data = {}
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
        data["device_id"] = device_id
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass
        
    return device_id

def generate_session_password():
    """Generates a simple 6-character random security key"""
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(random.choice(chars) for _ in range(6))

def get_local_ip():
    """Detects local LAN IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"
