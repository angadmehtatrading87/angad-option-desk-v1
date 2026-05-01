import os
import requests


class TelegramNotifier:
    def __init__(self, token: str | None = None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")

    def send(self, chat_id: str | int, text: str) -> dict:
        if not self.token:
            return {"ok": False, "reason": "missing_bot_token"}
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        try:
            resp = requests.post(url, json={"chat_id": str(chat_id), "text": text}, timeout=20)
            return {"ok": resp.ok, "status": resp.status_code}
        except Exception as exc:
            return {"ok": False, "reason": str(exc)}
