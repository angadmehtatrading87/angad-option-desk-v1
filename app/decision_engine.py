def score_trade(trade, snapshot, risk_eval):
    trend = snapshot.get("trend_score", 50)
    volatility = snapshot.get("volatility_score", 50)
    liquidity = snapshot.get("liquidity_score", 50)
    max_risk = trade.get("max_risk", 999)
    target_profit = trade.get("target_profit", 0)
    strategy = trade.get("strategy", "")

    reasons_for = []
    reasons_against = []

    if not risk_eval.get("passed"):
        return {
            "grade": "D",
            "agent_view": "REJECT",
            "confidence_score": 0,
            "trend_score": trend,
            "volatility_score": volatility,
            "liquidity_score": liquidity,
            "macro_risk_score": 50,
            "risk_reward_score": 0,
            "reasons_for": [],
            "reasons_against": [risk_eval.get("reason", "Risk engine failed.")],
            "summary": "Trade rejected by hard risk rules."
        }

    trend_component = 0
    if strategy == "debit_spread":
        if trend >= 65 or trend <= 35:
            trend_component = 25
            reasons_for.append("Clear directional trend detected.")
        else:
            trend_component = 10
            reasons_against.append("Directional conviction is not strong.")
    elif strategy == "put_credit_spread":
        if 40 <= trend <= 65:
            trend_component = 20
            reasons_for.append("Market is neutral-to-firm, suitable for put credit spread.")
        else:
            trend_component = 8
            reasons_against.append("Trend is not ideal for put credit spread.")
    else:
        reasons_against.append("Strategy not preferred by Decision Engine v1.")

    vol_component = 0
    if strategy == "put_credit_spread":
        if 50 <= volatility <= 75:
            vol_component = 20
            reasons_for.append("Volatility is elevated enough for premium selling.")
        elif volatility > 80:
            vol_component = 5
            reasons_against.append("Volatility is too high; risk-off/event risk possible.")
        else:
            vol_component = 10
            reasons_against.append("Premium may be too low for credit spread.")
    else:
        if volatility <= 70:
            vol_component = 18
            reasons_for.append("Volatility is acceptable for debit spread.")
        else:
            vol_component = 8
            reasons_against.append("Volatility is high; debit spread pricing may be expensive.")

    liquidity_component = 0
    if liquidity >= 85:
        liquidity_component = 25
        reasons_for.append("Liquidity score is strong.")
    elif liquidity >= 70:
        liquidity_component = 18
        reasons_for.append("Liquidity is acceptable.")
    else:
        liquidity_component = 5
        reasons_against.append("Liquidity is weak; fills may be poor.")

    rr_component = 0
    if max_risk <= 50:
        rr_component += 10
        reasons_for.append("Max risk is within small account limit.")
    else:
        reasons_against.append("Max risk too high for current account size.")

    rr_ratio = target_profit / max_risk if max_risk else 0

    if rr_ratio >= 0.50:
        rr_component += 10
        reasons_for.append("Risk/reward is acceptable.")
    elif rr_ratio >= 0.30:
        rr_component += 5
        reasons_against.append("Risk/reward is only moderate.")
    else:
        reasons_against.append("Risk/reward is poor.")

    macro_risk_score = 50
    macro_component = 10
    reasons_for.append("Macro/geopolitical filter is neutral in v1 placeholder.")

    total = trend_component + vol_component + liquidity_component + rr_component + macro_component

    if total >= 80:
        grade = "A"
        agent_view = "APPROVE"
        summary = "High-quality setup under current rules."
    elif total >= 65:
        grade = "B"
        agent_view = "WATCH"
        summary = "Acceptable setup, but not top quality."
    elif total >= 50:
        grade = "C"
        agent_view = "WATCH"
        summary = "Weak setup. Better to wait."
    else:
        grade = "D"
        agent_view = "REJECT"
        summary = "Reject. Setup quality is insufficient."

    return {
        "grade": grade,
        "agent_view": agent_view,
        "confidence_score": total,
        "trend_score": trend,
        "volatility_score": volatility,
        "liquidity_score": liquidity,
        "macro_risk_score": macro_risk_score,
        "risk_reward_score": round(rr_ratio * 100, 2),
        "reasons_for": reasons_for,
        "reasons_against": reasons_against,
        "summary": summary
    }
