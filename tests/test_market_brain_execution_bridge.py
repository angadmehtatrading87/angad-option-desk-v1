from types import SimpleNamespace

from app import market_brain_execution_bridge as b


def _out(opps, thesis, cap=None):
    if cap is None:
        cap = SimpleNamespace(total_capital=100000, min_reserve=30000, current_used_capital=20000, deployable_capital=50000, unused_capital=80000, recommendation_note="note")
    return SimpleNamespace(generated_at="2026-05-04T00:00:00Z", opportunities=opps, thesis=thesis, rejected=[], capital=cap)


def test_high_conviction_creates_candidate(monkeypatch):
    monkeypatch.setenv("MARKET_BRAIN_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MARKET_BRAIN_EXECUTION_MODE", "demo")
    monkeypatch.setattr(b.MarketBrainIGAdapter, "get_watchlist", lambda self: [{"epic": "CS.D.EURUSD.CFD.IP"}])
    monkeypatch.setattr(b.MarketBrainIGAdapter, "get_account", lambda self: {"balance": 100000, "equity": 100000, "available": 80000})
    monkeypatch.setattr(b.MarketBrainIGAdapter, "get_positions", lambda self: [])
    monkeypatch.setattr(b.MarketBrainIGAdapter, "get_candles", lambda self, epics: {})
    opp = SimpleNamespace(epic="CS.D.EURUSD.CFD.IP", direction="long", action="trade", opportunity_score=88, confidence_score=84, rr_ratio=2.1, friction_cost_estimate=0.0008, components={})
    th = SimpleNamespace(epic="CS.D.EURUSD.CFD.IP", recommended_size=6000, why_direction="trend", why_now="breakout", structure="clean")
    monkeypatch.setattr(b, "run_market_brain", lambda *_args, **_kwargs: _out([opp], [th]))
    out = b.build_market_brain_execution_pick()
    assert out["ok"] is True
    assert len(out["decisions"]) == 1


def test_rejections_and_reserve_protection(monkeypatch):
    monkeypatch.setenv("MARKET_BRAIN_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MARKET_BRAIN_EXECUTION_MODE", "simulation")
    monkeypatch.setattr(b.MarketBrainIGAdapter, "get_watchlist", lambda self: [{"epic": "A"}])
    monkeypatch.setattr(b.MarketBrainIGAdapter, "get_account", lambda self: {"balance": 100000, "equity": 100000, "available": 1000})
    monkeypatch.setattr(b.MarketBrainIGAdapter, "get_positions", lambda self: [])
    monkeypatch.setattr(b.MarketBrainIGAdapter, "get_candles", lambda self, epics: {})
    cap = SimpleNamespace(total_capital=100000, min_reserve=30000, current_used_capital=75000, deployable_capital=5000, unused_capital=25000, recommendation_note="note")
    opp = SimpleNamespace(epic="A", direction="long", action="trade", opportunity_score=55, confidence_score=50, rr_ratio=1.0, friction_cost_estimate=0.004, components={})
    th = SimpleNamespace(epic="A", recommended_size=100, why_direction="x", why_now="y", structure="z")
    monkeypatch.setattr(b, "run_market_brain", lambda *_args, **_kwargs: _out([opp], [th], cap=cap))
    out = b.build_market_brain_execution_pick()
    assert len(out["decisions"]) == 0
    reason = out["skips"][0]["reason"]
    assert "bad_spread_friction" in reason
    assert "liquidity_reserve_protection" in reason


def test_live_mode_blocked(monkeypatch):
    monkeypatch.setenv("MARKET_BRAIN_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MARKET_BRAIN_EXECUTION_MODE", "live")
    out = b.build_market_brain_execution_pick()
    assert out["ok"] is False
    assert "demo_or_simulation" in out["reason"][0]
