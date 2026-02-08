import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiohttp import web
import google.generativeai as genai
from dotenv import load_dotenv

# --- INITIALIZATION ---
load_dotenv()
logging.basicConfig(level=logging.INFO)

# Securely pull your tokens from Render/Railway environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# --- MODEL SELECTION (2026 UPDATE) ---
# 'gemini-2.5-flash' is the stable workhorse for 2026
# You can also try 'gemini-3-flash-preview' for the newest experimental features
MODEL_ID = 'gemini-2.5-flash' 

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(MODEL_ID)
chat_sessions = {}

# --- RENDER HEALTH SERVER ---
async def handle_health_check(request):
    return web.Response(text="Bot is online and healthy!", status=200)

async def start_webserver():
    app = web.Application()
    app.router.add_get("/", handle_health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render binds to port 10000 by default
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# --- HANDLERS ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(f"🚀 **Gemini AI Active**\nCurrently using: `{MODEL_ID}`\nI support images, history, and live streaming!")

# Multimodal (Image) Support
@dp.message(F.photo)
async def handle_image(message: types.Message):
    sent_msg = await message.reply("📸 Analyzing your image...")
    
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    photo_bytes = await bot.download_file(file.file_path)
    
    img_data = {"mime_type": "image/jpeg", "data": photo_bytes.getvalue()}
    prompt = message.caption if message.caption else "What is in this image?"
    
    try:
        response = model.generate_content([prompt, img_data])
        # Named arguments text=, chat_id=, message_id= fix Pydantic errors
        await bot.edit_message_text(
            text=response.text,
            chat_id=message.chat.id,
            message_id=sent_msg.message_id
        )
    except Exception as e:
        await bot.edit_message_text(
            text=f"❌ Error: {str(e)}",
            chat_id=message.chat.id,
            message_id=sent_msg.message_id
        )

# Chat with Streaming Support
@dp.message(F.text)
async def handle_chat(message: types.Message):
    # Retrieve or create session for history
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
            
            # Update UI every 8 chunks to avoid Telegram rate limits
            if chunk_count % 8 == 0:
                await bot.edit_message_text(
                    text=full_text + " ▌", 
                    chat_id=message.chat.id, 
                    message_id=sent_msg.message_id
                )
        
        # Final clean update
        await bot.edit_message_text(
            text=full_text, 
            chat_id=message.chat.id, 
            message_id=sent_msg.message_id
        )
    except Exception as e:
        await bot.edit_message_text(
            text=f"❌ Error: {str(e)}",
            chat_id=message.chat.id, 
            message_id=sent_msg.message_id
        )

# --- EXECUTION ---
async def main():
    # Drop pending updates to resolve ConflictErrors
    await bot.delete_webhook(drop_pending_updates=True)
    
    await asyncio.gather(
        dp.start_polling(bot),
        start_webserver()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")
