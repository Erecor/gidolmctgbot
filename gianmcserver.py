import asyncio
import aiohttp
from datetime import datetime

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ==========================
# CONFIG
# ==========================

BOT_TOKEN = "8921983178:AAGtkbi1tLNo9qA9CHpD4KdsxLZw6ut3hkY"
CHAT_ID = -1004273685959

HOST = "halkehalke.aternos.me"
PORT = 50742

CHECK_INTERVAL = 30
ONLINE_THRESHOLD = 2
OFFLINE_THRESHOLD = 2

# ==========================
# STATUS (dual API)
# ==========================

async def query_mcsrvstat(session: aiohttp.ClientSession) -> dict | None:
    url = f"https://api.mcsrvstat.us/bedrock/3/{HOST}:{PORT}"
    headers = {"User-Agent": "TelegramMCBot/1.0"}
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10), headers=headers) as r:
            if r.status != 200:
                return None
            data = await r.json()
            return {
                "online": data.get("online", False),
                "players_online": data.get("players", {}).get("online",
            
