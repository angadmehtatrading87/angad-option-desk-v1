from datetime import datetime, timezone
import json

from app.trade_store import get_trade, update_trade_status
from app.order_preview import build_dry_run_payload, preview_trade_order
from app.tasty_connector import tasty_config
from app.telegram_alerts import send_telegram_message
from app.trading_window import can_open_new_option_trade
from app.quote_engine import quote_options


def extract_symbols_from_trade(trade):
    legs_text = trade.get("legs", "")
    parts = [p.strip() for p in legs_text.split("/")]
    symbols = []

    for p in parts:
        if p.upper().startswith("BUY "):
            symbols.append(p[4:].strip())
        elif p.upper().startswith("SELL "):
            symbols.append(p[5:].strip())

    return symbols


def current_spread_price_from_trade(trade):
    """
    Reprice the approved spread using live bid/ask.
    Debit:
      Buy leg ask - Sell leg bid
    Credit:
      Sell leg bid - Buy leg ask
    """
    legs_text = trade.get("legs", "")
    parts = [p.strip() for p in legs_text.split("/")]

    if len(parts) != 2:
        raise ValueError("Expected exactly 2 spread legs.")

    parsed = []

    for p in parts:
        if p.upper().startswith("BUY "):
            parsed.append(("BUY", p[4:].strip()))
        elif p.upper().startswith("SELL "):
            parsed.append(("SELL", p[5:].strip()))
        else:
            raise ValueError(f"Could not parse leg: {p}")

    symbols = [x[1] for x in parsed]
    quotes = quote_options(symbols)

    buy_leg = next((x for x in parsed if x[0] == "BUY"), None)
    sell_leg = next((x for x in parsed if x[0] == "SELL"), None)

    if not buy_leg or not sell_leg:
        raise ValueError("Could not find one buy leg and one sell leg.")

    buy_q = quotes.get(buy_leg[1])
    sell_q = quotes.get(sell_leg[1])

    if not buy_q or not sell_q:
        raise ValueError("Missing quote for one or more legs.")

    buy_ask = buy_q.get("ask")
    sell_bid = sell_q.get("bid")

    if buy_ask is None or sell_bid is None:
        raise ValueError("Missing bid/ask for repricing.")

    # Detect debit/credit from trade
    if trade.get("estimated_debit") is not None:
        price = round(buy_ask - sell_bid, 2)
        price_effect = "Debit"
    elif trade.get("estimated_credit") is not None:
        # For credit spread, original legs are usually Sell / Buy.
        sell_q2 = quotes.get(sell_leg[1])
        buy_q2 = quotes.get(buy_leg[1])
        price = round((sell_q2.get("bid") or 0) - (buy_q2.get("ask") or 0), 2)
        price_effect = "Credit"
    else:
        raise ValueError("Trade has no estimated debit/credit.")

    return {
        "current_price": price,
        "price_effect": price_effect,
        "quotes": quotes
    }


def check_stale_price(trade, tolerance_percent=12):
    if trade.get("estimated_debit") is not None:
        original = float(trade["estimated_debit"])
    elif trade.get("estimated_credit") is not None:
        original = float(trade["estimated_credit"])
    else:
        raise ValueError("Missing original price.")

    current = current_spread_price_from_trade(trade)
    current_price = float(current["current_price"])

    if original <= 0:
        raise ValueError("Original price invalid.")

    move_pct = abs(current_price - original) / original * 100

    return {
        "ok": move_pct <= tolerance_percent,
        "original_price": round(original, 2),
        "current_price": round(current_price, 2),
        "move_pct": round(move_pct, 2),
        "tolerance_percent": tolerance_percent,
        "price_effect": current["price_effect"],
        "quotes": current["quotes"]
    }


def execute_approved_trade(trade_id):
    cfg = tasty_config()

    trade = get_trade(trade_id)
    if not trade:
        raise ValueError(f"Trade #{trade_id} not found.")

    allowed, window_reason = can_open_new_option_trade()
    if not allowed:
        msg = f"""
<b>Execution Blocked #{trade_id}</b>

Reason: {window_reason}
No order placed.
"""
        send_telegram_message(msg)
        return {"status": "BLOCKED", "reason": window_reason}

    stale = check_stale_price(trade, tolerance_percent=12)

    if not stale["ok"]:
        msg = f"""
<b>Execution Blocked — Stale Price #{trade_id}</b>

Original Price: {stale["original_price"]}
Current Price: {stale["current_price"]}
Move: {stale["move_pct"]}%
Tolerance: {stale["tolerance_percent"]}%

No order placed.
"""
        send_telegram_message(msg)
        update_trade_status(trade_id, "STALE_PRICE_BLOCKED")
        return {"status": "STALE_PRICE_BLOCKED", "stale": stale}

    preview = preview_trade_order(trade_id)

    if preview["preview_status"] != "PASSED":
        msg = f"""
<b>Execution Blocked — Broker Dry-Run Failed #{trade_id}</b>

HTTP: {preview["result"].get("status_code")}
Result:
{json.dumps(preview["result"].get("body"), indent=2)[:2500]}

No order placed.
"""
        send_telegram_message(msg)
        update_trade_status(trade_id, "BROKER_DRY_RUN_FAILED")
        return {"status": "BROKER_DRY_RUN_FAILED", "preview": preview}

    if not cfg.get("order_execution_enabled"):
        msg = f"""
<b>Execution Ready but Disabled #{trade_id}</b>

Fresh quote check: PASSED
Broker dry-run: PASSED

Execution flag:
TASTY_ORDER_EXECUTION_ENABLED=false

No live order placed.
"""
        send_telegram_message(msg)
        update_trade_status(trade_id, "READY_EXECUTION_DISABLED")
        return {"status": "READY_EXECUTION_DISABLED", "preview": preview}

    # Live execution intentionally not implemented yet.
    # We add it only after explicit final approval and passing dry-run.
    msg = f"""
<b>Execution Engine Reached Live Step #{trade_id}</b>

Execution flag is enabled, but live order submission module is not yet installed.
No order placed.
"""
    send_telegram_message(msg)
    return {"status": "LIVE_MODULE_NOT_INSTALLED"}
