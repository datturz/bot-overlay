# -*- coding: utf-8 -*-
"""
Configuration for Lineage2M Boss Timer v2
"""

import os
import sys
from datetime import timezone, timedelta
from dotenv import load_dotenv

# Handle PyInstaller bundled files
def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        # Running as compiled executable
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

# Load .env from bundled location or current directory
env_path = get_resource_path('.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# Timezone GMT+7 (Jakarta, Bangkok, Vietnam)
GMT_PLUS_7 = timezone(timedelta(hours=7))

# App settings
APP_TITLE = "L2M Boss Timer"
APP_VERSION = "2.3.0"

# Timer settings
WARNING_MINUTES_YELLOW = 30  # Yellow warning 30 minutes before spawn
WARNING_MINUTES_RED = 10     # Red warning 10 minutes before spawn

# UI Settings
OVERLAY_OPACITY = 0.85
WINDOW_WIDTH = 400
WINDOW_HEIGHT = 500
OVERLAY_MIN_WIDTH = 300
OVERLAY_MIN_HEIGHT = 200
