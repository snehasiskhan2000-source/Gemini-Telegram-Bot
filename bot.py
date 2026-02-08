import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiohttp import web
import google.generativeai as genai
from dotenv import load_dotenv

# 1. Setup & Config
load_dotenv()
# Securely fetch keys from Environment Variables (Render/Railway)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# 2. Gemini Configuration
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')
chat_sessions = {}

# 3. Health Check for Render & Uptime Robot
async def handle_health_check(request):
    return web.Response(text="Bot is running smoothly!", status=200)

async def start_webserver():
    app = web.Application()
    app.router.add_get("/", handle_health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# 4. Command Handlers
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("✨ **Gemini Advanced AI** is now online.\nI can remember our chat and see images!")

# 5. Image Support Handler
@dp.message(F.photo)
async def handle_image(message: types.Message):
    sent_msg = await message.reply("🤔 Thinking...")
    
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    photo_bytes = await bot.download_file(file.file_path)
    
    img_data = {"mime_type": "image/jpeg", "data": photo_bytes.getvalue()}
    prompt = message.caption if message.caption else "Describe this image."
    
    try:
        response = model.generate_content([prompt, img_data])
        # FIX: Using explicit keywords to prevent ValidationErrors
        await bot.edit_message_text(
            text=response.text,
            chat_id=message.chat.id,
            message_id=sent_msg.message_id
        )
    except Exception as e:
        await bot.edit_message_text(
            text=f"❌ Image Error: {str(e)}",
            chat_id=message.chat.id,
            message_id=sent_msg.message_id
        )

# 6. Chat Support + Streaming Handler
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
            
            # Stream update every 6 chunks to avoid Telegram rate limits
            if chunk_count % 6 == 0:
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
        await bot.edit_message_text(
            text=f"❌ Error: {str(e)}",
            chat_id=message.chat.id,
            message_id=sent_msg.message_id
        )

# 7. Main Execution
async def main():
    await asyncio.gather(
        dp.start_polling(bot),
        start_webserver()
    )

if __name__ == "__main__":
    asyncio.run(main())
