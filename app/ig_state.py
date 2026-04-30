from app.ig_adapter import IGAdapter

def get_ig_state():
    ig = IGAdapter()
    readiness = ig.is_ready()

    out = {
        "readiness": readiness,
        "login": None,
        "positions": None,
        "watchlist": None,
        "account_id": ig.account_id,
    }

    if not readiness.get("enabled"):
        return out

    login = ig.login()
    out["login"] = login

    if not login.get("ok"):
        return out

    out["session"] = ig.session()
    out["positions"] = ig.positions()
    out["watchlist"] = ig.watchlist_snapshot()
    return out
