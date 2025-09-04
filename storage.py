# storage.py
import os
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BUCKET = os.getenv("SUPABASE_BUCKET")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def upload_photo(item_id: str, file_bytes, index: int) -> str:
    fname = f"{item_id}_{index}.jpg"
    print(fname)
    supabase.storage.from_(BUCKET).upload(
        path=fname,
        file=file_bytes,
        file_options={"content-type": "image/jpeg"}
    )

    return supabase.storage.from_(BUCKET).get_public_url(fname)

