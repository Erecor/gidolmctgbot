import asyncio
import aiohttp
from datetime import datetime
from mcstatus import BedrockServer

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

# Require N consecutive agreeing checks before alerting
ONLINE_THRESHOLD = 3
OFFLINE_THRESHOLD = 3

SERVER = BedrockServer.lookup(f"{HOST}:{PORT}")

# ==========================
# 3 SOURCES
# ==========================

async def query_direct() -> bool | None:
    """Direct UDP ping — real-time but can flicker during Aternos startup."""
    try:
        await asyncio.wait_for(SERVER.async_status(), timeout=8)
        return True
    except Exception:
        return False


async def query_mcsrvstat(session: aiohttp.ClientSession) -> bool | None:
    url = f"https://api.mcsrvstat.us/bedrock/3/{HOST}:{PORT}"
    headers = {"User-Agent": "TelegramMCBot/1.0"}
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10), headers=headers) as r:
            if r.status != 200:
                return None
            data = await r.json()
            return bool(data.get("online", False))
    except Exception:
        return None


async def query_mcstatus_io(session: aiohttp.ClientSession) -> bool | None:
    url = f"https://api.mcstatus.io/v2/status/bedrock/{HOST}:{PORT}"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status != 200:
                return None
            data = await r.json()
            return bool(data.get("online", False))
    except Exception:
        return None


async def get_server_status() -> dict:
    """
    Poll all 3 sources concurrently.
    Returns:
      online=True   — majority (2+/3) say online
      online=False  — majority (2+/3) say offline
      online=None   — too much disagreement, skip this tick
    """
    async with aiohttp.ClientSession() as session:
        direct, r1, r2 = await asyncio.gather(
            query_direct(),
            query_mcsrvstat(session),
            query_mcstatus_io(session),
        )

    votes = [v for v in (direct, r1, r2) if v is not None]

    if len(votes) < 2:
        # Fewer than 2 sources responded — not enough data
        return {"online": None, "players_online": 0, "players_max": 0}

    online_votes = sum(1 for v in votes if v)
    offline_votes = len(votes) - online_votes

    if online_votes > offline_votes:
        # Majority says online — get player count from APIs
        async with aiohttp.ClientSession() as session:
            r1_full, r2_full = await asyncio.gather(
                _query_mcsrvstat_full(session),
                _query_mcstatus_io_full(session),
            )
        results = [r for r in (r1_full, r2_full) if r]
        best = max(results, key=lambda r: r.get("players_online", 0)) if results else {}
        return {
            "online": True,
            "players_online": best.get("players_online", 0),
            "players_max": best.get("players_max", 0),
        }
    elif offline_votes > online_votes:
        return {"online": False, "players_online": 0, "players_max": 0}
    else:
        # Exact tie (1 vs 1) — skip tick, don't change state
        return {"online": None, "players_online": 0, "players_max": 0}


async def _query_mcsrvstat_full(session: aiohttp.ClientSession) -> dict | None:
    url = f"https://api.mcsrvstat.us/bedrock/3/{HOST}:{PORT}"
    headers = {"User-Agent": "TelegramMCBot/1.0"}
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10), headers=headers) as r:
            if r.status != 200:
                return None
            data = await r.json()
            return {
                "players_online": data.get("players", {}).get("online", 0),
                "players_max": data.get("players", {}).get("max", 0),
            }
    except Exception:
        return None


async def _query_mcstatus_io_full(session: aiohttp.ClientSession) -> dict | None:
    url = f"https://api.mcstatus.io/v2/status/bedrock/{HOST}:{PORT}"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status != 200:
                return None
            data = await r.json()
            players = data.get("players") or {}
            return {
                "players_online": players.get("online", 0),
                "players_max": players.get("max", 0),
            }
    except Exception:
        return None

# ==========================
# COMMANDS
# ==========================

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = await get_server_status()

    if status["online"] is None:
        await update.message.reply_text("⚠️ Sources are split, try again in a moment.")
        return

    if not status["online"]:
        await update.message.reply_text("🔴 Server Offline")
        return

    await update.message.reply_text(
        "🟢 Server Online\n\n"
        f"👥 Players: {status['players_online']}/{status['players_max']}"
    )


async def bang_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await status_command(update, context)

# ==========================
# MONITOR
# ==========================

async def monitor_server(app):
    server_online = False
    online_streak = 0
    offline_streak = 0

    while True:
        try:
            status = await get_server_status()

            if status["online"] is None:
                # Sources disagree — freeze streaks, don't change state
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Sources split, skipping tick.")
                await asyncio.sleep(CHECK_INTERVAL)
                continue

            if status["online"]:
                online_streak += 1
                offline_streak = 0
            else:
                offline_streak += 1
                online_streak = 0

            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] "
                f"online={status['online']} | "
                f"streak +{online_streak}✅ -{offline_streak}❌"
            )

            # OFFLINE -> ONLINE
            if not server_online and online_streak >= ONLINE_THRESHOLD:
                server_online = True
                online_streak = 0  # reset so it doesn't re-trigger
                now = datetime.now().strftime("%H:%M:%S")
                await app.bot.send_message(
                    chat_id=CHAT_ID,
                    text=(
                        "🟢 Server Online\n\n"
                        f"⏰ Time: {now}\n"
                        f"👥 Players: {status['players_online']}/{status['players_max']}"
                    ),
                )

            # ONLINE -> OFFLINE
            elif server_online and offline_streak >= OFFLINE_THRESHOLD:
                server_online = False
                offline_streak = 0  # reset so it doesn't re-trigger
                await app.bot.send_message(
                    chat_id=CHAT_ID,
                    text="🔴 Server Offline"
                )

        except Exception as e:
            print(f"Monitor error: {e}")

        await asyncio.sleep(CHECK_INTERVAL)

# ==========================
# STARTUP
# ==========================

async def post_init(app):
    try:
        await app.bot.send_message(chat_id=CHAT_ID, text="🤖 Bot started! Monitoring server...")
    except Exception as e:
        print("Startup message failed:", e)
    asyncio.create_task(monitor_server(app))


def main():
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex(r"^\s*!status\s*$"),
            bang_status,
        )
    )

    print(f"Monitoring {HOST}:{PORT}")
    app.run_polling()


if __name__ == "__main__":
    main()
