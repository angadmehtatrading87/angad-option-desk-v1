import time
from datetime import datetime
from zoneinfo import ZoneInfo

from app.agent_policy import load_agent_policy
from app.reporting_engine import (
    pre_session_due,
    post_session_due,
    mark_pre_session_sent,
    mark_post_session_sent,
    get_pre_session_message,
    build_owner_post_session_report,
)
from app.telegram_alerts import send_telegram_message

DXB = ZoneInfo("Asia/Dubai")

def _now():
    return datetime.now(DXB)

def _hhmm():
    n = _now()
    return f"{n.hour:02d}:{n.minute:02d}"

def main():
    while True:
        try:
            policy = load_agent_policy()
            comms = policy.get("communications", {})
            pre_time = comms.get("pre_session_report_time_dxb", "17:15")
            post_time = comms.get("post_session_report_time_dxb", "23:45")
            current = _hhmm()

            if current == pre_time and pre_session_due():
                send_telegram_message(get_pre_session_message())
                mark_pre_session_sent()

            if current == post_time and post_session_due():
                msg, new_pool = build_owner_post_session_report()
                send_telegram_message(msg)
                mark_post_session_sent(new_pool)

            time.sleep(30)
        except Exception:
            time.sleep(60)

if __name__ == "__main__":
    main()
