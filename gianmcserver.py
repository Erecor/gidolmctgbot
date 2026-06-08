import asyncio
from mcstatus import BedrockServer

HOST = "darkhaldwani.aternos.me"
PORT = 50742

CHECK_INTERVAL = 60

ONLINE_THRESHOLD = 2
OFFLINE_THRESHOLD = 2

SERVER = BedrockServer.lookup(
    f"{HOST}:{PORT}"
)


async def get_server_status():
    try:
        status = await asyncio.wait_for(
            SERVER.async_status(),
            timeout=8
        )

        return {
            "online": True,
            "players_online": status.players_online,
            "players_max": status.players_max,
            "latency": getattr(status, "latency", 0)
        }

    except Exception:
        return {
            "online": False
        }


async def monitor_server():
    server_online = False

    online_streak = 0
    offline_streak = 0

    while True:

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

            print(
                f"🟢 VERIFIED ONLINE "
                f"({status['players_online']}/"
                f"{status['players_max']})"
            )

            # Telegram send_message here

        # ONLINE -> OFFLINE
        elif (
            server_online
            and offline_streak >= OFFLINE_THRESHOLD
        ):
            server_online = False

            print("🔴 VERIFIED OFFLINE")

            # Telegram send_message here

        await asyncio.sleep(
            CHECK_INTERVAL
        )


async def status_command():
    status = await get_server_status()

    if not status["online"]:
        print("🔴 Server Offline")
        return

    print(
        f"🟢 Server Online\n"
        f"Players: "
        f"{status['players_online']}/"
        f"{status['players_max']}"
    )


async def main():
    asyncio.create_task(
        monitor_server()
    )

    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
