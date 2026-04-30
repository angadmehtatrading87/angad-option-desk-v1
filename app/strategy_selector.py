from app.strategy_registry import STRATEGY_REGISTRY
from app.adaptive_learning import strategy_score_adjustment

def infer_market_view(row, regime):
    chg = float(row.get("change_pct") or 0)

    if regime == "RISK_OFF":
        if chg <= -1.0:
            return {
                "direction": "bearish",
                "vol_view": "vol_buy",
                "shape": "trend_down",
                "conviction": "high",
            }
        return {
            "direction": "bearish",
            "vol_view": "vol_sell",
            "shape": "range_down",
            "conviction": "medium",
        }

    if regime == "RISK_ON":
        if chg >= 1.0:
            return {
                "direction": "bullish",
                "vol_view": "vol_sell",
                "shape": "trend_up",
                "conviction": "high",
            }
        return {
            "direction": "bullish",
            "vol_view": "vol_buy",
            "shape": "trend_up",
            "conviction": "medium",
        }

    # MIXED / NEUTRAL
    if chg <= -2.0:
        return {
            "direction": "bearish",
            "vol_view": "vol_buy",
            "shape": "trend_down",
            "conviction": "medium",
        }
    if chg >= 2.0:
        return {
            "direction": "bullish",
            "vol_view": "vol_buy",
            "shape": "trend_up",
            "conviction": "medium",
        }
    return {
        "direction": "neutral",
        "vol_view": "vol_sell",
        "shape": "range_bound",
        "conviction": "medium",
    }

def score_strategy(view, strategy_name, meta):
    tags = set(meta.get("view_tags", []))
    score = 0

    if view["direction"] in tags:
        score += 30
    if view["shape"] in tags:
        score += 30
    if view["vol_view"] in tags:
        score += 25

    if view["conviction"] == "high" and meta.get("defined_risk", False):
        score += 10
    if meta.get("execution_ready", False):
        score += 20

    return score

def choose_strategy_families(top_opportunities, regime):
    chosen = []

    for row in top_opportunities:
        view = infer_market_view(row, regime)
        ranked = []

        for name, meta in STRATEGY_REGISTRY.items():
            s = score_strategy(view, name, meta) + strategy_score_adjustment(name)
            ranked.append({
                "strategy_name": name,
                "family": meta.get("family"),
                "execution_ready": meta.get("execution_ready", False),
                "score": s,
            })

        ranked = sorted(ranked, key=lambda x: x["score"], reverse=True)

        chosen.append({
            "symbol": row.get("symbol"),
            "market_view": view,
            "top_strategy_choices": ranked[:5],
            "execution_ready_choices": [x for x in ranked if x["execution_ready"]][:3],
        })

    return chosen
