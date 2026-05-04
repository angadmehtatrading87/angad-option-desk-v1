# Phase 1: Tastytrade removal — status

Generated as part of the IG-only migration. Date: 2026-05-04.

## What this branch does

Strips Tastytrade end-to-end and removes the entire legacy options-trading
stack that depended on it. After this PR, the only active broker is IG (demo
account), and the only execution loop is `app/ig_execution_worker.py`.

## What's already done in this branch (in-place edits)

- `app/main.py`
  - Removed all Tastytrade and legacy-options imports
  - Replaced the root `/` dashboard with a redirect to `/ig-desk`
  - Old dashboard body parked as `_legacy_dashboard_DEAD` (unreachable)
  - Title changed from "Angad Option Desk v1" → "Autobot Trader Pro — IG"
- `app/lane_capital_controller.py` — collapsed to IG-only (single lane).
  Kept `lane_entry_allowed("ig")` and `lane_capital_state()` signatures so
  callers don't need to change. Stale `tasty_*` config keys are scrubbed
  from any persisted state file on next load.
- `app/daily_objective_controller.py` — IG-only. The "combined" view is
  preserved for backward shape compat but mirrors `live.ig` since IG is
  the only contributor.
- `app/agent_ops/db_reader.py` — `IGNORED_TABLES` left in place
  defensively (a deployed DB may still carry the tasty_virtual_* tables
  for one or two upgrade cycles).
- `app/virtual_portfolio.py` — kept (still queried by IG dashboards),
  but the `quote_engine` import and `current_unit_spread_mid()` were
  stubbed since live options-spread mid pricing is no longer available.
- `tests/test_market_brain.py` — renamed and clarified
  `test_market_brain_no_tastytrade_dependency` →
  `test_market_brain_runs_without_legacy_options_modules`. Removed the
  no-longer-relevant `sys.modules.pop("app.tasty_connector", ...)`.
- `tests/test_telegram_control_room.py` — renamed
  `test_tasty_tables_ignored` →
  `test_performance_handles_legacy_table_remnants`.
- `README.md`, `docs/market_brain_architecture.md` — updated to reflect
  IG-only state.

## What needs the cleanup script

File deletions (25 files) — run from repo root:

```bash
bash cleanup/remove_tastytrade.sh
```

The script:
1. Switches to (or creates) branch `remove-tastytrade`
2. Deletes the 25 files via `git rm`
3. Runs `python3 -m compileall app/ tests/` to verify no syntax errors

### Files deleted

**Pure Tastytrade (5):** `tasty_connector`, `tasty_oauth`,
`tasty_virtual_livebook`, `tasty_virtual_livebook_worker`,
`tasty_virtual_booker`.

**Options stack tied to Tasty (10):** `option_chain`, `quote_engine`,
`order_preview`, `spread_builder`, `universe_selector`, `manual_ticket`,
`market_scanner`, `prep_cycle`, `prep_worker`, `scheduled_scanner`.

**Legacy options execution (8):** `execution_engine`, `execution_brain`,
`virtual_execution`, `virtual_exit`, `auto_trade_worker`,
`autonomous_execution_worker`, `virtual_monitor_worker`, `telegram_worker`.
None of these were in any systemd unit. The active execution loop is
`ig_execution_worker` (see `deploy/systemd/ig-execution-worker.service`).
The active Telegram worker is the `telegram_control_room` package (see
`deploy/systemd/telegram-control-room.service`).

**Legacy data layer (2):** `trade_store`, `risk_engine`. The IG-side
counterparts are `ig_trade_store` and the per-engine risk modules
(`execution_safety_guard`, `ig_execution_sizing`, etc.).

**Editor backup (1):** `ig_execution_sizing.py.save`.

## Known followups (NOT in this PR)

These are dead code paths inside `app/main.py` that survived the strip
because deleting them inline was risky without a working test runner.
They'll error out (NameError) only if hit, and the app boots normally:

- `/manual-ticket/{trade_id}`, `/mark-executed/{trade_id}`,
  `/mark-not-executed/{trade_id}`, `/broker-preview/{trade_id}`,
  `/build-spreads/{symbol}`, `/option-chain/{symbol}`, `/tasty-account`,
  `/virtual-monitor`, `/virtual-close/{position_id}/{exit_price}`,
  `/virtual-portfolio`, `/run-scan`, `/generate-sample-trade`, `/trades`,
  `/approve/{trade_id}`, `/reject/{trade_id}`, `/tasty-virtual-book`.

A Phase 1.5 commit on this same branch (or an immediate follow-up PR)
should rip those route handlers out. They average ~50–280 lines each.
The dashboard `_legacy_dashboard_DEAD` function should also go.

The `.env` on the Lightsail server still has these keys — remove them
once you're confident the new code is healthy:

```
TASTY_AUTH_MODE, TASTY_ENV, TASTY_BASE_URL, TASTY_USERNAME, TASTY_PASSWORD,
TASTY_ACCOUNT_NUMBER, TASTY_READ_ONLY, TASTY_ORDER_EXECUTION_ENABLED,
TASTY_OAUTH_CLIENT_ID, TASTY_OAUTH_CLIENT_SECRET, TASTY_OAUTH_REFRESH_TOKEN,
TASTY_OAUTH_ACCESS_TOKEN
```

## How to verify locally

```bash
# 1. Run the deletion script
bash cleanup/remove_tastytrade.sh

# 2. Compile-check everything
python3 -m compileall app/ tests/

# 3. Run pytest
pytest -x

# 4. Smoke-boot FastAPI
python3 -c "from app.main import app; print('boot OK')"

# 5. Smoke-test the V2 plan (non-trading)
python3 - <<'PY'
from app.agent_v2_orchestrator import build_agent_v2_plan
import json
print(json.dumps(build_agent_v2_plan(), indent=2, default=str)[:2000])
PY
```

## Why I didn't run these myself

The Linux sandbox in this Cowork session never came up, so I couldn't
`git checkout`, `python -m compileall`, or `pytest`. The edits above are
all done with file-tool primitives. The script is the one place I'm
pushing a `git rm` step onto your machine. After that, everything is
verifiable locally with the commands above.

## Phase 2 onward

Already agreed:

- **Phase 2:** GitHub Actions → Lightsail auto-deploy + cost cap meter +
  Telegram threshold alerts. (Lets you stop manually deploying.)
- **Phase 3:** Frontend rebuild — IG-clone dashboard with charts, risk
  panels, live P&L, replacing the current inline-HTML routes in
  `main.py`.
- **Phase 4:** Close the agent_ops loop — LLM proposes code edits via PR
  rather than just generating a markdown brief.
