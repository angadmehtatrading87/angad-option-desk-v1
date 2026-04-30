import os
import json
import yaml
from datetime import datetime
from zoneinfo import ZoneInfo
from app.tasty_connector import get_market_data
from app.market_prep_brain import load_market_prep_state, STATE_PATH

DXB = ZoneInfo("Asia/Dubai")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED_PATH = os.path.join(BASE_DIR, "config", "universe_seed.yaml")

def _load_seed():
    with open(SEED_PATH, "r") as f:
        return yaml.safe_load(f) or {}

def get_seed_symbols():
    data = _load_seed()
    return [str(x).upper() for x in data.get("symbols", [])]

def safe_float(v, default=None):
    try:
        if v in (None, ""):
            return default
        return float(v)
    except Exception:
        return default

def fetch_equity_quotes(symbols):
    resp = get_market_data("Equity", symbols)
    if resp["status_code"] != 200:
        return {"ok": False, "error": f"quote fetch failed: {resp['status_code']}", "quotes": {}}
    items = resp["body"].get("data", {}).get("items", [])
    quotes = {}
    for item in items:
        symbol = (item.get("symbol") or "").upper()
        bid = safe_float(item.get("bid"))
        ask = safe_float(item.get("ask"))
        last = safe_float(item.get("last"), safe_float(item.get("mark")))
        prev_close = safe_float(item.get("prev-close"), safe_float(item.get("prev_close")))
        volume = safe_float(item.get("volume"), 0)

        spread_pct = None
        if bid not in (None, 0) and ask not in (None, 0):
            mid = (bid + ask) / 2
            if mid > 0:
                spread_pct = round(((ask - bid) / mid) * 100, 3)

        change_pct = None
        if last is not None and prev_close not in (None, 0):
            change_pct = round(((last - prev_close) / prev_close) * 100, 3)

        quotes[symbol] = {
            "symbol": symbol,
            "bid": bid,
            "ask": ask,
            "last": last,
            "prev_close": prev_close,
            "volume": volume,
            "spread_pct": spread_pct,
            "change_pct": change_pct,
        }
    return {"ok": True, "quotes": quotes}

def score_symbol(quote, regime):
    score = 0
    reasons = []
    reject_reasons = []

    last = quote.get("last")
    spread_pct = quote.get("spread_pct")
    volume = quote.get("volume") or 0
    chg = quote.get("change_pct")

    if last is None or last < 5:
        reject_reasons.append("price_too_low_or_missing")
    else:
        score += 10
        reasons.append("price_ok")

    if spread_pct is None:
        reject_reasons.append("spread_missing")
    elif spread_pct <= 0.08:
        score += 25
        reasons.append("tight_spread")
    elif spread_pct <= 0.20:
        score += 15
        reasons.append("acceptable_spread")
    elif spread_pct <= 0.50:
        score += 5
        reasons.append("wide_but_usable")
    else:
        reject_reasons.append("spread_too_wide")

    if volume >= 10_000_000:
        score += 25
        reasons.append("very_high_volume")
    elif volume >= 2_000_000:
        score += 18
        reasons.append("high_volume")
    elif volume >= 500_000:
        score += 10
        reasons.append("tradable_volume")
    else:
        reject_reasons.append("volume_too_low")

    if chg is not None:
        abs_chg = abs(chg)
        if abs_chg >= 3:
            score += 20
            reasons.append("strong_move")
        elif abs_chg >= 1.5:
            score += 12
            reasons.append("decent_move")
        elif abs_chg >= 0.5:
            score += 6
            reasons.append("mild_move")
        else:
            reject_reasons.append("move_too_small")
    else:
        reject_reasons.append("change_missing")

    if regime == "RISK_ON" and chg is not None and chg > 0:
        score += 8
        reasons.append("aligned_with_risk_on")
    elif regime == "RISK_OFF" and chg is not None and chg < 0:
        score += 8
        reasons.append("aligned_with_risk_off")

    return {
        "eligible": len(reject_reasons) == 0,
        "score": score,
        "reasons": reasons,
        "reject_reasons": reject_reasons,
    }

def build_dynamic_universe():
    state = load_market_prep_state()
    regime = state.get("regime_view", {}).get("regime", "MIXED")
    symbols = get_seed_symbols()
    quote_resp = fetch_equity_quotes(symbols)

    if not quote_resp["ok"]:
        state["dynamic_universe"] = {
            "generated_at_dxb": datetime.now(DXB).isoformat(),
            "ok": False,
            "error": quote_resp["error"],
            "eligible_symbols": [],
            "focus_tier_1": [],
            "focus_tier_2": [],
            "rejected_symbols": [],
        }
        with open(STATE_PATH, "w") as f:
            json.dump(state, f, indent=2)
        return state

    eligible = []
    rejected = []

    for symbol in symbols:
        q = quote_resp["quotes"].get(symbol)
        if not q:
            rejected.append({"symbol": symbol, "reject_reasons": ["quote_missing"]})
            continue

        scored = score_symbol(q, regime)
        row = {
            "symbol": symbol,
            "score": scored["score"],
            "reasons": scored["reasons"],
            "reject_reasons": scored["reject_reasons"],
            "change_pct": q.get("change_pct"),
            "spread_pct": q.get("spread_pct"),
            "volume": q.get("volume"),
            "last": q.get("last"),
        }

        if scored["eligible"]:
            eligible.append(row)
        else:
            rejected.append(row)

    eligible = sorted(eligible, key=lambda x: x["score"], reverse=True)
    focus_tier_1 = eligible[:5]
    focus_tier_2 = eligible[5:12]

    state["dynamic_universe"] = {
        "generated_at_dxb": datetime.now(DXB).isoformat(),
        "ok": True,
        "eligible_symbols": eligible,
        "focus_tier_1": focus_tier_1,
        "focus_tier_2": focus_tier_2,
        "rejected_symbols": rejected[:25],
    }
    state["focus_symbols"] = [x["symbol"] for x in focus_tier_1]
    state["avoid_symbols"] = [x["symbol"] for x in rejected[:10]]

    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)

    return state
