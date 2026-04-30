import yaml
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_risk_config():
    with open(os.path.join(BASE_DIR, "config", "risk_limits.yaml"), "r") as f:
        return yaml.safe_load(f)

def evaluate_trade(strategy, max_risk, dte):
    risk = load_risk_config()
    reasons = []

    if risk.get("kill_switch", False):
        reasons.append("Kill switch is active.")

    if strategy in risk.get("blocked_trade_types", []):
        reasons.append(f"Strategy {strategy} is blocked.")

    if strategy not in risk.get("allowed_trade_types", []):
        reasons.append(f"Strategy {strategy} is not in allowed trade types.")

    if max_risk > risk.get("max_risk_per_trade_usd", 0):
        reasons.append(
            f"Max risk ${max_risk} exceeds allowed ${risk.get('max_risk_per_trade_usd')}."
        )

    if dte < risk.get("min_days_to_expiry", 0):
        reasons.append(
            f"DTE {dte} is below minimum {risk.get('min_days_to_expiry')}."
        )

    if dte > risk.get("max_days_to_expiry", 999):
        reasons.append(
            f"DTE {dte} is above maximum {risk.get('max_days_to_expiry')}."
        )

    if reasons:
        return {
            "passed": False,
            "result": "FAILED",
            "reason": " ".join(reasons)
        }

    return {
        "passed": True,
        "result": "PASSED",
        "reason": "Trade passed current risk rules."
    }
