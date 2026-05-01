from .instrument_research import instrument_profiles
from .macro_research import macro_snapshot
from .sentiment_research import sentiment_snapshot

def build_research_context(db_reader=None):
    macro = macro_snapshot()
    sentiment = sentiment_snapshot()
    profiles = instrument_profiles(db_reader)
    return {
        "market_bias": macro["market_regime"],
        "session_bias": macro["session_bias"],
        "volatility_bias": macro["volatility_state"],
        "preferred_instruments": [k for k, v in profiles.items() if v.get("rating") in {"tradable", "high conviction"}],
        "avoid_instruments": [k for k, v in profiles.items() if v.get("rating") == "avoid"],
        "risk_level": macro["risk_level"],
        "confidence_adjustments": {},
        "sizing_adjustments": {},
        "regime_notes": macro["notes"],
        "active_warnings": sentiment["warnings"],
        "opportunities_to_watch": macro["opportunities"],
    }
