import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from app.virtual_portfolio import virtual_account_snapshot
from app.lane_capital_controller import tasty_lane_snapshot

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(BASE_DIR, "data", "tasty_virtual_livebook.json")
DXB = ZoneInfo("Asia/Dubai")

def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

def _now():
    return datetime.now(DXB).isoformat()

def _save_state(state):
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def _fallback_mark(entry_value, side, symbol=None):
    entry_value = _safe_float(entry_value)
    if entry_value <= 0:
        return 0.0

    # conservative fallback so fresh trades do not instantly mark to zero
    if side == "DEBIT":
        return round(max(0.01, entry_value * 0.92), 2)
    return round(max(0.01, entry_value * 1.08), 2)

def refresh_tasty_virtual_livebook():
    snap = virtual_account_snapshot()
    lane = tasty_lane_snapshot()

    positions = []
    for p in snap.get("open_positions", []):
        detail = None
        for d in snap.get("unrealized_details", []):
            if d.get("position_id") == p.get("id"):
                detail = d
                break

        side = "DEBIT" if p.get("entry_debit") else "CREDIT"
        entry_value = p.get("entry_debit") or p.get("entry_credit") or 0.0
        raw_mark = _safe_float((detail or {}).get("current_spread_mid", 0.0))
        mark_value = raw_mark if raw_mark > 0 else _fallback_mark(entry_value, side, p.get("symbol"))

        quantity_est = p.get("quantity", 1)
        if side == "DEBIT":
            unrealized_pnl = round((mark_value - _safe_float(entry_value)) * 100.0 * _safe_float(quantity_est), 2)
        else:
            unrealized_pnl = round((_safe_float(entry_value) - mark_value) * 100.0 * _safe_float(quantity_est), 2)

        positions.append({
            "position_id": p.get("id"),
            "trade_id": p.get("trade_id"),
            "symbol": p.get("symbol"),
            "strategy": p.get("strategy"),
            "status": p.get("status"),
            "side": side,
            "confidence": None,
            "quality_score": None,
            "entry_value": entry_value,
            "mark_value": mark_value,
            "quantity_est": quantity_est,
            "max_risk": p.get("reserved_capital", 0.0),
            "unrealized_pnl": unrealized_pnl,
            "created_at": p.get("opened_at"),
            "agent_note": p.get("notes") or "Virtual live position"
        })

    raw_cash = _safe_float(snap.get("cash_balance"))
    raw_equity = _safe_float(snap.get("total_equity"))
    raw_realized = _safe_float(snap.get("realized_pnl"))
    raw_unrealized = _safe_float(snap.get("unrealized_pnl"))

    if raw_cash <= 0 and raw_equity <= 0 and not positions:
        cash_balance = _safe_float(lane.get("cash_balance"))
        equity = _safe_float(lane.get("equity"))
        realized_pnl = _safe_float(lane.get("realized_pnl"))
        unrealized_pnl = round(sum(_safe_float(p.get("unrealized_pnl")) for p in positions), 2)
        source_status = "lane_capital_fallback"
    else:
        cash_balance = raw_cash
        equity = raw_equity
        realized_pnl = raw_realized
        unrealized_pnl = round(sum(_safe_float(pos.get("unrealized_pnl")) for pos in positions), 2)
        source_status = "virtual_account_snapshot"

    summary = {
        "updated_at": _now(),
        "source_status": source_status,
        "open_positions": len(positions),
        "cash_balance": round(cash_balance, 2),
        "equity": round(equity, 2),
        "realized_pnl": round(realized_pnl, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "deployed_risk_est": round(sum(_safe_float(p.get("max_risk")) for p in positions), 2)
    }

    state = {
        "updated_at": _now(),
        "positions": positions,
        "summary": summary
    }
    _save_state(state)
    return state

def load_tasty_virtual_livebook():
    return refresh_tasty_virtual_livebook()
