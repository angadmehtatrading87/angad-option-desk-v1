from app.ig_adapter import IGAdapter
import json

def main():
    ig = IGAdapter()
    print("READINESS")
    print(json.dumps(ig.is_ready(), indent=2))

    if not ig.is_ready().get("enabled"):
        print("\nIG is disabled in config/ig_config.json")
        return

    print("\nLOGIN")
    login = ig.login()
    print(json.dumps(login, indent=2, default=str)[:12000])

    if not login.get("ok"):
        return

    print("\nACCOUNTS")
    print(json.dumps(ig.accounts(), indent=2, default=str)[:12000])

    print("\nPOSITIONS")
    print(json.dumps(ig.positions(), indent=2, default=str)[:12000])

    print("\nWATCHLIST SNAPSHOT")
    print(json.dumps(ig.watchlist_snapshot(), indent=2, default=str)[:12000])

if __name__ == "__main__":
    main()
