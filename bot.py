import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiohttp import web
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()

# Gemini Config
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')
chat_sessions = {}

# --- [NEW] HEALTH CHECK FOR RENDER/UPTIME ROBOT ---
async def handle_health_check(request):
    return web.Response(text="Bot is Alive!", status=200)

async def start_webserver():
    app = web.Application()
    app.router.add_get("/", handle_health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render provides the PORT environment variable automatically
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Web server started on port {port}")

# --- [GEMINI LOGIC] ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("✨ Gemini Advanced is Online!\nSend a message or a photo.")

@dp.message(F.text)
async def handle_chat(message: types.Message):
    if message.chat.id not in chat_sessions:
        chat_sessions[message.chat.id] = model.start_chat(history=[])
    
    sent_msg = await message.answer("▌")
    full_text = ""
    try:
        response = chat_sessions[message.chat.id].send_message(message.text, stream=True)
        for chunk in response:
            full_text += chunk.text
            # Simple streaming: update every few chunks
            if len(full_text) % 10 == 0:
                await bot.edit_message_text(full_text + " ▌", message.chat.id, sent_msg.message_id)
        await bot.edit_message_text(full_text, message.chat.id, sent_msg.message_id)
    except Exception as e:
        await bot.edit_message_text(f"❌ Error: {e}", message.chat.id, sent_msg.message_id)

# --- MAIN RUNNER ---
async def main():
    # Run both the bot and the web server concurrently
    await asyncio.gather(
        dp.start_polling(bot),
        start_webserver()
    )

if __name__ == "__main__":
    asyncio.run(main())
