"""
Printer Bridge - Configuration Module
"""

import os
import json

# Thư mục data
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
GCODE_DIR = os.path.join(DATA_DIR, "gcode")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

# Tạo thư mục
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(GCODE_DIR, exist_ok=True)

# Config mặc định
DEFAULT_CONFIG = {
    "printer_ip": "192.168.0.100",
    "printer_port": 3030,
    "mainboard_id": "",
    "mqtt_broker": "103.252.136.112",
    "mqtt_port": 1883,
    "api_key": "4a9124de9687d5a3d9634c2940c64bed5aa4432ecd3785fa0be8284bc90980e7",
    "read_interval": 5,
    "max_files_to_mqtt": 20
}

config = DEFAULT_CONFIG.copy()


def load_config():
    """Load config từ file"""
    global config
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config.update(json.load(f))
            return True
    except Exception as e:
        print(f"Load config error: {e}")
    return False


def save_config():
    """Lưu config vào file"""
    global config
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Save config error: {e}")
        return False
