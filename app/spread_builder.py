from app.option_chain import get_chain_summary
from app.risk_engine import evaluate_trade
from app.decision_engine import score_trade
from app.trade_store import create_trade
from app.quote_engine import quote_options, quote_quality
from app.news_macro import latest_news_macro

MAX_RISK_LIMIT = 100000.0

def macro_headline_regime():
    data = latest_news_macro()
    snap = (data or {}).get("snapshot") or {}
    return snap.get("macro_regime", "NEUTRAL"), snap.get("summary", "No macro summary.")

def safe_float(value, default=None):
    try:
        return float(value)
    except Exception:
        return default

def usable_strikes(strikes):
    cleaned = []
    for s in strikes:
        strike = safe_float(s.get("strike_price"))
        if strike is None:
            continue
        if s.get("call_symbol") or s.get("put_symbol"):
            cleaned.append({
                "strike": strike,
                "strike_price": s.get("strike_price"),
                "call_symbol": s.get("call_symbol"),
                "put_symbol": s.get("put_symbol"),
            })
    return sorted(cleaned, key=lambda x: x["strike"])

def calculate_debit_spread(buy_symbol, sell_symbol, quotes):
    buy_q = quotes.get(buy_symbol)
    sell_q = quotes.get(sell_symbol)

    buy_quality = quote_quality(buy_q)
    sell_quality = quote_quality(sell_q)

    if not buy_quality["ok"]:
        return None, f"Buy leg quote issue: {buy_quality['reason']}"
    if not sell_quality["ok"]:
        return None, f"Sell leg quote issue: {sell_quality['reason']}"

    debit = (buy_q["ask"] or 0) - (sell_q["bid"] or 0)
    if debit <= 0:
        return None, "Invalid debit calculation."

    max_risk = round(debit * 100, 2)
    target_profit = round(max_risk * 0.65, 2)
    stop_loss = round(max_risk * 0.50, 2)
    quality_score = round((buy_quality["score"] + sell_quality["score"]) / 2, 2)

    return {
        "estimated_debit": round(debit, 2),
        "estimated_credit": None,
        "max_risk": max_risk,
        "target_profit": target_profit,
        "stop_loss": stop_loss,
        "quality_score": quality_score,
        "quote_quality": f"Buy score {buy_quality['score']}, Sell score {sell_quality['score']}"
    }, None

def calculate_credit_spread(sell_symbol, buy_symbol, sell_strike, buy_strike, quotes):
    sell_q = quotes.get(sell_symbol)
    buy_q = quotes.get(buy_symbol)

    sell_quality = quote_quality(sell_q)
    buy_quality = quote_quality(buy_q)

    if not sell_quality["ok"]:
        return None, f"Sell leg quote issue: {sell_quality['reason']}"
    if not buy_quality["ok"]:
        return None, f"Buy leg quote issue: {buy_quality['reason']}"

    credit = (sell_q["bid"] or 0) - (buy_q["ask"] or 0)
    if credit <= 0:
        return None, "Invalid credit calculation."

    width = abs(float(sell_strike) - float(buy_strike))
    max_risk = round((width - credit) * 100, 2)
    if max_risk <= 0:
        return None, "Invalid max risk calculation."

    target_profit = round(credit * 100 * 0.60, 2)
    stop_loss = round(max_risk * 0.50, 2)
    quality_score = round((sell_quality["score"] + buy_quality["score"]) / 2, 2)

    return {
        "estimated_credit": round(credit, 2),
        "estimated_debit": None,
        "max_risk": max_risk,
        "target_profit": target_profit,
        "stop_loss": stop_loss,
        "quality_score": quality_score,
        "quote_quality": f"Sell score {sell_quality['score']}, Buy score {buy_quality['score']}"
    }, None

def candidate_snapshot(setup_name, quality_score):
    if setup_name == "call_debit_spread":
        return {"trend_score": 72, "volatility_score": 52, "liquidity_score": min(100, max(60, quality_score))}
    if setup_name == "put_debit_spread":
        return {"trend_score": 30, "volatility_score": 55, "liquidity_score": min(100, max(60, quality_score))}
    return {"trend_score": 52, "volatility_score": 60, "liquidity_score": min(100, max(60, quality_score))}

def build_spread_candidates(symbol):
    chain = get_chain_summary(symbol, min_dte=21, max_dte=45, max_expiries=3)
    candidates = []

    for expiry in chain.get("expiries", []):
        strikes = usable_strikes(expiry.get("sample_strikes", []))
        if len(strikes) < 8:
            continue

        mid = len(strikes) // 2
        subset = strikes[max(0, mid - 6): min(len(strikes), mid + 6)]

        needed_symbols = []
        for s in subset:
            if s.get("call_symbol"):
                needed_symbols.append(s["call_symbol"])
            if s.get("put_symbol"):
                needed_symbols.append(s["put_symbol"])

        quotes = quote_options(list(set(needed_symbols)))

        for i in range(len(subset) - 1):
            lower = subset[i]
            higher = subset[i + 1]

            if lower.get("call_symbol") and higher.get("call_symbol") and lower["strike"] < higher["strike"]:
                pricing, _ = calculate_debit_spread(lower["call_symbol"], higher["call_symbol"], quotes)
                if pricing and pricing["max_risk"] <= MAX_RISK_LIMIT:
                    candidates.append({
                        "symbol": symbol.upper(),
                        "strategy": "debit_spread",
                        "setup_name": "call_debit_spread",
                        "expiry": f'{expiry["expiration_date"]} / {expiry["dte"]} DTE',
                        "expiry_date_only": expiry["expiration_date"],
                        "dte": expiry["dte"],
                        "legs": f'Buy {lower["call_symbol"]} / Sell {higher["call_symbol"]}',
                        "estimated_credit": pricing["estimated_credit"],
                        "estimated_debit": pricing["estimated_debit"],
                        "max_risk": pricing["max_risk"],
                        "target_profit": pricing["target_profit"],
                        "stop_loss": pricing["stop_loss"],
                        "quality_score": pricing["quality_score"],
                        "reason": f"Real-priced call debit spread. {pricing['quote_quality']}"
                    })

            if higher.get("put_symbol") and lower.get("put_symbol") and lower["strike"] < higher["strike"]:
                pricing, _ = calculate_debit_spread(higher["put_symbol"], lower["put_symbol"], quotes)
                if pricing and pricing["max_risk"] <= MAX_RISK_LIMIT:
                    candidates.append({
                        "symbol": symbol.upper(),
                        "strategy": "debit_spread",
                        "setup_name": "put_debit_spread",
                        "expiry": f'{expiry["expiration_date"]} / {expiry["dte"]} DTE',
                        "expiry_date_only": expiry["expiration_date"],
                        "dte": expiry["dte"],
                        "legs": f'Buy {higher["put_symbol"]} / Sell {lower["put_symbol"]}',
                        "estimated_credit": pricing["estimated_credit"],
                        "estimated_debit": pricing["estimated_debit"],
                        "max_risk": pricing["max_risk"],
                        "target_profit": pricing["target_profit"],
                        "stop_loss": pricing["stop_loss"],
                        "quality_score": pricing["quality_score"],
                        "reason": f"Real-priced put debit spread. {pricing['quote_quality']}"
                    })

            if higher.get("put_symbol") and lower.get("put_symbol") and lower["strike"] < higher["strike"]:
                pricing, _ = calculate_credit_spread(higher["put_symbol"], lower["put_symbol"], higher["strike"], lower["strike"], quotes)
                if pricing and pricing["max_risk"] <= MAX_RISK_LIMIT:
                    candidates.append({
                        "symbol": symbol.upper(),
                        "strategy": "put_credit_spread",
                        "setup_name": "put_credit_spread",
                        "expiry": f'{expiry["expiration_date"]} / {expiry["dte"]} DTE',
                        "expiry_date_only": expiry["expiration_date"],
                        "dte": expiry["dte"],
                        "legs": f'Sell {higher["put_symbol"]} / Buy {lower["put_symbol"]}',
                        "estimated_credit": pricing["estimated_credit"],
                        "estimated_debit": pricing["estimated_debit"],
                        "max_risk": pricing["max_risk"],
                        "target_profit": pricing["target_profit"],
                        "stop_loss": pricing["stop_loss"],
                        "quality_score": pricing["quality_score"],
                        "reason": f"Real-priced put credit spread. {pricing['quote_quality']}"
                    })

    candidates = sorted(candidates, key=lambda x: (-x.get("quality_score", 0), x.get("max_risk", 9999)))
    return candidates[:12]

def dedupe_candidates(candidates):
    buckets = {}
    for c in candidates:
        key = (c["symbol"], c["setup_name"], c["expiry_date_only"])
        buckets.setdefault(key, []).append(c)

    deduped = []
    blocked = []

    for _, items in buckets.items():
        items = sorted(items, key=lambda x: (x["max_risk"], -x.get("quality_score", 0)))
        deduped.append(items[0])
        blocked.extend(items[1:])

    deduped = sorted(deduped, key=lambda x: (-x.get("quality_score", 0), x.get("max_risk", 9999)))
    return deduped[:6], blocked

def propose_spread_candidates(symbol):
    raw_candidates = build_spread_candidates(symbol)
    candidates, duplicate_blocked = dedupe_candidates(raw_candidates)
    created = []

    regime, regime_summary = macro_headline_regime()

    for trade in candidates:
        snapshot = candidate_snapshot(trade["setup_name"], trade.get("quality_score", 70))
        snapshot["symbol"] = trade["symbol"]

        if regime == "RISK_OFF":
            if trade["setup_name"] == "call_debit_spread":
                snapshot["trend_score"] = max(0, snapshot["trend_score"] - 25)
                snapshot["volatility_score"] = min(100, snapshot["volatility_score"] + 10)
            elif trade["setup_name"] == "put_debit_spread":
                snapshot["trend_score"] = min(100, snapshot["trend_score"] + 10)
            elif trade["setup_name"] == "put_credit_spread":
                snapshot["trend_score"] = max(0, snapshot["trend_score"] - 10)
        elif regime == "RISK_ON":
            if trade["setup_name"] == "call_debit_spread":
                snapshot["trend_score"] = min(100, snapshot["trend_score"] + 10)

        risk_eval = evaluate_trade(
            strategy=trade["strategy"],
            max_risk=trade["max_risk"],
            dte=trade["dte"]
        )

        decision = score_trade(trade, snapshot, risk_eval)

        if regime == "RISK_OFF" and trade["setup_name"] == "call_debit_spread":
            final_status = "BLOCKED"
        elif not risk_eval["passed"]:
            final_status = "BLOCKED"
        elif decision["agent_view"] == "APPROVE" and decision["grade"] == "A":
            final_status = "AUTONOMOUS_CANDIDATE"
        else:
            final_status = "WATCH_ONLY"

        full_reason = (
            f"Macro regime: {regime}. {regime_summary} "
            f"{trade['reason']} "
            f"Decision: {decision['summary']} "
            f"Risk: {risk_eval['reason']}"
        )

        trade_id = create_trade(
            symbol=trade["symbol"],
            strategy=trade["strategy"],
            expiry=trade["expiry"],
            legs=trade["legs"],
            estimated_credit=trade["estimated_credit"],
            estimated_debit=trade["estimated_debit"],
            max_risk=trade["max_risk"],
            target_profit=trade["target_profit"],
            stop_loss=trade["stop_loss"],
            status=final_status,
            reason=full_reason,
            risk_result=risk_eval["result"],
            decision=decision
        )

        created.append({
            "trade_id": trade_id,
            "symbol": trade["symbol"],
            "strategy": trade["strategy"],
            "setup_name": trade["setup_name"],
            "status": final_status,
            "grade": decision["grade"],
            "agent_view": decision["agent_view"],
            "confidence": decision["confidence_score"],
            "max_risk": trade["max_risk"],
            "estimated_debit": trade["estimated_debit"],
            "estimated_credit": trade["estimated_credit"],
            "quality_score": trade.get("quality_score"),
        })

    for trade in duplicate_blocked:
        risk_eval = evaluate_trade(
            strategy=trade["strategy"],
            max_risk=trade["max_risk"],
            dte=trade["dte"]
        )
        create_trade(
            symbol=trade["symbol"],
            strategy=trade["strategy"],
            expiry=trade["expiry"],
            legs=trade["legs"],
            estimated_credit=trade["estimated_credit"],
            estimated_debit=trade["estimated_debit"],
            max_risk=trade["max_risk"],
            target_profit=trade["target_profit"],
            stop_loss=trade["stop_loss"],
            status="BLOCKED_DUPLICATE_PROPOSAL",
            reason="Blocked at proposal stage due to duplicate same-family setup.",
            risk_result=risk_eval["result"],
            decision={"grade": "D", "agent_view": "REJECT", "confidence_score": 0}
        )

    return created
