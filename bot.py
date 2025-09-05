import os
from io import BytesIO
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from dotenv import load_dotenv
load_dotenv()

from storage import upload_photo
from sequence import next_sequence
from ai_client import classify_item

import gspread
from google.oauth2.service_account import Credentials

# ---------------- CONFIG ----------------
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
UPLOAD_ROOT = os.getenv("UPLOAD_ROOT")
BASE_URL = os.getenv("BASE_URL")
GOOGLE_SA_FILE = os.getenv("GOOGLE_CREDENTIALS_JSON_PATH")
SHEET_ID = os.getenv("SHEET_ID")

CONTROLLED_LISTS = {
    "type": ["Shoes", "Clothes", "Bags"],
    "category": ["Men", "Women", "Kids"],
    "color": ["Red", "Blue", "Green"],
    "brand": ["Nike", "Adidas", "Puma"]
}

AUTHORIZED_USERS = [8067976030]  # Telegram IDs

# ---------------- FSM ----------------
class NewItemStates(StatesGroup):
    waiting_product_id = State()
    waiting_photos = State()
    waiting_prices = State()

# ---------------- BOT ----------------
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ---------------- HELPERS ----------------
def user_ok(user_id: int) -> bool:
    return user_id in AUTHORIZED_USERS

def parse_prices(text: str) -> tuple:
    text = text.replace("€", "").strip()
    if "/" in text:
        discounted, full = text.split("/")
        return float(full), float(discounted)
    else:
        return float(text), None

# ---------------- GOOGLE SHEETS ----------------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file(GOOGLE_SA_FILE, scopes=SCOPES)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SHEET_ID)
worksheet = sheet.sheet1

# ---------------- HANDLERS ----------------

# Start new item
@dp.message(Command(commands=["new"]))
async def cmd_new(message: Message, state: FSMContext):
    await state.set_state(NewItemStates.waiting_product_id)
    await state.update_data(photos=[], gender="M", needs_review=False)
    await message.reply("🆔 Send your product ID or type 'auto' to generate automatically.")

# Handle product ID
@dp.message(NewItemStates.waiting_product_id)
async def handle_product_id(message: Message, state: FSMContext):
    pid = message.text.strip()
    if pid.lower() == "auto":
        pid = f"{datetime.utcnow().year}-{next_sequence():04d}"

    await state.update_data(item_id=pid)
    await state.set_state(NewItemStates.waiting_photos)
    await message.reply(
        f"✅ Started new item with ID: {pid}\n"
        "Now send photos (first = main). When done, send /prices."
    )

# Handle photo upload
@dp.message(NewItemStates.waiting_photos, F.photo)
async def handle_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)

    buf = BytesIO()
    await bot.download(file, buf)
    file_bytes = buf.getvalue()

    # Upload to server
    url = upload_photo(data["item_id"], file_bytes, len(photos)+1)
    photos.append(url)
    await state.update_data(photos=photos)
    await message.reply(f"📸 Photo {len(photos)} uploaded. Send more or /prices to continue.")

# Switch to price input
@dp.message(NewItemStates.waiting_photos, Command(commands=["prices"]))
async def cmd_prices(message: Message, state: FSMContext):
    data = await state.get_data()
    if not data.get("photos"):
        await message.reply("❌ Upload at least 1 photo before adding prices.")
        return
    await state.set_state(NewItemStates.waiting_prices)
    await message.reply("💰 Send prices like `750/1000`, `750`, or `-25%`.")

# Handle price messages
@dp.message(NewItemStates.waiting_prices)
async def handle_prices(message: Message, state: FSMContext):
    try:
        full_price, discounted_price = parse_prices(message.text.strip())
    except Exception:
        full_price, discounted_price = None, None

    await state.update_data(full_price=full_price, discounted_price=discounted_price)
    await message.reply(f"✅ Price recorded: Full={full_price}, Discounted={discounted_price}. Send more or /save to finish.")

# Save item
@dp.message(NewItemStates.waiting_prices, Command(commands=["save"]))
async def cmd_save(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    if not photos:
        await message.reply("❌ No photos uploaded.")
        return

    full_price = data.get("full_price")
    discounted_price = data.get("discounted_price")

    # AI Classification
    ai_result, needs_review = classify_item(photos[0], CONTROLLED_LISTS)

    row = [
        data["item_id"],                # A
        photos[0],                      # B
        ",".join(photos[1:]),           # C
        ai_result["title"],             # D
        ai_result["description"],       # E
        ai_result["type"],              # F
        ai_result["category"],          # G
        ai_result["color"],             # H
        data.get("gender", "M"),        # I
        ai_result["brand"] or "",       # J
        "",                              # K Supplier
        full_price,                     # L
        discounted_price,               # M
        "TRUE" if needs_review else "FALSE"  # N
    ]

    worksheet.append_row(row, value_input_option="USER_ENTERED")
    await message.reply(f"✅ Item {data['item_id']} saved.\nMain Photo URL: {photos[0]}")
    await state.clear()

# Cancel creation
@dp.message(Command(commands=["cancel"]))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.reply("Item creation cancelled.")

# Status check
@dp.message(Command(commands=["status"]))
async def cmd_status(message: Message, state: FSMContext):
    data = await state.get_data()
    await message.reply(f"Current data: {data}")

# ---------------- MAIN ----------------
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    print("Bot is running...")
    asyncio.run(dp.start_polling(bot))
