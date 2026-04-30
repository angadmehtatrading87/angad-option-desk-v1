from datetime import datetime, timezone
from app.tasty_connector import get_nested_option_chain

def parse_expiry_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except Exception:
        try:
            return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
        except Exception:
            return None

def extract_expirations(raw):
    items = raw.get("data", {}).get("items", [])
    expirations = []

    for item in items:
        if "expirations" in item:
            expirations.extend(item.get("expirations", []))
        else:
            expirations.append(item)

    return expirations

def get_chain_summary(symbol, min_dte=21, max_dte=45, max_expiries=8):
    raw = get_nested_option_chain(symbol)
    expirations = extract_expirations(raw)

    today = datetime.now(timezone.utc).date()
    all_expiries = []
    filtered_expiries = []

    for item in expirations:
        expiry_date_raw = (
            item.get("expiration-date")
            or item.get("expiration")
            or item.get("expires-at")
            or item.get("expiry")
        )

        expiry_date = parse_expiry_date(expiry_date_raw)

        if not expiry_date:
            continue

        dte = item.get("days-to-expiration")
        if dte is None:
            dte = (expiry_date - today).days
        else:
            try:
                dte = int(dte)
            except Exception:
                dte = (expiry_date - today).days

        strikes = item.get("strikes", [])

        cleaned_strikes = []
        for strike in strikes:
            cleaned_strikes.append({
                "strike_price": strike.get("strike-price"),
                "call_symbol": strike.get("call"),
                "call_streamer": strike.get("call-streamer-symbol"),
                "put_symbol": strike.get("put"),
                "put_streamer": strike.get("put-streamer-symbol"),
            })

        expiry_obj = {
            "expiration_date": str(expiry_date),
            "dte": dte,
            "strike_count": len(strikes),
            "sample_strikes": cleaned_strikes,
        }

        all_expiries.append(expiry_obj)

        if min_dte <= dte <= max_dte:
            filtered_expiries.append(expiry_obj)

    all_expiries = sorted(all_expiries, key=lambda x: x["dte"])
    filtered_expiries = sorted(filtered_expiries, key=lambda x: x["dte"])

    display_expiries = filtered_expiries[:max_expiries]
    fallback_used = False

    if not display_expiries:
        display_expiries = all_expiries[:max_expiries]
        fallback_used = True

    return {
        "symbol": symbol.upper(),
        "min_dte": min_dte,
        "max_dte": max_dte,
        "expiries_found": len(display_expiries),
        "filtered_expiries_found": len(filtered_expiries),
        "all_expiries_count": len(all_expiries),
        "fallback_used": fallback_used,
        "available_expiries": [
            {
                "expiration_date": e["expiration_date"],
                "dte": e["dte"],
                "strike_count": e["strike_count"]
            }
            for e in all_expiries[:30]
        ],
        "expiries": display_expiries,
    }
