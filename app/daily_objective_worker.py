import time
from app.daily_objective_controller import compute_daily_objective_state

def main():
    while True:
        try:
            compute_daily_objective_state()
            time.sleep(300)
        except Exception:
            time.sleep(120)

if __name__ == "__main__":
    main()
