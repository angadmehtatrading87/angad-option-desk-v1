from datetime import datetime, timezone
from app.news_macro import latest_news_macro
from app.virtual_portfolio import virtual_account_snapshot

GRACE_PERIOD_SECONDS = 180

def macro_regime():
    data = latest_news_macro()
    snap = (data or {}).get("snapshot") or {}
    return snap.get("macro_regime", "NEUTRAL")

def _parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None

def _seconds_open(opened_at):
    dt = _parse_dt(opened_at)
    if not dt:
        return None
    now = datetime.now(dt.tzinfo or timezone.utc)
    return (now - dt).total_seconds()

def evaluate_exit_decisions():
    snap = virtual_account_snapshot()
    regime = macro_regime()
    decisions = []

    for pos in snap["unrealized_details"]:
        unreal = pos.get("unrealized_pnl")
        current_mid = pos.get("current_spread_mid")
        quote_status = pos.get("quote_status", "OK")

        open_pos = next((x for x in snap["open_positions"] if x["id"] == pos["position_id"]), None)
        if not open_pos:
            continue

        seconds_open = _seconds_open(open_pos.get("opened_at"))
        entry_debit = open_pos.get("entry_debit")
        entry_credit = open_pos.get("entry_credit")
        qty = int(open_pos.get("quantity") or 1)

        if entry_debit is not None:
            entry_value = float(entry_debit) * 100 * qty
            entry_unit = float(entry_debit)
        elif entry_credit is not None:
            entry_value = float(entry_credit) * 100 * qty
            entry_unit = float(entry_credit)
        else:
            entry_value = 0.0
            entry_unit = 0.0

        tp = round(entry_value * 0.60, 2)
        sl = round(entry_value * -0.50, 2)

        action = "HOLD"
        reason = "No trigger."
        confidence = 60

        # 1) grace period after opening
        if seconds_open is not None and seconds_open < GRACE_PERIOD_SECONDS:
            action = "HOLD"
            reason = f"In grace period after entry ({int(seconds_open)}s < {GRACE_PERIOD_SECONDS}s)"
            confidence = 25

        # 2) reject clearly bad quote states
        elif quote_status != "OK":
            action = "HOLD"
            reason = f"Quote status not clean: {quote_status}"
            confidence = 30

        elif current_mid is None:
            action = "HOLD"
            reason = "Current spread mid missing."
            confidence = 30

        elif current_mid <= 0:
            action = "HOLD"
            reason = f"Invalid spread mid ({current_mid}); refusing forced exit."
            confidence = 20

        # for debit spreads, if mark collapses unrealistically too fast, ignore until stabilized
        elif open_pos["strategy"] == "debit_spread" and entry_unit > 0:
            if current_mid < entry_unit * 0.15 and (seconds_open is not None and seconds_open < 900):
                action = "HOLD"
                reason = f"Mid looks unstable vs entry ({current_mid} vs {entry_unit}); waiting for stabilization."
                confidence = 20
            elif unreal is None:
                action = "HOLD"
                reason = "Missing unrealized P&L."
                confidence = 35
            elif unreal >= tp:
                action = "TAKE_PROFIT_NOW"
                reason = f"Profit target reached: {unreal} >= {tp}"
                confidence = 90
            elif unreal <= sl:
                action = "STOP_OUT_NOW"
                reason = f"Stop threshold reached: {unreal} <= {sl}"
                confidence = 95
            elif unreal > 0 and unreal >= tp * 0.65:
                action = "TAKE_PROFIT_EARLY"
                reason = f"Good profit captured early: {unreal}"
                confidence = 78
            elif unreal < 0 and abs(unreal) >= abs(sl) * 0.75:
                action = "EXIT_EARLY_DUE_TO_WEAKNESS"
                reason = f"Loss approaching stop with weakening trade: {unreal}"
                confidence = 72

        else:
            if unreal is None:
                action = "HOLD"
                reason = "Missing unrealized P&L."
                confidence = 35
            elif unreal >= tp:
                action = "TAKE_PROFIT_NOW"
                reason = f"Profit target reached: {unreal} >= {tp}"
                confidence = 90
            elif unreal <= sl:
                action = "STOP_OUT_NOW"
                reason = f"Stop threshold reached: {unreal} <= {sl}"
                confidence = 95

        decisions.append({
            "position_id": pos["position_id"],
            "trade_id": pos["trade_id"],
            "symbol": pos["symbol"],
            "strategy": pos["strategy"],
            "quantity": pos.get("quantity"),
            "entry_price": pos.get("entry_price"),
            "current_spread_mid": current_mid,
            "unrealized_pnl": unreal,
            "quote_status": quote_status,
            "macro_regime": regime,
            "target_profit": tp,
            "stop_loss": sl,
            "action": action,
            "reason": reason,
            "confidence": confidence,
        })

    return decisions
