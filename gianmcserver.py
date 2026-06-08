import asyncio
from datetime import datetime

from mcstatus import JavaServer
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
CHAT_ID = -1004273685959  # Your Telegram chat ID
SERVER_ADDRESS = "darkhaldwani.aternos.me"
CHECK_INTERVAL = 30

# ==========================
# SERVER STATUS
# ==========================

async def get_server_status():
    try:
        server = JavaServer.lookup(SERVER_ADDRESS)
        status = await server.async_status()

        players = []

        if status.players.sample:
            players = [p.name for p in status.players.sample]

        return {
            "online": True,
            "players_online": status.players.online,
            "players_max": status.players.max,
            "latency": round(status.latency),
            "players": players,
        }

    except Exception:
        return {
            "online": False
        }

# ==========================
# STATUS COMMAND
# ==========================

async def status_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    status = await get_server_status()

    if not status["online"]:
        await update.message.reply_text(
            "🔴 Server Offline"
        )
        return

    player_text = (
        ", ".join(status["players"])
        if status["players"]
        else "Unavailable"
    )

    msg = (
        "🟢 Server Online\n\n"
        f"👥 Players: {status['players_online']}/{status['players_max']}\n"
        f"📶 Latency: {status['latency']} ms\n"
        f"🎮 Online: {player_text}"
    )

    await update.message.reply_text(msg)

# ==========================
# !status SUPPORT
# ==========================

async def bang_status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await status_command(update, context)

# ==========================
# MONITOR LOOP
# ==========================

async def monitor_server(app):
    previous_state = None

    while True:

        status = await get_server_status()
        current_state = status["online"]

        if previous_state is None:
            previous_state = current_state

        elif current_state != previous_state:

            now = datetime.now().strftime("%H:%M:%S")

            if current_state:

                if status["players"]:
                    starter = status["players"][0]
                    player_info = (
                        f"\n🎮 First detected player: {starter}"
                    )
                else:
                    player_info = ""

                message = (
                    "🟢 Server Online\n\n"
                    "A new session has started.\n"
                    f"⏰ Time: {now}\n"                
                    f"📶 Latency: {status['latency']} ms"
                   
                )

            else:

                message = (
                    "🔴 Server Offline"
                )

            await app.bot.send_message(
                chat_id=CHAT_ID,
                text=message
            )

            previous_state = current_state

        await asyncio.sleep(CHECK_INTERVAL)

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
        CommandHandler("status", status_command)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex(r"^!status$"),
            bang_status
        )
    )

    print("Bot is running...")

    app.run_polling()

if __name__ == "__main__":
    main()

