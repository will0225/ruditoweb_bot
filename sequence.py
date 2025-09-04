# sequence.py
import os
from datetime import datetime
from supabase import create_client

# Load Supabase config from environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase URL or KEY not set in .env")

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Table storing last sequence per year
TABLE_NAME = "counters"  # Columns: year (int, PK), last_seq (int)

def next_sequence() -> int:
    """
    Returns the next sequence number for the current year.
    Handles first-time rows safely and survives Supabase errors.
    """
    year = datetime.utcnow().year

    try:
        # maybe_single() returns None if row doesn't exist
        res = supabase.table(TABLE_NAME).select("*").eq("year", year).maybe_single().execute()
        data = res.data if res and hasattr(res, "data") else None
    except Exception as e:
        print("Supabase query error:", e)
        data = None

    if data:
        seq = data.get("last_seq", 0) + 1
        try:
            supabase.table(TABLE_NAME).update({"last_seq": seq}).eq("year", year).execute()
        except Exception as e:
            print("Supabase update error:", e)
    else:
        seq = 1
        try:
            supabase.table(TABLE_NAME).insert({"year": year, "last_seq": seq}).execute()
        except Exception as e:
            print("Supabase insert error:", e)

    return seq
