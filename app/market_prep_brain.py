import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from app.news_macro import latest_news_macro
from app.agent_policy import load_agent_policy

DXB = ZoneInfo("Asia/Dubai")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(BASE_DIR, "data", "market_prep_state.json")

def now_dxb_iso():
    return datetime.now(DXB).isoformat()

def macro_snapshot():
    data = latest_news_macro()
    snap = (data or {}).get("snapshot") or {}
    return {
        "macro_regime": snap.get("macro_regime", "NEUTRAL"),
        "summary": snap.get("summary", "No macro summary."),
        "risk_on_score": snap.get("risk_on_score", 0),
        "risk_off_score": snap.get("risk_off_score", 0),
        "headline_count": snap.get("headline_count", 0),
    }

def classify_regime(macro):
    regime = macro.get("macro_regime", "NEUTRAL")
    if regime == "RISK_ON":
        return {
            "regime": "RISK_ON",
            "style": "trend_follow",
            "confidence": 68,
            "preferred_structures": ["call_debit_spread", "put_credit_spread"],
            "forbidden_structures": ["low-conviction bearish debit spreads"],
            "session_note": "Constructive tape. Favor strength, but avoid sloppy entries."
        }
    if regime == "RISK_OFF":
        return {
            "regime": "RISK_OFF",
            "style": "defensive",
            "confidence": 72,
            "preferred_structures": ["put_debit_spread"],
            "forbidden_structures": ["bullish call debit spreads without clear reversal confirmation"],
            "session_note": "Defensive tape. Favor weakness or stay selective."
        }
    return {
        "regime": "MIXED",
        "style": "selective",
        "confidence": 55,
        "preferred_structures": ["only highest-quality directional spreads"],
        "forbidden_structures": ["random low-conviction entries", "duplicate same-thesis exposure"],
        "session_note": "Mixed tape. Trade only if setup quality is clearly superior."
    }

def build_market_prep_state():
    policy = load_agent_policy()
    macro = macro_snapshot()
    regime_view = classify_regime(macro)
    state = {
        "generated_at_dxb": now_dxb_iso(),
        "policy": policy,
        "macro": macro,
        "regime_view": regime_view,
        "focus_groups": [],
        "avoid_groups": [],
        "focus_symbols": [],
        "avoid_symbols": [],
        "session_plan": {
            "max_new_entries": policy.get("execution", {}).get("max_new_entries_per_session", 3),
            "telegram_trade_alerts_enabled": policy.get("communications", {}).get("telegram_trade_alerts_enabled", False),
            "owner_briefing_only": policy.get("communications", {}).get("telegram_owner_briefing_only", True),
        },
        "notes": [
            "Phase 1 market prep state created.",
            "Dynamic universe selection and opportunity ranking will populate focus symbols."
        ]
    }
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)
    return state

def load_market_prep_state():
    if not os.path.exists(STATE_PATH):
        return build_market_prep_state()
    with open(STATE_PATH, "r") as f:
        return json.load(f)
