# -*- coding: utf-8 -*-
"""
Test database connection and find correct table name
"""

from supabase import create_client

SUPABASE_URL = "https://nvwbebcnaofggyuvlpxx.supabase.co/"
SUPABASE_KEY = "sb_publishable_mOKc8ZfLs7v5gnUq2SFGQQ_CnW752vN"

print("Connecting to Supabase...")
client = create_client(SUPABASE_URL, SUPABASE_KEY)
print("Connected!")

# Try different table names
table_names = ["boss_timers", "bosses", "boss", "timers", "boss_timer", "l2m_boss", "l2m_bosses"]

for table_name in table_names:
    try:
        result = client.table(table_name).select("*").limit(5).execute()
        print(f"\n[SUCCESS] Table '{table_name}' found!")
        print(f"  Data count: {len(result.data)}")
        if result.data:
            print(f"  Sample data: {result.data[0]}")
        break
    except Exception as e:
        print(f"[FAILED] Table '{table_name}': {e}")
