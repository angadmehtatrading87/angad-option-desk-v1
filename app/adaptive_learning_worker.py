import time
from app.adaptive_learning import build_adaptation_state

def main():
    while True:
        try:
            build_adaptation_state()
            time.sleep(300)
        except Exception:
            time.sleep(60)

if __name__ == "__main__":
    main()
