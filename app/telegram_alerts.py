import os
import requests
from dotenv import load_dotenv

load_dotenv("/home/ubuntu/angad-option-desk-v1/.env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_message(message: str, chat_id=None):
    if not TELEGRAM_BOT_TOKEN:
        return {"ok": False, "reason": "missing_bot_token"}

    target_chat_id = chat_id or TELEGRAM_CHAT_ID
    if not target_chat_id:
        return {"ok": False, "reason": "missing_chat_id"}

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": target_chat_id,
        "text": message,
        "parse_mode": "HTML",
    }

    try:
        r = requests.post(url, json=payload, timeout=20)
        try:
            body = r.json()
        except Exception:
            body = r.text
        return {"ok": r.ok, "status_code": r.status_code, "body": body}
    except Exception as e:
        return {"ok": False, "reason": str(e)}

def send_ig_trade_alert(title: str, lines: list[str]):
    body = "<b>" + title + "</b>\n\n" + "\n".join(lines)
    return send_telegram_message(body)

def send_trade_action_message(title: str, lines: list[str]):
    body = "<b>" + title + "</b>\n\n" + "\n".join(lines)
    return send_telegram_message(body)
