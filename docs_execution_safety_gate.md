# Unified Execution Safety Gate (PR-0.1)

This module centralizes pre-execution safety checks before any order submission path runs.

## Module
- `app/execution_safety_guard.py`

## Enforced checks
1. Kill switch (`config/risk_limits.yaml`)
2. Explicit account mode sanity (`simulation|demo|live`)
3. Market/session eligibility
4. Snapshot freshness (stale snapshot rejection)
5. Burst order throttling by time window
6. Capital safety via minimum 30% liquidity reserve

## Response contract
`evaluate_execution_safety(...)` returns:
- `ok`: bool
- `mode`: `ALLOW|REJECT`
- `reasons`: machine-readable rejection reasons
- `metadata`: operational context (burst counters, liquidity ratio)

## Integration points
- `app/ig_execution_worker.py`
- `app/ig_execution_engine.py`
- `app/autonomous_execution_worker.py`
- `app/auto_trade_worker.py`

## Extension guide
To add a new rule:
1. Add a deterministic check in `evaluate_execution_safety`.
2. Emit a clear machine reason in `reasons`.
3. Add unit tests in `tests/test_execution_safety_guard.py` for allow + reject paths.
4. Keep default posture fail-closed (reject on uncertain state).

## Notes
- This gate does not alter strategy or signal generation logic.
- It only blocks unsafe execution states and defaults uncertain states to reject/observe-only.
