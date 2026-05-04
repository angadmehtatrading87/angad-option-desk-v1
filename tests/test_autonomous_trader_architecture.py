from datetime import datetime, timedelta, timezone

from app.autonomous_trader_architecture import (
    Candidate,
    capital_allocation,
    detect_regime,
    score_candidate,
    validate_market_data,
)


def test_missing_snapshot_account_positions_watchlist():
    out = validate_market_data(None)
    assert out["ok"] is False
    out2 = validate_market_data({"timestamp": datetime.now(timezone.utc).isoformat(), "account": None, "positions": None, "watchlist": None})
    assert "missing_account" in out2["reasons"]
    assert "missing_positions" in out2["reasons"]
    assert "missing_watchlist" in out2["reasons"]


def test_stale_data_detection():
    old = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    out = validate_market_data({"timestamp": old, "account": {"equity": 1}, "positions": [], "watchlist": []})
    assert "stale_data" in out["reasons"]


def test_chop_regime_and_trend_regime_sizing():
    chop = [{"close": 100 + (0.01 if i % 2 == 0 else -0.01)} for i in range(30)]
    trend = [{"close": 100 + i * 0.5} for i in range(30)]
    rg_chop = detect_regime(chop)
    rg_trend = detect_regime(trend)
    s_chop = capital_allocation(100000, 20000, 80, rg_chop["regime"])
    s_trend = capital_allocation(100000, 20000, 80, rg_trend["regime"])
    assert rg_chop["regime"] in ("CHOP", "RANGE")
    assert rg_trend["regime"] == "TREND"
    assert s_trend["recommended_notional"] > s_chop["recommended_notional"]


def test_30pct_reserve_and_underutilization():
    out = capital_allocation(100000, 10000, 56, "CHOP")
    assert out["liquidity_reserve"] == 30000
    assert out["under_utilization_detected"] is True


def test_high_conviction_vs_weak_rejection_signal():
    c = Candidate("A", "long", 0.6, 85, 88, 80, 70, 2.3, 82)
    rg = {"regime": "TREND", "confidence": 84}
    scored = score_candidate(c, rg)
    assert scored["tradability_score"] > 70
    w = Candidate("A", "long", 4.0, 30, 35, 40, 50, 1.1, 42)
    scored_w = score_candidate(w, {"regime": "CHOP", "confidence": 45})
    assert scored_w["tradability_score"] < scored["tradability_score"]
