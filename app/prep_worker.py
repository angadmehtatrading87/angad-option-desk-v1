import time
from app.prep_cycle import run_full_prep_cycle

def main():
    while True:
        try:
            run_full_prep_cycle()
            time.sleep(300)
        except Exception:
            time.sleep(60)

if __name__ == "__main__":
    main()
