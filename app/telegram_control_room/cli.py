import argparse
import os
import time
import requests
from .bot import TelegramControlRoomBot
from .notifier import TelegramNotifier


def run_bot():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is required")
    base = f"https://api.telegram.org/bot{token}"
    offset = None
    bot = TelegramControlRoomBot()
    notifier = TelegramNotifier(token)
    while True:
        res = requests.get(f"{base}/getUpdates", params={"offset": offset, "timeout": 20}, timeout=30).json()
        for upd in res.get("result", []):
            offset = upd["update_id"] + 1
            msg = upd.get("message", {})
            chat_id = msg.get("chat", {}).get("id")
            text = msg.get("text", "")
            if chat_id and text:
                notifier.send(chat_id, bot.handle_command(str(chat_id), text))
        time.sleep(1)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["run", "status", "test-message"])
    args = p.parse_args()
    bot = TelegramControlRoomBot()
    if args.command == "run":
        run_bot()
    elif args.command == "status":
        print(bot.handle_command(os.getenv("TELEGRAM_ALLOWED_CHAT_ID", ""), "/status"))
    else:
        print("Telegram control room test command ok")


if __name__ == "__main__":
    main()
