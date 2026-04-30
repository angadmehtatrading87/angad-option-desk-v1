import time
import os
from dotenv import load_dotenv

from app.telegram_alerts import get_updates, send_telegram_message, answer_callback_query
from app.trade_store import update_trade_status
from app.virtual_execution import open_virtual_trade

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

ALLOWED_CHAT_ID = str(os.getenv("TELEGRAM_CHAT_ID", ""))

APPROVE_COMMANDS = {"A", "Y", "YES", "APPROVE", "OK"}
REJECT_COMMANDS = {"R", "N", "NO", "REJECT", "SKIP"}

def approve_trade(trade_id: int):
    update_trade_status(trade_id, "APPROVED_BY_USER")
    send_telegram_message(
        f"✅ Trade #{trade_id} approved. Running virtual fill checks."
    )

    try:
        result = open_virtual_trade(trade_id)
        send_telegram_message(f"Virtual workflow result for #{trade_id}: {result.get('status')}")
    except Exception as e:
        send_telegram_message(f"Virtual workflow error for #{trade_id}: {e}")

def reject_trade(trade_id: int):
    update_trade_status(trade_id, "REJECTED")
    send_telegram_message(f"❌ Trade #{trade_id} rejected.")

def handle_text_command(text, chat_id):
    text = text.strip().upper()
    chat_id = str(chat_id)

    if chat_id != ALLOWED_CHAT_ID:
        send_telegram_message("Blocked unauthorized Telegram command attempt.")
        return

    parts = text.split()

    if len(parts) != 2:
        send_telegram_message("Use: A <trade_id> or R <trade_id>, or tap the buttons.")
        return

    action, trade_id_raw = parts

    if not trade_id_raw.isdigit():
        send_telegram_message("Trade ID must be a number. Example: A 42")
        return

    trade_id = int(trade_id_raw)

    if action in APPROVE_COMMANDS:
        approve_trade(trade_id)
    elif action in REJECT_COMMANDS:
        reject_trade(trade_id)
    else:
        send_telegram_message("Unknown command. Use: A <trade_id> or R <trade_id>")

def handle_callback(callback):
    callback_id = callback.get("id")
    data = callback.get("data", "")
    message = callback.get("message", {})
    chat_id = str(message.get("chat", {}).get("id"))

    if chat_id != ALLOWED_CHAT_ID:
        answer_callback_query(callback_id, "Unauthorized")
        send_telegram_message("Blocked unauthorized Telegram button attempt.")
        return

    if ":" not in data:
        answer_callback_query(callback_id, "Invalid action")
        return

    action, trade_id_raw = data.split(":", 1)

    if not trade_id_raw.isdigit():
        answer_callback_query(callback_id, "Invalid trade ID")
        return

    trade_id = int(trade_id_raw)

    if action == "A":
        answer_callback_query(callback_id, f"Approving trade #{trade_id}")
        approve_trade(trade_id)

    elif action == "R":
        answer_callback_query(callback_id, f"Rejecting trade #{trade_id}")
        reject_trade(trade_id)

    else:
        answer_callback_query(callback_id, "Unknown action")

def main():
    send_telegram_message("🤖 Telegram worker restarted. Virtual trading mode active.")
    offset = None

    while True:
        try:
            data = get_updates(offset=offset)

            if data.get("ok"):
                for update in data.get("result", []):
                    offset = update["update_id"] + 1

                    if update.get("callback_query"):
                        handle_callback(update["callback_query"])
                        continue

                    msg = update.get("message")
                    if not msg:
                        continue

                    chat_id = msg.get("chat", {}).get("id")
                    text = msg.get("text", "")

                    if text:
                        handle_text_command(text, chat_id)

            time.sleep(2)

        except Exception as e:
            send_telegram_message(f"Telegram worker error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
