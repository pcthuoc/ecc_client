"""
Printer Bridge - SDCP Protocol Module
"""

import uuid
import time
from config import config

# Status mapping
STATUS_MAP = {
    0: "idle",
    1: "homing",
    2: "dropping",
    3: "printing",
    4: "lifting",
    5: "pausing",
    6: "paused",
    7: "stopping",
    8: "stopped",
    9: "complete",
    10: "file_checking",
    12: "recovery",
    13: "printing",
    15: "loading",
    16: "preheating",
    20: "leveling",
}

# Command codes
CMD_STATUS = 0
CMD_START_PRINT = 128
CMD_PAUSE_PRINT = 129
CMD_STOP_PRINT = 130
CMD_RESUME_PRINT = 131
CMD_FILE_LIST = 258
CMD_CONTROL_DEVICE = 403


def create_sdcp_message(cmd, data=None):
    """Tạo tin nhắn SDCP"""
    return {
        "Id": str(uuid.uuid4()),
        "Data": {
            "Cmd": cmd,
            "Data": data or {},
            "RequestID": str(uuid.uuid4()),
            "MainboardID": config["mainboard_id"],
            "TimeStamp": int(time.time()),
            "From": 0
        },
        "Topic": f"sdcp/request/{config['mainboard_id']}"
    }
