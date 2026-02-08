import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiohttp import web
import google.generativeai as genai
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()
logging.basicConfig(level=logging.INFO)

# Fetch keys securely from Render Environment Variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Use Gemini 3 Flash (Latest for 2026)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-3-flash') 
chat_sessions = {}

# --- HEALTH CHECK FOR RENDER ---
async def handle_health_check(request):
    return web.Response(text="Bot is Alive!", status=200)

async def start_webserver():
    app = web.Application()
    app.router.add_get("/", handle_health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render uses port 10000 or the $PORT variable
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Health check server running on port {port}")

# --- AI HANDLERS ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("✨ **Gemini 3 Advanced** is active.\nI support history, images, and live streaming!")

# Multimodal Image Support
@dp.message(F.photo)
async def handle_image(message: types.Message):
    sent_msg = await message.reply("🎨 Analyzing image...")
    
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    photo_bytes = await bot.download_file(file.file_path)
    
    img_data = {"mime_type": "image/jpeg", "data": photo_bytes.getvalue()}
    prompt = message.caption if message.caption else "Describe this image in detail."
    
    try:
        response = model.generate_content([prompt, img_data])
        # FIX: Named arguments to prevent Pydantic errors
        await bot.edit_message_text(
            text=response.text,
            chat_id=message.chat.id,
            message_id=sent_msg.message_id
        )
    except Exception as e:
        await bot.edit_message_text(text=f"❌ Error: {str(e)}", chat_id=message.chat.id, message_id=sent_msg.message_id)

# Streaming Chat Support
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
            
            # Update every 8 chunks to respect Telegram rate limits
            if chunk_count % 8 == 0:
                await bot.edit_message_text(
                    text=full_text + " ▌", 
                    chat_id=message.chat.id, 
                    message_id=sent_msg.message_id
                )
        
        # Final update
        await bot.edit_message_text(
            text=full_text, 
            chat_id=message.chat.id, 
            message_id=sent_msg.message_id
        )
    except Exception as e:
        await bot.edit_message_text(text=f"❌ Error: {str(e)}", chat_id=message.chat.id, message_id=sent_msg.message_id)

# --- MAIN RUNNER ---
async def main():
    # Drop pending updates to avoid TelegramConflictError
    await bot.delete_webhook(drop_pending_updates=True)
    
    await asyncio.gather(
        dp.start_polling(bot),
        start_webserver()
    )

if __name__ == "__main__":
    asyncio.run(main())
