import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime, timedelta, timezone

from app import execution_two_phase_commit as tpc


def test_prepare_rejects_duplicate_active_intent(tmp_path):
    state = str(tmp_path / "two_phase.json")
    now = datetime.now(timezone.utc)

    first = tpc.prepare_intent("CS.D.EURUSD.CFD.IP", "BUY", 2.0, now=now, state_path=state)
    assert first["ok"] is True

    second = tpc.prepare_intent("CS.D.EURUSD.CFD.IP", "BUY", 2.0, now=now + timedelta(seconds=5), state_path=state)
    assert second["ok"] is False
    assert second["reason"] == "intent_already_prepared"


def test_prepare_allows_after_abort_and_finalize_commit(tmp_path):
    state = str(tmp_path / "two_phase.json")
    now = datetime.now(timezone.utc)

    prepared = tpc.prepare_intent("CS.D.GBPUSD.CFD.IP", "SELL", 1.3, now=now, state_path=state)
    assert prepared["ok"] is True

    aborted = tpc.finalize_intent(prepared["intent_key"], "ABORTED", now=now, note="unit_test_abort", state_path=state)
    assert aborted["ok"] is True

    retry = tpc.prepare_intent("CS.D.GBPUSD.CFD.IP", "SELL", 1.3, now=now + timedelta(seconds=2), state_path=state)
    assert retry["ok"] is True

    committed = tpc.finalize_intent(retry["intent_key"], "COMMITTED", deal_reference="DREF1", deal_id="DID1", now=now, state_path=state)
    assert committed["ok"] is True
