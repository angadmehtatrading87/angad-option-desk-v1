import time
from app.tasty_virtual_livebook import refresh_tasty_virtual_livebook

def main():
    while True:
        try:
            refresh_tasty_virtual_livebook()
            time.sleep(20)
        except Exception:
            time.sleep(10)

if __name__ == "__main__":
    main()
