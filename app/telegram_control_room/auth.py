import os


def get_allowed_chat_id() -> str:
    return str(os.getenv("TELEGRAM_ALLOWED_CHAT_ID", "")).strip()


def is_authorized_chat(chat_id: int | str | None) -> bool:
    allowed = get_allowed_chat_id()
    return bool(allowed and str(chat_id) == allowed)
