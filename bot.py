import os
import asyncio
from io import BytesIO
from datetime import datetime
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from dotenv import load_dotenv

# load env
load_dotenv()

# your modules - make sure these exist in your project
from storage import upload_photo         # must accept (item_id, bytes, index) -> public url
from sequence import next_sequence      # optional; fallback used if missing
from ai_client import classify_item     # your ai classification

# Google Sheets pieces omitted here; keep your existing code for append_row
# import gspread / google creds in your original file if needed

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not set in environment")

# ---------------- FSM ----------------
class NewItemStates(StatesGroup):
    waiting_id_or_photo = State()
    waiting_photos = State()
    waiting_prices = State()


# ---------------- Bot & Dispatcher ----------------
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ---------------- Helpers ----------------
def gen_auto_id() -> str:
    """Generate fallback ID if next_sequence not available or fails."""
    try:
        seq = next_sequence()
        return f"{datetime.utcnow().year}-{seq:04d}"
    except Exception:
        return datetime.utcnow().strftime("%Y%m%d%H%M%S")


async def _download_photo_bytes(message: Message) -> Optional[bytes]:
    """
    Download highest-res photo from the incoming message and return bytes.
    Tries multiple fallback methods to be robust across aiogram versions.
    """
    try:
        photo = message.photo[-1]  # highest resolution
    except Exception:
        return None

    file_id = photo.file_id
    try:
        # get file metadata
        file_obj = await bot.get_file(file_id)
        file_path = getattr(file_obj, "file_path", None)
    except Exception as e:
        # couldn't get file meta
        print("DEBUG: bot.get_file() failed:", e)
        file_path = None

    buf = BytesIO()
    # Try methods in order
    try:
        if file_path:
            # preferred: download by file_path
            await bot.download_file(file_path, buf)
        else:
            # fallback: try download by file_id (some aiogram versions accept it)
            await bot.download_file(file_id, buf)
    except Exception as e1:
        # last resort: use bot.get_file + bot.download(file_obj, buf) if available
        try:
            file_obj = await bot.get_file(file_id)
            # some versions allow bot.download(file_obj, destination)
            await bot.download(file_obj, buf)
        except Exception as e2:
            print("DEBUG: all download attempts failed:", e1, e2)
            return None

    buf.seek(0)
    data = buf.read()
    return data


# ---------------- HANDLERS ----------------

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Start flow: accept optional ID or direct photo."""
    await state.clear()
    await state.set_state(NewItemStates.waiting_id_or_photo)
    await state.update_data(photos=[], gender='M', needs_review=False)
    await message.reply(
        "👋 Welcome!\n"
        "Please send a product photo (first = main).\n"
        "If you want a custom product ID, send it BEFORE the photo. Otherwise an ID will be generated automatically."
    )


# If user sends text while waiting for id or photo -> treat as custom ID and move to waiting_photos
@dp.message(NewItemStates.waiting_id_or_photo, F.text)
async def handle_custom_id_before_photo(message: Message, state: FSMContext):
    text = message.text.strip()
    # if user typed commands, ignore
    if text.startswith("/"):
        await message.reply("Please send a plain product ID or a photo.")
        return

    pid = text
    if pid.lower() == "auto":
        pid = gen_auto_id()

    await state.update_data(item_id=pid, photos=[])
    await state.set_state(NewItemStates.waiting_photos)
    await message.reply(f"✅ Product ID set: {pid}\nNow send photos (first = main). When done, send /prices.")


# If user sends a photo as first message (no ID), auto-generate ID and accept the photo
@dp.message(NewItemStates.waiting_id_or_photo, F.photo)
async def handle_first_photo_any_state(message: Message, state: FSMContext):
    data = await state.get_data()
    pid = data.get("item_id")
    if not pid:
        pid = gen_auto_id()
        await state.update_data(item_id=pid)

    # download bytes
    file_bytes = await _download_photo_bytes(message)
    if not file_bytes:
        await message.reply("❌ Failed to download photo from Telegram. Try again.")
        return

    photos = data.get("photos", []) or []
    try:
        url = upload_photo(pid, file_bytes, len(photos) + 1)
    except Exception as e:
        print("DEBUG: upload_photo error:", e)
        await message.reply("❌ Failed to upload photo to storage. Check server logs.")
        return

    photos.append(url)
    await state.update_data(photos=photos)
    # move to waiting_photos so user can continue uploading more photos
    await state.set_state(NewItemStates.waiting_photos)
    await message.reply(f"📸 Photo uploaded as main image for {pid}. Send more photos or /prices to continue.")


# Generic handler for waiting_photos: accept either text (ID not yet set) or photos
@dp.message(NewItemStates.waiting_photos)
async def handle_product_id_or_photo(message: Message, state: FSMContext):
    """
    This handler ensures multiple photos are accepted and that if user hasn't set item_id
    they can send it here as text. Photos are delegated to handle_photo below.
    """
    data = await state.get_data()

    # If text and no item_id -> treat as setting item_id
    if message.text and not data.get("item_id"):
        text = message.text.strip()
        if text.startswith("/"):
            await message.reply("Send product ID (plain text) or a photo.")
            return
        pid = text if text.lower() != "auto" else gen_auto_id()
        await state.update_data(item_id=pid)
        await message.reply(f"✅ Product ID set: {pid}\nNow send photos (first = main). When done, send /prices.")
        return

    # If this message contains a photo -> delegate to the dedicated photo handler
    if message.photo:
        # call dedicated photo handler (so it can be used from multiple places)
        await handle_photo_upload(message, state)
        return

    # Otherwise give hint
    await message.reply("Please send a photo (or send product ID first).")


# Dedicated photo upload handler used by multiple places
async def handle_photo_upload(message: Message, state: FSMContext):
    data = await state.get_data()
    pid = data.get("item_id")
    if not pid:
        # defensive generate
        pid = gen_auto_id()
        await state.update_data(item_id=pid)

    file_bytes = await _download_photo_bytes(message)
    if not file_bytes:
        await message.reply("❌ Failed to download photo. Please try again.")
        return

    photos = data.get("photos") or []
    try:
        url = upload_photo(pid, file_bytes, len(photos) + 1)
    except Exception as e:
        print("DEBUG: upload_photo error:", e)
        await message.reply("❌ Failed to upload photo to server. Contact admin.")
        return

    photos.append(url)
    await state.update_data(photos=photos)
    await message.reply(f"📸 Photo {len(photos)} uploaded. Send more or /prices to continue.")


# Bind the dedicated photo upload handler to messages that are photos (so direct photo messages also work)
@dp.message(NewItemStates.waiting_photos, F.photo)
async def handle_photo(message: Message, state: FSMContext):
    await handle_photo_upload(message, state)


# Allow /prices globally (not tied to specific state) but require at least 1 photo
@dp.message(Command("prices"))
async def cmd_prices(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos") or []
    if not photos:
        await message.reply("❌ You need to upload at least 1 photo before adding prices.")
        return
    await state.set_state(NewItemStates.waiting_prices)
    await message.reply("💰 Send prices (e.g., `750/1000` or `750`) or use /edit_price.")


# Price input handler
@dp.message(NewItemStates.waiting_prices)
async def handle_prices(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        # ignore commands here (unless you want to handle /save etc.)
        return
    # parse price (very permissive)
    try:
        if "/" in text:
            disc, full = text.split("/", 1)
            discounted = float(disc.strip())
            full_price = float(full.strip())
        else:
            full_price = float(text)
            discounted = None
    except Exception:
        await message.reply("⚠️ Price parse error. Send like `750/1000` or `750`.")
        return

    await state.update_data(full_price=full_price, discounted_price=discounted)
    await message.reply(f"✅ Price recorded: full={full_price} discounted={discounted}. Use /save to finish.")


# /save command: checks price & photos present, then runs AI and persist (fill your sheet logic)
@dp.message(Command("save"))
async def cmd_save(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos") or []
    if not photos:
        await message.reply("❌ No photos uploaded.")
        return
    if data.get("full_price") is None:
        await message.reply("❌ Please set price before saving (use /prices).")
        return

    # Example: call your AI classifier - keep controlled lists logic as you already have
    try:
        # choose categories by gender if needed; here passing entire controlled lists as-is
        ai_result, needs_review = classify_item(photos[0], {})  # pass your controlled lists
    except Exception as e:
        print("DEBUG: classify_item error:", e)
        ai_result, needs_review = {"title":"", "description":"", "type":"", "category":"", "color":"", "brand":""}, True

    # TODO: append to Google Sheets (use your existing code)
    # Example reply:
    await message.reply(f"✅ Saved item {data.get('item_id')}. Main photo: {photos[0]}")
    # clear state to allow next product
    await state.clear()


# Cancel
@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.reply("Cancelled.")


# Status
@dp.message(Command("status"))
async def cmd_status(message: Message, state: FSMContext):
    data = await state.get_data()
    await message.reply(f"Current state data:\n{data}")


# ---------------- Main ----------------
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    print("Bot starting...")
    asyncio.run(dp.start_polling(bot))
