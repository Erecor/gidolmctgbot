
import asyncio
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

HOST = "darkhaldwani.aternos.me"
PORT = 50742

CHECK_INTERVAL = 60

ONLINE_THRESHOLD = 2
OFFLINE_THRESHOLD = 2

SERVER = BedrockServer.lookup(
    f"{HOST}:{PORT}"
)

# ==========================
# STATUS
# ==========================

async def get_server_status():
    try:
        status = await asyncio.wait_for(
            SERVER.async_status(),
            timeout=8
        )

        return {
            "online": True,
            "players_online": getattr(
                status,
                "players_online",
                0
            ),
            "players_max": getattr(
                status,
                "players_max",
                0
            ),
        }

    except Exception:
        return {
            "online": False
        }

# ==========================
# COMMANDS
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

    msg = (
        "🟢 Server Online\n\n"
        f"👥 Players: "
        f"{status['players_online']}/"
        f"{status['players_max']}"
    )

    await update.message.reply_text(msg)


async def bang_status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await status_command(
        update,
        context
    )

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

