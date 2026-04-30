import json
import re

from app.trade_store import get_trade, update_broker_preview
from app.tasty_connector import dry_run_order, tasty_config
from app.telegram_alerts import send_telegram_message


def extract_leg_symbols(legs_text):
    parts = [p.strip() for p in legs_text.split("/")]

    legs = []

    for p in parts:
        if p.upper().startswith("BUY "):
            action_word = "Buy"
            symbol = p[4:].strip()
        elif p.upper().startswith("SELL "):
            action_word = "Sell"
            symbol = p[5:].strip()
        else:
            continue

        legs.append({
            "action_word": action_word,
            "symbol": symbol
        })

    return legs


def infer_order_action(action_word):
    if action_word == "Buy":
        return "Buy to Open"
    if action_word == "Sell":
        return "Sell to Open"
    return action_word


def parse_option_strike(symbol):
    """
    Tasty option symbol example:
    SPY   260515C00675000
    Last 8 digits are strike * 1000.
    00675000 -> 675.000
    """
    compact = symbol.replace(" ", "")
    m = re.search(r"([CP])(\d{8})$", compact)

    if not m:
        return None

    raw = m.group(2)
    return int(raw) / 1000.0


def spread_width_from_legs(legs):
    strikes = []

    for leg in legs:
        strike = parse_option_strike(leg["symbol"])
        if strike is not None:
            strikes.append(strike)

    if len(strikes) < 2:
        return None

    return abs(strikes[0] - strikes[1])


def normalize_order_price(value, spread_width=None):
    """
    Broker order price must be per-share option price, e.g. 0.42,
    not total contract dollars, e.g. 42.
    """
    if value is None:
        return None

    price = float(value)

    # If price is larger than spread width, it is almost certainly contract-dollar value.
    if spread_width and price > spread_width:
        price = price / 100.0

    # Extra safety: if price is absurdly large for an option spread, divide by 100.
    if price > 20:
        price = price / 100.0

    return round(price, 2)


def build_dry_run_payload(trade):
    estimated_debit = trade.get("estimated_debit")
    estimated_credit = trade.get("estimated_credit")

    legs = extract_leg_symbols(trade.get("legs", ""))

    if len(legs) != 2:
        raise ValueError(f"Could not parse 2 option legs from: {trade.get('legs')}")

    width = spread_width_from_legs(legs)

    order_legs = []
    for leg in legs:
        order_legs.append({
            "instrument-type": "Equity Option",
            "symbol": leg["symbol"],
            "quantity": 1,
            "action": infer_order_action(leg["action_word"])
        })

    if estimated_debit is not None:
        price_value = normalize_order_price(estimated_debit, width)
        price_effect = "Debit"
    elif estimated_credit is not None:
        price_value = normalize_order_price(estimated_credit, width)
        price_effect = "Credit"
    else:
        raise ValueError("Trade has neither estimated_debit nor estimated_credit.")

    if price_value is None or price_value <= 0:
        raise ValueError("Invalid order price.")

    if width and price_value > width:
        raise ValueError(f"Order price {price_value} is greater than spread width {width}.")

    payload = {
        "order-type": "Limit",
        "time-in-force": "Day",
        "price": str(price_value),
        "price-effect": price_effect,
        "legs": order_legs
    }

    return payload


def preview_trade_order(trade_id):
    cfg = tasty_config()

    if cfg.get("order_execution_enabled"):
        raise RuntimeError("Execution flag is enabled. Refusing preview until config is reviewed.")

    trade = get_trade(trade_id)

    if not trade:
        raise ValueError(f"Trade #{trade_id} not found.")

    payload = build_dry_run_payload(trade)

    result = dry_run_order(payload)

    preview_status = "PASSED" if result.get("status_code") in [200, 201] else "FAILED"

    update_broker_preview(
        trade_id=trade_id,
        preview_status=preview_status,
        preview_response=result,
        order_payload=payload
    )

    msg = f"""
<b>Broker Dry-Run Preview #{trade_id}</b>

Status: {preview_status}
HTTP: {result.get("status_code")}

Symbol: {trade.get("symbol")}
Strategy: {trade.get("strategy")}
Expiry: {trade.get("expiry")}

Legs:
{trade.get("legs")}

Payload:
{json.dumps(payload, indent=2)}

No order placed.
Execution Enabled: {cfg.get("order_execution_enabled")}
"""
    send_telegram_message(msg)

    return {
        "trade_id": trade_id,
        "preview_status": preview_status,
        "payload": payload,
        "result": result
    }
