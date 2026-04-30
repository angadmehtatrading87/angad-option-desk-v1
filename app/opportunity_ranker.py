import json
from datetime import datetime
from zoneinfo import ZoneInfo
from app.market_prep_brain import load_market_prep_state, STATE_PATH
from app.adaptive_learning import symbol_score_adjustment

DXB = ZoneInfo("Asia/Dubai")

def rank_opportunities():
    state = load_market_prep_state()
    dyn = state.get("dynamic_universe", {})
    regime = state.get("regime_view", {}).get("regime", "MIXED")
    ranked = []

    for row in dyn.get("eligible_symbols", []):
        base = row.get("score", 0)
        symbol = row["symbol"]
        reasons = list(row.get("reasons", []))
        structure_bias = []
        structure_score = 0
        chg = row.get("change_pct") or 0

        if regime == "RISK_ON":
            if chg > 0:
                structure_bias = ["call_debit_spread", "put_credit_spread"]
                structure_score += 12
            else:
                structure_bias = ["put_debit_spread"]
                structure_score += 4

        elif regime == "RISK_OFF":
            if chg < 0:
                structure_bias = ["put_debit_spread"]
                structure_score += 12
            else:
                structure_bias = ["call_debit_spread"]
                structure_score -= 8

        else:  # MIXED
            if chg <= -1:
                structure_bias = ["put_debit_spread"]
                structure_score += 10
            elif chg >= 1:
                structure_bias = ["call_debit_spread", "put_credit_spread"]
                structure_score += 10
            else:
                structure_bias = ["call_debit_spread", "put_debit_spread"]
                structure_score += 2

        total_score = base + structure_score + symbol_score_adjustment(symbol)

        ranked.append({
            "symbol": symbol,
            "opportunity_score": total_score,
            "change_pct": row.get("change_pct"),
            "spread_pct": row.get("spread_pct"),
            "volume": row.get("volume"),
            "last": row.get("last"),
            "reasons": reasons,
            "preferred_structures": structure_bias,
        })

    ranked = sorted(ranked, key=lambda x: x["opportunity_score"], reverse=True)

    state["opportunity_ranking"] = {
        "generated_at_dxb": datetime.now(DXB).isoformat(),
        "regime": regime,
        "top_opportunities": ranked[:10],
        "top_trade_focus": ranked[:5],
    }

    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)

    return state
