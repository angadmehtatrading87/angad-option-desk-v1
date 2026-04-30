from app.trade_store import get_trade, update_trade_status
from app.virtual_portfolio import open_virtual_position, virtual_account_snapshot, list_open_virtual_positions
from app.telegram_alerts import send_telegram_message
from app.execution_engine import check_stale_price

def same_trade_family(open_pos, trade):
    if (open_pos.get("symbol") or "").upper() != (trade.get("symbol") or "").upper():
        return False
    if (open_pos.get("strategy") or "").lower() != (trade.get("strategy") or "").lower():
        return False
    open_exp = str(open_pos.get("expiry") or "").split("/")[0].strip()
    new_exp = str(trade.get("expiry") or "").split("/")[0].strip()
    return open_exp == new_exp

def open_virtual_trade(trade_id, quantity=1):
    trade = get_trade(trade_id)
    if not trade:
        raise ValueError(f"Trade #{trade_id} not found.")

    for p in list_open_virtual_positions():
        if same_trade_family(p, trade):
            update_trade_status(trade_id, "VIRTUAL_DUPLICATE_BLOCKED")
            return {"status": "VIRTUAL_DUPLICATE_BLOCKED"}

    try:
        stale = check_stale_price(trade, tolerance_percent=12)
    except Exception as e:
        update_trade_status(trade_id, "VIRTUAL_QUOTE_UNAVAILABLE")
        return {"status": "VIRTUAL_QUOTE_UNAVAILABLE", "error": str(e)}

    if not stale["ok"]:
        update_trade_status(trade_id, "VIRTUAL_STALE_BLOCKED")
        return {"status": "VIRTUAL_STALE_BLOCKED", "stale": stale}

    opened = open_virtual_position(trade_id, quantity=quantity)
    update_trade_status(trade_id, "VIRTUAL_OPEN")
    snapshot = virtual_account_snapshot()

    total_risk = round(float(trade.get("max_risk") or 0) * int(quantity), 2)

    send_telegram_message(
        f"<b>Virtual Position Opened #{trade_id}</b>\n\n"
        f"Symbol: {trade['symbol']}\n"
        f"Strategy: {trade['strategy']}\n"
        f"Expiry: {trade['expiry']}\n"
        f"Quantity: {quantity}\n"
        f"Unit Max Risk: ${trade.get('max_risk')}\n"
        f"Total Risk: ${total_risk}\n"
        f"Cash Balance: ${snapshot['cash_balance']}\n"
        f"Total Equity: ${snapshot['total_equity']}"
    )
    return {"status": "VIRTUAL_OPEN", "opened": opened, "snapshot": snapshot}
