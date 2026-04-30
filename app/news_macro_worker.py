import time
from app.news_macro import refresh_news_macro
from app.telegram_alerts import send_telegram_message

LAST_NOTE = None

def main():
    global LAST_NOTE
    send_telegram_message("📰 News/macro worker restarted.")

    while True:
        try:
            result = refresh_news_macro()
            snap = result["snapshot"]

            note = (
                f"News macro refresh complete. "
                f"Headlines: {snap['headline_count']} | "
                f"Risk-on: {snap['risk_on_score']} | "
                f"Risk-off: {snap['risk_off_score']} | "
                f"Regime: {snap['macro_regime']}"
            )

            LAST_NOTE = note
            time.sleep(300)

        except Exception as e:
            send_telegram_message(f"News macro worker error: {e}")
            time.sleep(300)

if __name__ == "__main__":
    main()
