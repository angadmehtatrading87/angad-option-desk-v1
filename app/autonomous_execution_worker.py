import time
from app.trading_window import can_open_new_option_trade
from app.execution_brain import run_autonomous_entries

def main():
    while True:
        try:
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
