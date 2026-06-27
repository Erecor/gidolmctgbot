import asyncio
import socket
import struct
import time
import random
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

HOST = "darkhaldwani.aternos.me"
PORT = 50742

CHECK_INTERVAL = 30
ONLINE_THRESHOLD = 3
OFFLINE_THRESHOLD = 3

# ==========================
# RAW RAKNET UDP PING
# Implements the Bedrock "Unconnected Ping" packet directly.
# This is exactly what the Minecraft client sends — no library needed.
# ==========================

RAKNET_MAGIC = bytes([
    0x00, 0xFF, 0xFF, 0x00,
    0xFE, 0xFE, 0xFE, 0xFE,
    0xFD, 0xFD, 0xFD, 0xFD,
    0x12, 0x34, 0x56, 0x78
])

def build_unconnected_ping() -> bytes:
    """Build a RakNet Unconnected Ping packet (0x01)."""
    packet_id = b'\x01'
    timestamp = struct.pack('>Q', int(time.time() * 1000) & 0xFFFFFFFFFFFFFFFF)
    client_guid = struct.pack('>Q', random.getrandbits(64))
    return packet_id + timestamp + RAKNET_MAGIC + client_guid


def parse_pong(data: bytes) -> dict | None:
    """
    Parse RakNet Unconnected Pong (0x1C).
    Returns player info or None if invalid.
    """
    if len(data) < 35 or data[0] != 0x1C:
        return None

    # Skip: packet_id(1) + timestamp(8) + server_guid(8) + magic(16) + str_len(2) = 35
    try:
        str_len = struct.unpack('>H', data[33:35])[0]
        motd_raw = data[35:35 + str_len].decode('utf-8', errors='ignore')
        parts = motd_raw.split(';')
        # Format: MCPE;MOTD;protocol;version;players;max_players;...
        players_online = int(parts[4]) if len(parts) > 4 else 0
        players_max = int(parts[5]) if len(parts) > 5 else 0
        return {
            "online": True,
            "players_online": players_online,
            "players_max": players_max,
        }
    except Exception:
        return {"online": True, "players_online": 0, "players_max": 0}


async def raknet_ping(host: str, port: int, timeout: float = 5.0) -> dict:
    """
    Send 3 UDP pings and return on first valid pong.
    Retries handle UDP packet loss — common on Aternos.
    """
    loop = asyncio.get_event_loop()

    def _ping_sync():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout / 3)
        try:
            ip = socket.gethostbyname(host)
            ping_packet = build_unconnected_ping()
            for _ in range(3):  # 3 attempts
                try:
                    sock.sendto(ping_packet, (ip, port))
                    data, _ = sock.recvfrom(1024)
                    result = parse_pong(data)
                    if result:
                        return result
                except socket.timeout:
                    continue
            return {"online": False, "players_online": 0, "players_max": 0}
        except Exception:
            return {"online": False, "players_online": 0, "players_max": 0}
        finally:
            sock.close()

    return await loop.run_in_executor(None, _ping_sync)


# ==========================
# STATUS — pure UDP, no APIs
# ==========================

async def get_server_status() -> dict:
    return await raknet_ping(HOST, PORT)


# ==========================
# COMMANDS
# ==========================

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = await get_server_status()

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

            if status["online"]:
                online_streak += 1
                offline_streak = 0
            else:
                offline_streak += 1
                online_streak = 0

            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] "
                f"online={status['online']} | "
                f"+{online_streak}✅ -{offline_streak}❌"
            )

            # OFFLINE -> ONLINE
            if not server_online and online_streak >= ONLINE_THRESHOLD:
                server_online = True
                online_streak = 0
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
                offline_streak = 0
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
        await app.bot.send_message(chat_id=CHAT_ID, text="🤖 Bot started!")
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
