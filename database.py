# -*- coding: utf-8 -*-
"""
Database operations for Lineage2M Boss Timer v2
Using existing database schema with kill_time + interval
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY, GMT_PLUS_7

# FFA (Free For All) boss list - high value bosses anyone can kill
FFA_BOSSES = [
    "Samuel", "Glaki", "Flynt", "Dragon Beast", "Cabrio", "Hisilrome",
    "Mirror of Oblivion", "Landor", "Haff", "Andras", "Olkuth", "Orfen"
]


class Database:
    def __init__(self):
        self.client: Optional[Client] = None
        self.connected = False
        self.table_name = "bosses"  # Table name in existing database

    def connect(self) -> bool:
        """Connect to Supabase"""
        try:
            if not SUPABASE_URL or not SUPABASE_KEY:
                print("Supabase credentials not configured")
                return False
            self.client = create_client(SUPABASE_URL, SUPABASE_KEY)
            self.connected = True
            return True
        except Exception as e:
            print(f"Failed to connect to Supabase: {e}")
            self.connected = False
            return False

    def get_all_bosses(self) -> List[Dict]:
        """Get all bosses from the database"""
        try:
            result = self.client.table(self.table_name).select("*").execute()
            return result.data or []
        except Exception as e:
            print(f"Get bosses error: {e}")
            return []

    def get_bosses_by_type(self, boss_type: str) -> List[Dict]:
        """Get bosses filtered by type (ours/invasion/ffa)"""
        try:
            if boss_type == "ffa":
                # FFA is not a database type, filter by name
                result = self.client.table(self.table_name).select("*").execute()
                return [b for b in (result.data or []) if b.get("name") in FFA_BOSSES]
            else:
                result = self.client.table(self.table_name).select("*").eq("type", boss_type).execute()
                return result.data or []
        except Exception as e:
            print(f"Get bosses by type error: {e}")
            return []

    def calculate_spawn_time(self, kill_time_str: str, interval_hours: int, allow_spawn_display: bool = True) -> datetime:
        """
        Calculate spawn time from kill_time + interval
        kill_time is in HH:MM format (GMT+7)
        Returns spawn time as datetime with GMT+7 timezone

        Logic:
        1. Parse kill_time as a time today
        2. If kill_time is in the future (hasn't happened today), it was yesterday
        3. spawn_time = kill_time + interval
        4. If spawn_time just passed (within 1 min), keep it to show SPAWN!
        5. If spawn_time passed more than 1 min ago, add interval for next cycle
        """
        now = datetime.now(GMT_PLUS_7)

        # Parse kill time (HH:MM)
        try:
            parts = kill_time_str.split(":")
            kill_hour = int(parts[0])
            kill_minute = int(parts[1]) if len(parts) > 1 else 0
        except (ValueError, IndexError):
            # Default to current time if parsing fails
            kill_hour = now.hour
            kill_minute = now.minute

        # Create kill time datetime for today
        kill_time = now.replace(hour=kill_hour, minute=kill_minute, second=0, microsecond=0)

        # If kill time is in the future (hasn't happened today yet), it was yesterday
        if kill_time > now:
            kill_time = kill_time - timedelta(days=1)

        # Calculate spawn time by adding interval
        spawn_time = kill_time + timedelta(hours=interval_hours)

        # If spawn time has passed
        if spawn_time <= now:
            time_since_spawn = (now - spawn_time).total_seconds()

            # If within 3 minutes of spawn, keep showing SPAWN!
            if allow_spawn_display and time_since_spawn <= 180:
                return spawn_time  # Will result in negative countdown = SPAWN!

            # Otherwise, calculate next cycle
            while spawn_time <= now:
                spawn_time = spawn_time + timedelta(hours=interval_hours)

        return spawn_time

    def calculate_countdown_seconds(self, kill_time_str: str, interval_hours: int) -> int:
        """
        Calculate countdown in seconds
        Returns seconds until spawn (positive = future, negative = past)
        """
        spawn_time = self.calculate_spawn_time(kill_time_str, interval_hours)
        now = datetime.now(GMT_PLUS_7)
        diff = spawn_time - now
        return int(diff.total_seconds())

    def validate_pin(self, pin: str) -> bool:
        """Validate PIN against pin_validation table in Supabase"""
        try:
            result = self.client.table("pin_validation").select("pin").eq("pin", pin).execute()
            return len(result.data) > 0
        except Exception as e:
            print(f"PIN validation error: {e}")
            return False


# Global database instance
db = Database()
