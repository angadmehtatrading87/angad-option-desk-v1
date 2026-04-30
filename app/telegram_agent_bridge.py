import json
import os
import time
import requests

from app.telegram_alerts import send_telegram_message
from app.ig_position_takeover import takeover_view
from app.daily_objective_controller import compute_daily_objective_state
from app.ig_adapter import IGAdapter

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else None
OFFSET_PATH = "/home/ubuntu/angad-option-desk-v1/data/telegram_bridge_offset.json"

def _load_offset():
    if not os.path.exists(OFFSET_PATH):
        return {"offset": 0}
    with open(OFFSET_PATH, "r") as f:
        return json.load(f)

def _save_offset(offset):
    with open(OFFSET_PATH, "w") as f:
        json.dump({"offset": offset}, f)

def _get_updates(offset):
    if not BASE_URL:
        return []
    r = requests.get(f"{BASE_URL}/getUpdates", params={"timeout": 25, "offset": offset}, timeout=35)
    body = r.json()
    return body.get("result", []) if body.get("ok") else []

def _reply(chat_id, text):
    send_telegram_message(text, chat_id=chat_id)

def _positions_summary():
    tv = takeover_view()
    managed = tv.get("managed_positions", [])
    if not managed:
        return "No live IG positions."
    lines = ["<b>IG Live Positions</b>", ""]
    for p in managed[:10]:
        lines.append(
            f"{p.get('name')} | {p.get('direction')} | size {p.get('size')} | "
            f"action {p.get('agent_action')} | pnl_pts {p.get('pnl_points')}"
        )
    return "\n".join(lines)

def _objective_summary():
    st = compute_daily_objective_state()
    c = ((st.get("live") or {}).get("combined") or {})
    return (
        "<b>Combined Objective</b>\n\n"
        f"Start Equity: {c.get('start_equity')}\n"
        f"Current Equity: {c.get('current_equity')}\n"
        f"Day P&L: {c.get('day_pnl')}\n"
        f"Target Amount: {c.get('target_amount')}\n"
        f"Target Progress %: {c.get('target_progress_pct')}\n"
        f"Capital Usage %: {c.get('capital_usage_pct')}\n"
        f"Usage Blocked: {c.get('usage_blocked')}"
    )

def _status_summary():
    ig = IGAdapter()
    login = ig.login()
    if not login.get("ok"):
        return "IG login not available."
    body = login.get("body") or {}
    info = body.get("accountInfo", {}) or {}
    return (
        "<b>Agent Status</b>\n\n"
        f"IG Account: {body.get('currentAccountId')}\n"
        f"Balance: {info.get('balance')}\n"
        f"Open P&L: {info.get('profitLoss')}\n"
        f"Available: {info.get('available')}\n"
        f"Dealing Enabled: {body.get('dealingEnabled')}"
    )

def _help():
    return (
        "<b>Agent Commands</b>\n\n"
        "/status - overall status\n"
        "/positions - live IG positions\n"
        "/objective - combined daily objective\n"
        "/why - current takeover view\n"
        "/help - command list\n\n"
        "You can also send plain text like:\n"
        "status\npositions\nobjective\nwhy no trades"
    )

def _free_text_reply(msg):
    m = (msg or "").strip().lower()
    if "status" in m:
        return _status_summary()
    if "position" in m or "trade" in m:
        return _positions_summary()
    if "objective" in m or "target" in m or "profit" in m:
        return _objective_summary()
    if "why" in m:
        tv = takeover_view()
        managed = tv.get("managed_positions", [])
        if not managed:
            return "No live positions. Waiting for valid signals."
        lines = ["<b>Agent View</b>", ""]
        for p in managed[:10]:
            lines.append(f"{p.get('name')} -> {p.get('agent_action')} | {p.get('agent_reason')}")
        return "\n".join(lines)
    return (
        "Message received.\n\n"
        "Try /status, /positions, /objective, /why or /help."
    )

def process_message(chat_id, text):
    t = (text or "").strip()
    if not t:
        return
    if t == "/status":
        _reply(chat_id, _status_summary())
    elif t == "/positions":
        _reply(chat_id, _positions_summary())
    elif t == "/objective":
        _reply(chat_id, _objective_summary())
    elif t == "/why":
        tv = takeover_view()
        managed = tv.get("managed_positions", [])
        if not managed:
            _reply(chat_id, "No live positions. Waiting for valid signals.")
        else:
            lines = ["<b>Agent View</b>", ""]
            for p in managed[:10]:
                lines.append(f"{p.get('name')} -> {p.get('agent_action')} | {p.get('agent_reason')}")
            _reply(chat_id, "\n".join(lines))
    elif t == "/help":
        _reply(chat_id, _help())
    else:
        _reply(chat_id, _free_text_reply(t))

def main():
    state = _load_offset()
    offset = state.get("offset", 0)

    while True:
        try:
            updates = _get_updates(offset)
            for u in updates:
                offset = max(offset, u["update_id"] + 1)
                msg = u.get("message") or {}
                chat = msg.get("chat") or {}
                chat_id = chat.get("id")
                text = msg.get("text", "")
                if chat_id:
                    process_message(chat_id, text)
            _save_offset(offset)
            time.sleep(2)
        except Exception:
            time.sleep(5)

if __name__ == "__main__":
    main()
