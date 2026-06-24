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

CHECK_INTERVAL = 60
ONLINE_THRESHOLD = 2
OFFLINE_THRESHOLD = 2

# ==========================
# STATUS (dual API)
# ==========================

async def query_mcsrvstat(session: aiohttp.ClientSession) -> dict | None:
    """mcsrvstat.us — no auth, 5-min cache, Bedrock endpoint."""
    url = f"https://api.mcsrvstat.us/bedrock/3/{HOST}:{PORT}"
    headers = {"User-Agent": "TelegramMCBot/1.0"}
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10), headers=headers) as r:
            if r.status != 200:
                return None
            data = await r.json()
            return {
                "online": data.get("online", False),
                "players_online": data.get("players", {}).get("online", 0),
                "players_max": data.get("players", {}).get("max", 0),
            }
    except Exception:
        return None


async def query_mcstatus_io(session: aiohttp.ClientSession) -> dict | None:
    """mcstatus.io — no auth required, Bedrock endpoint."""
    url = f"https://api.mcstatus.io/v2/status/bedrock/{HOST}:{PORT}"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status != 200:
                return None
            data = await r.json()
            players = data.get("players") or {}
            return {
                "online": data.get("online", False),
                "players_online": players.get("online", 0),
                "players_max": players.get("max", 0),
            }
    except Exception:
        return None


async def get_server_status() -> dict:
    """
    Query both APIs concurrently.
    Server is online only if BOTH agree it's online.
    Falls back to whichever API responded if one times out.
    """
    async with aiohttp.ClientSession() as session:
        r1, r2 = await asyncio.gather(
            query_mcsrvstat(session),
            query_mcstatus_io(session),
        )

    results = [r for r in (r1, r2) if r is not None]

    if not results:
        # Both APIs failed — treat as unknown, don't flip state
        return {"online": None}

    if len(results) == 1:
        # Only one API responded — use it but don't trust fully
        return results[0]

    # Both responded — require consensus to report online
    both_online = all(r["online"] for r in results)
    # Use player count from whichever shows more (more likely to be accurate)
    best = max(results, key=lambda r: r.get("players_online", 0))
    return {
        "online": both_online,
        "players_online": best["players_online"],
        "players_max": best["players_max"],
    }

# ==========================
# COMMANDS
# ==========================

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = await get_server_status()

    if status["online"] is None:
        await update.message.reply_text("⚠️ Could not reach status APIs. Try again shortly.")
        return

    if not status["online"]:
        await update.message.reply_text("🔴 Server Offline")
        return

    msg = (
        "🟢 Server Online\n\n"
        f"👥 Players: {status['players_online']}/{status['players_max']}"
    )
    await update.message.reply_text(msg)


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

            # If both APIs are unreachable, skip this tick entirely
            if status["online"] is None:
                print("Both APIs unreachable, skipping tick.")
                await asyncio.sleep(CHECK_INTERVAL)
                continue

            if status["online"]:
                online_streak += 1
                offline_streak = 0
            else:
                offline_streak += 1
                online_streak = 0

            # OFFLINE -> ONLINE
            if not server_online and online_streak >= ONLINE_THRESHOLD:
                server_online = True
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
                await app.bot.send_message(chat_id=CHAT_ID, text="🔴 Server Offline")

        except Exception as e:
            print("Monitor error:", e)

        await asyncio.sleep(CHECK_INTERVAL)

# ==========================
# STARTUP
# ==========================

async def post_init(app):
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
    while True:

        try:

            status = await get_server_status()

            if status["online"]:
                online_streak += 1
                offline_streak = 0
            else:
                offline_streak += 1
                online_streak = 0

            # OFFLINE -> ONLINE
            if (
                not server_online
                and online_streak >= ONLINE_THRESHOLD
            ):
                server_online = True

                now = datetime.now().strftime(
                    "%H:%M:%S"
                )

                await app.bot.send_message(
                    chat_id=CHAT_ID,
                    text=(
                        "🟢 Server Online\n\n"
                        f"⏰ Time: {now}\n"
                        f"👥 Players: "
                        f"{status['players_online']}/"
                        f"{status['players_max']}"
                    )
                )

            # ONLINE -> OFFLINE
            elif (
                server_online
                and offline_streak >= OFFLINE_THRESHOLD
            ):
                server_online = False

                await app.bot.send_message(
                    chat_id=CHAT_ID,
                    text="🔴 Server Offline"
                )

        except Exception as e:
            print(
                "Monitor error:",
                e
            )

        await asyncio.sleep(
            CHECK_INTERVAL
        )

# ==========================
# STARTUP
# ==========================

async def post_init(app):
    asyncio.create_task(
        monitor_server(app)
    )

def main():

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(
        CommandHandler(
            "status",
            status_command
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT
            & filters.Regex(
                r"^\s*!status\s*$"
            ),
            bang_status
        )
    )

    print(
        f"Monitoring {HOST}:{PORT}"
    )

    app.run_polling()

if __name__ == "__main__":
    main()

