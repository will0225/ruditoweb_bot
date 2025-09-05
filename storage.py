# storage.py
import os
from supabase import create_client
from datetime import datetime

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BUCKET = os.getenv("SUPABASE_BUCKET")
UPLOAD_PATH = os.getenv("UPLOAD_ROOT") # Optional local path if needed
BASE_URL = os.getenv("BASE_URL");

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def upload_photo_supabase(item_id: str, file_bytes, index: int) -> str:
    fname = f"{item_id}_{index}.jpg"
    print(fname)
    supabase.storage.from_(BUCKET).upload(
        path=fname,
        file=file_bytes,
        file_options={"content-type": "image/jpeg"}
    )

    return supabase.storage.from_(BUCKET).get_public_url(fname)



def upload_photo(item_id: str, file_bytes: bytes, index: int) -> str:
    # Create folder by year/month
    now = datetime.utcnow()
    year = now.strftime("%Y")
    month = now.strftime("%m")
    folder = os.path.join(UPLOAD_PATH, year, month)
    os.makedirs(folder, exist_ok=True)

    # Save file
    fname = f"{item_id}_{index}.jpg"
    path = os.path.join(folder, fname)
    with open(path, "wb") as f:
        f.write(file_bytes)

    # Return URL
    return f"{BASE_URL}/{year}/{month}/{fname}"