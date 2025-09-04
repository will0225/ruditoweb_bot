import os
from dotenv import load_dotenv
load_dotenv() 
import json
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters.command import Command
from datetime import datetime
from sequence import next_sequence
from storage import upload_photo
from utils import parse_price_field
from sheets import write_row_to_sheet
from ai_client import classify_item

BOT_TOKEN = os.getenv("BOT_TOKEN")
WHITELIST = set(int(x.strip()) for x in os.getenv("TELEGRAM_WHITELIST","").split(",") if x.strip())
UPLOAD_ROOT = os.getenv("UPLOAD_ROOT","/app/uploads")

import asyncio

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
    


@dp.message(Command(commands=["ping"]))
async def ping_handler(message: Message):
    await message.reply("pong")

    
class NewItemStates(StatesGroup):
    waiting_photos = State()
    waiting_prices = State()
    review = State()

def user_ok(tg_user):
    return tg_user in WHITELIST

@dp.message(Command(commands=["new"]))
async def cmd_new(message: Message, state: FSMContext):
    print(message.from_user.id)
    if not user_ok(message.from_user.id):
        await message.reply("Unauthorized.")
        return
    # create draft
    seq = next_sequence()
    item_id = f"{datetime.utcnow().year}-{seq:04d}"
    await state.update_data(item_id=item_id, photos=[], gender='M', needs_review=False)
    await state.set_state(NewItemStates.waiting_photos)
    await message.reply(f"Started new item. ID {item_id}. Send photos (first = main). When done send /prices.")

@dp.message(lambda msg: msg.photo)
async def handle_photo(message: Message, state: FSMContext):
    if not user_ok(message.from_user.id): return
    data = await state.get_data()
    if not data:
        await message.reply("Send /new to start.")
        return
    photos = data.get("photos", [])

    ph = message.photo[-1]
    file = await bot.get_file(ph.file_id)
    file_bytes = await bot.download_file(file.file_path)

    # upload to Supabase
    url = upload_photo(data["item_id"], file_bytes.read(), len(photos)+1)
    photos.append(url)
    await state.update_data(photos=photos)
    await message.reply(f"Uploaded photo #{len(photos)}. /save when ready or send more.")

@dp.message(Command(commands=["prices"]))
async def cmd_prices(message: Message, state: FSMContext):
    await state.set_state(NewItemStates.waiting_prices)
    await message.reply("Send price(s). Examples: `750`, `750/1000`, `-25%`, `€1000`")

@dp.message(NewItemStates.waiting_prices)
async def handle_price_text(message: Message, state: FSMContext):
    text = message.text.strip()
    data = await state.get_data()
    parsed = parse_price_field(text, context_full_price_cents=data.get('full_cents'))
    # store cents and currency in data
    await state.update_data(full_cents=parsed.get('full_cents'),
                            discounted_cents=parsed.get('discounted_cents'),
                            currency=parsed.get('currency'),
                            needs_review=parsed.get('needs_review') or data.get('needs_review', False))
    await state.set_state(NewItemStates.review)
    await message.reply("Price recorded. /save to write to sheet or /edit price to change.")

@dp.message(Command(commands=["save"]))
async def cmd_save(message: Message, state: FSMContext):
    data = await state.get_data()
    if not data: 
        await message.reply("No draft. Use /new.")
        return
    # build sheet row object with AI classification
    photos = data.get('photos', [])
    if not photos:
        await message.reply("No photos found. Send a photo first.")
        return
    # classify with AI (title, desc, type, category, color, brand, confidences)
    print(photos)
    ai_result = classify_item(photos[0])
    # normalization logic here: set Needs Review if any controlled item is uncertain
    row = {
      'product_id': data['item_id'],
      'main_photo': photos[0],
      'additional_photos': ",".join(photos[1:]),
      'title': ai_result.get('title',''),
      'description': ai_result.get('description',''),
      'type_l1': ai_result.get('type_l1',''),
      'category_l2': ai_result.get('category_l2',''),
      'color': ai_result.get('color',''),
      'gender': data.get('gender','M'),
      'brand': data.get('brand') or ai_result.get('brand',''),
      'supplier': data.get('supplier',''),
      'full_price': data.get('full_cents'),
      'discounted_price': data.get('discounted_cents'),
      'needs_review': data.get('needs_review') or ai_result.get('needs_review', False)
    }
    write_row_to_sheet(row)
    await message.reply(f"Saved item {data['item_id']}. Main photo: {row['main_photo']}")
    await state.clear()


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    # init_db()  # make sure database is initialized
    asyncio.run(dp.start_polling(bot))