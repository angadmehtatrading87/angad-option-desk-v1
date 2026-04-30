import random
from datetime import datetime, timezone
import yaml
import os

from app.risk_engine import evaluate_trade
from app.trade_store import create_trade, recent_similar_trade_exists
from app.telegram_alerts import send_telegram_message, send_trade_action_message
from app.decision_engine import score_trade

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_yaml(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def get_mock_market_snapshot(symbol):
    """
    Temporary scanner data.
    Later this will be replaced with live Tastytrade/IBKR market data.
    """
    trend_score = random.randint(20, 90)
    volatility_score = random.randint(20, 90)
    liquidity_score = random.randint(50, 100)

    return {
        "symbol": symbol,
        "trend_score": trend_score,
        "volatility_score": volatility_score,
        "liquidity_score": liquidity_score,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

def choose_strategy(snapshot):
    trend = snapshot["trend_score"]
    vol = snapshot["volatility_score"]
    liquidity = snapshot["liquidity_score"]

    if liquidity < 60:
        return None, "Liquidity score too low."

    if trend >= 65 and vol <= 75:
        return "debit_spread", "Bullish trend detected. Defined-risk call debit spread proposed."

    if trend <= 35 and vol <= 80:
        return "debit_spread", "Bearish trend detected. Defined-risk put debit spread proposed."

    if 40 <= trend <= 60 and vol >= 55:
        return "put_credit_spread", "Neutral-to-firm market with elevated volatility. Put credit spread proposed."

    return None, "No clean setup based on current scanner rules."

def build_trade_from_snapshot(snapshot, strategy, reason):
    symbol = snapshot["symbol"]
    trend = snapshot["trend_score"]

    dte = random.choice([28, 32, 35, 42])

    if strategy == "debit_spread":
        if trend >= 65:
            legs = f"Buy {symbol} call / Sell higher {symbol} call"
            setup_name = "bullish_debit_spread"
        else:
            legs = f"Buy {symbol} put / Sell lower {symbol} put"
            setup_name = "bearish_debit_spread"

        estimated_debit = random.choice([28, 34, 42, 48])
        estimated_credit = None
        max_risk = estimated_debit
        target_profit = round(max_risk * 0.65, 2)
        stop_loss = round(max_risk * 0.50, 2)

    elif strategy == "put_credit_spread":
        setup_name = "put_credit_spread"
        legs = f"Sell {symbol} put / Buy lower {symbol} put"
        estimated_credit = random.choice([12, 15, 18, 22])
        spread_width = random.choice([50, 75, 100])
        max_risk = spread_width - estimated_credit
        estimated_debit = None
        target_profit = round(estimated_credit * 0.60, 2)
        stop_loss = round(max_risk * 0.50, 2)

    else:
        return None

    return {
        "symbol": symbol,
        "strategy": strategy,
        "setup_name": setup_name,
        "expiry": f"{dte} DTE",
        "dte": dte,
        "legs": legs,
        "estimated_credit": estimated_credit,
        "estimated_debit": estimated_debit,
        "max_risk": max_risk,
        "target_profit": target_profit,
        "stop_loss": stop_loss,
        "reason": reason,
        "scanner_snapshot": snapshot
    }

def run_scan():
    scanner_config = load_yaml(os.path.join(BASE_DIR, "config", "scanner.yaml"))
    symbols = scanner_config.get("symbols", [])
    max_proposals = scanner_config.get("proposal_limits", {}).get("max_proposals_per_scan", 3)

    created = []

    for symbol in symbols:
        if len(created) >= max_proposals:
            break

        snapshot = get_mock_market_snapshot(symbol)
        strategy, reason = choose_strategy(snapshot)

        if not strategy:
            continue

        trade = build_trade_from_snapshot(snapshot, strategy, reason)
        if not trade:
            continue

        duplicate_enabled = scanner_config.get("duplicate_protection", {}).get("enabled", True)
        cooldown_minutes = scanner_config.get("duplicate_protection", {}).get("cooldown_minutes", 180)

        if duplicate_enabled and recent_similar_trade_exists(
            symbol=trade["symbol"],
            strategy=trade["strategy"],
            cooldown_minutes=cooldown_minutes
        ):
            continue

        risk_eval = evaluate_trade(
            strategy=trade["strategy"],
            max_risk=trade["max_risk"],
            dte=trade["dte"]
        )

        decision = score_trade(trade, snapshot, risk_eval)

        if not risk_eval["passed"]:
            final_status = "BLOCKED"
        elif decision["agent_view"] == "APPROVE" and decision["grade"] == "A":
            final_status = "PENDING_APPROVAL"
        else:
            final_status = "WATCH_ONLY"

        full_reason = (
            f"{trade['reason']} "
            f"Trend score: {snapshot['trend_score']}. "
            f"Volatility score: {snapshot['volatility_score']}. "
            f"Liquidity score: {snapshot['liquidity_score']}. "
            f"Risk check: {risk_eval['reason']} "
            f"Decision: {decision['summary']}"
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
            "status": final_status,
            "symbol": trade["symbol"],
            "strategy": trade["strategy"],
            "max_risk": trade["max_risk"],
            "risk_result": risk_eval["result"]
        })

        if final_status == "PENDING_APPROVAL":
            msg = f"""
<b>Scanner Trade Proposal #{trade_id}</b>

Symbol: {trade["symbol"]}
Setup: {trade["setup_name"]}
Strategy: {trade["strategy"]}
Expiry: {trade["expiry"]}
Legs: {trade["legs"]}

Max Risk: ${trade["max_risk"]}
Target Profit: ${trade["target_profit"]}
Stop Loss: ${trade["stop_loss"]}

Trend Score: {snapshot["trend_score"]}
Volatility Score: {snapshot["volatility_score"]}
Liquidity Score: {snapshot["liquidity_score"]}

Risk Result: {risk_eval["result"]}
Agent Grade: {decision["grade"]}
Agent View: {decision["agent_view"]}
Confidence: {decision["confidence_score"]}/100

Decision Summary:
{decision["summary"]}

Why approve:
{"; ".join(decision["reasons_for"])}

Why reject / risks:
{"; ".join(decision["reasons_against"])}

Reply:
APPROVE {trade_id}
or
REJECT {trade_id}

Dashboard:
http://16.60.74.15
"""
        else:
            msg = f"""
<b>Scanner Blocked Trade #{trade_id}</b>

Symbol: {trade["symbol"]}
Strategy: {trade["strategy"]}
Max Risk: ${trade["max_risk"]}

Risk Result: {risk_eval["result"]}
Agent Grade: {decision["grade"]}
Agent View: {decision["agent_view"]}
Confidence: {decision["confidence_score"]}/100

Decision Summary:
{decision["summary"]}

Reason:
{risk_eval["reason"]}
"""

        if final_status == "PENDING_APPROVAL":
            send_trade_action_message(msg, trade_id)

    return created
