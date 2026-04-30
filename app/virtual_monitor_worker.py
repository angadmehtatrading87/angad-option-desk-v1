import time
from app.exit_brain import evaluate_exit_decisions
from app.virtual_exit import close_position_now
from app.telegram_alerts import send_telegram_message

_closed_positions = set()
_alerted_positions = set()

def should_close(action):
    return action in [
        "TAKE_PROFIT_NOW",
        "STOP_OUT_NOW",
        "TAKE_PROFIT_EARLY",
        "EXIT_EARLY_DUE_TO_WEAKNESS",
    ]

def should_alert(action):
    return action in [
        "TAKE_PROFIT_NOW",
        "STOP_OUT_NOW",
        "TAKE_PROFIT_EARLY",
        "EXIT_EARLY_DUE_TO_WEAKNESS",
        "REDUCE_RISK",
    ]

def main():
    while True:
        try:
            decisions = evaluate_exit_decisions()

            for a in decisions:
                pid = a["position_id"]
                action = a["action"]

                if should_alert(action):
                    key = f"{pid}:{action}"
                    if key not in _alerted_positions:
                        _alerted_positions.add(key)
                        send_telegram_message(
                            f"<b>Exit Brain Update</b>\n\n"
                            f"Position ID: {pid}\n"
                            f"Trade ID: {a['trade_id']}\n"
                            f"Symbol: {a['symbol']}\n"
                            f"Action: {action}\n"
                            f"Unrealized P&L: {a['unrealized_pnl']}\n"
                            f"Reason: {a['reason']}"
                        )

                if should_close(action):
                    if pid in _closed_positions:
                        continue

                    current_mid = a.get("current_spread_mid")
                    if current_mid is None:
                        continue

                    _closed_positions.add(pid)

                    try:
                        close_position_now(
                            position_id=pid,
                            exit_price=float(current_mid),
                            note=f"Auto-closed by Exit Brain: {action}"
                        )
                    except Exception as e:
                        send_telegram_message(
                            f"<b>Virtual Auto-Close Error</b>\n\n"
                            f"Position ID: {pid}\n"
                            f"Action: {action}\n"
                            f"Error: {str(e)}"
                        )

            time.sleep(5)
        except Exception:
            time.sleep(15)

if __name__ == "__main__":
    main()
