import time
from app.execution_safety_guard import evaluate_execution_safety
from app.trading_window import can_open_new_option_trade
from app.execution_brain import run_autonomous_entries

def main():
    while True:
        try:
            safety = evaluate_execution_safety(channel="autonomous_execution_worker", expected_order_count=1)
            if not safety.get("ok"):
                time.sleep(60)
                continue

            allowed, _ = can_open_new_option_trade()
            if not allowed:
                time.sleep(60)
                continue
            run_autonomous_entries()
            time.sleep(120)
        except Exception:
            time.sleep(60)

if __name__ == "__main__":
    main()
