import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiohttp import web
import google.generativeai as genai
from dotenv import load_dotenv

# --- SETUP ---
load_dotenv()
logging.basicConfig(level=logging.INFO)

# Fetch keys from Render Environment Variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# --- GEMINI CONFIG ---
genai.configure(api_key=GEMINI_API_KEY)

# Use the correct model string for 2026
# Try 'gemini-3-flash-preview' or 'gemini-2.5-flash'
MODEL_NAME = 'gemini-3-flash-preview' 
model = genai.GenerativeModel(MODEL_NAME)
chat_sessions = {}

# --- RENDER HEALTH CHECK ---
async def handle_health_check(request):
    return web.Response(text="Bot is Alive!", status=200)

async def start_webserver():
    app = web.Application()
    app.router.add_get("/", handle_health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# --- BOT HANDLERS ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(f"✨ **Gemini 3 Advanced** is online using {MODEL_NAME}!")

@dp.message(F.photo)
async def handle_image(message: types.Message):
    sent_msg = await message.reply("🎨 Analyzing image...")
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    photo_bytes = await bot.download_file(file.file_path)
    
    img_data = {"mime_type": "image/jpeg", "data": photo_bytes.getvalue()}
    prompt = message.caption if message.caption else "Describe this image."
    
    try:
        response = model.generate_content([prompt, img_data])
        await bot.edit_message_text(
            text=response.text,
            chat_id=message.chat.id,
            message_id=sent_msg.message_id
        )
    except Exception as e:
        await bot.edit_message_text(text=f"❌ Image Error: {str(e)}", chat_id=message.chat.id, message_id=sent_msg.message_id)

@dp.message(F.text)
async def handle_chat(message: types.Message):
    if message.chat.id not in chat_sessions:
        chat_sessions[message.chat.id] = model.start_chat(history=[])
    
    sent_msg = await message.answer("▌")
    full_text = ""
    chunk_count = 0
    
    try:
        response = chat_sessions[message.chat.id].send_message(message.text, stream=True)
        for chunk in response:
            full_text += chunk.text
            chunk_count += 1
            if chunk_count % 8 == 0:
                await bot.edit_message_text(
                    text=full_text + " ▌", 
                    chat_id=message.chat.id, 
                    message_id=sent_msg.message_id
                )
        await bot.edit_message_text(text=full_text, chat_id=message.chat.id, message_id=sent_msg.message_id)
    except Exception as e:
        await bot.edit_message_text(text=f"❌ Error: {str(e)}", chat_id=message.chat.id, message_id=sent_msg.message_id)

# --- MAIN ---
async def main():
    # Drop pending updates to resolve ConflictErrors seen in logs
    await bot.delete_webhook(drop_pending_updates=True)
    await asyncio.gather(dp.start_polling(bot), start_webserver())

if __name__ == "__main__":
    asyncio.run(main())
