# -*- coding: utf-8 -*-
"""Test spawn time calculation"""

from datetime import datetime, timedelta, timezone

GMT_PLUS_7 = timezone(timedelta(hours=7))

def calculate_spawn_time(kill_time_str: str, interval_hours: int):
    now = datetime.now(GMT_PLUS_7)
    print(f"Current time (GMT+7): {now.strftime('%Y-%m-%d %H:%M:%S')}")

    # Parse kill time (HH:MM)
    parts = kill_time_str.split(":")
    kill_hour = int(parts[0])
    kill_minute = int(parts[1]) if len(parts) > 1 else 0

    # Create kill time datetime for today
    kill_time = now.replace(hour=kill_hour, minute=kill_minute, second=0, microsecond=0)
    print(f"Kill time (if today): {kill_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # If kill time is in the future (hasn't happened today yet), it was yesterday
    if kill_time > now:
        kill_time = kill_time - timedelta(days=1)
        print(f"Kill time adjusted to yesterday: {kill_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Calculate spawn time by adding interval
    spawn_time = kill_time + timedelta(hours=interval_hours)
    print(f"Spawn time (kill + {interval_hours}h): {spawn_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # If spawn time is still in the past, keep adding interval until it's in the future
    while spawn_time <= now:
        spawn_time = spawn_time + timedelta(hours=interval_hours)
        print(f"Spawn time adjusted (+{interval_hours}h): {spawn_time.strftime('%Y-%m-%d %H:%M:%S')}")

    diff = spawn_time - now
    total_seconds = int(diff.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    print(f"Countdown: {hours:02d}:{minutes:02d}:{seconds:02d}")
    return spawn_time

# Test cases
print("=" * 50)
print("Test: Timitris - kill_time=17:03, interval=8h")
print("=" * 50)
calculate_spawn_time("17:03", 8)

print("\n" + "=" * 50)
print("Test: Felis - kill_time=21:20, interval=3h")
print("=" * 50)
calculate_spawn_time("21:20", 3)

print("\n" + "=" * 50)
print("Test: Pan Narod - kill_time=20:06, interval=5h")
print("=" * 50)
calculate_spawn_time("20:06", 5)
