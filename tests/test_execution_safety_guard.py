import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime, timezone

from app import execution_safety_guard as g


def _ok_snapshot(ts):
    return {
        "ok": True,
        "timestamp": ts.isoformat(),
        "account": {"equity": 1000.0, "available": 400.0},
    }


def test_allows_when_safe(monkeypatch, tmp_path):
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(g, "get_ig_session_state", lambda: {"session": "london", "market_open": True})
    monkeypatch.setattr(g, "_load_yaml", lambda p: {"kill_switch": False, "account_mode": "simulation"})
    monkeypatch.setattr(g, "_load_json", lambda p: {"demo_only": True, "safety_max_snapshot_age_seconds": 120, "safety_burst_window_seconds": 120, "safety_max_burst_orders": 3})

    result = g.evaluate_execution_safety(
        channel="unit",
        expected_order_count=1,
        ig_snapshot=_ok_snapshot(now),
        now=now,
        burst_state_path=str(tmp_path / "burst.json"),
    )
    assert result["ok"] is True
    assert result["reasons"] == []


def test_rejects_killswitch_and_low_liquidity(monkeypatch, tmp_path):
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(g, "get_ig_session_state", lambda: {"session": "london", "market_open": True})
    monkeypatch.setattr(g, "_load_yaml", lambda p: {"kill_switch": True, "account_mode": "simulation"})
    monkeypatch.setattr(g, "_load_json", lambda p: {"demo_only": True, "safety_max_snapshot_age_seconds": 120, "safety_burst_window_seconds": 120, "safety_max_burst_orders": 3})
    snap = {"ok": True, "timestamp": now.isoformat(), "account": {"equity": 1000.0, "available": 200.0}}

    result = g.evaluate_execution_safety("unit", ig_snapshot=snap, now=now, burst_state_path=str(tmp_path / "burst.json"))
    assert result["ok"] is False
    assert "kill_switch_active" in result["reasons"]
    assert "liquidity_reserve_below_30pct" in result["reasons"]


def test_rejects_stale_snapshot_and_burst(monkeypatch, tmp_path):
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(g, "get_ig_session_state", lambda: {"session": "london", "market_open": True})
    monkeypatch.setattr(g, "_load_yaml", lambda p: {"kill_switch": False, "account_mode": "simulation"})
    monkeypatch.setattr(g, "_load_json", lambda p: {"demo_only": True, "safety_max_snapshot_age_seconds": 60, "safety_burst_window_seconds": 120, "safety_max_burst_orders": 2})

    burst = tmp_path / "burst.json"
    g.record_execution_attempt(count=2, now=now, burst_state_path=str(burst))
    stale = now.replace(year=now.year - 1)
    result = g.evaluate_execution_safety("unit", expected_order_count=1, ig_snapshot=_ok_snapshot(stale), now=now, burst_state_path=str(burst))
    assert result["ok"] is False
    assert "snapshot_stale" in result["reasons"]
    assert "max_burst_orders_exceeded" in result["reasons"]
