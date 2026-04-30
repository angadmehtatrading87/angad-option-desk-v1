# Angad Option Desk – Codex Agent Instructions

You are working on a production-sensitive trading engine.

Objective:
Evolve the IG trading engine from a reactive signal executor into a conviction-ranked capital allocator.

Core rules:
1. Do not touch .env, keys, credentials, data, logs, backups, or systemd files.
2. Do not run live execution commands unless Angad explicitly asks.
3. Preserve working execution plumbing unless a change is clearly justified.
4. Focus on fewer, larger, higher-conviction trades.
5. Reduce small-ticket churn.
6. Improve capital deployment logic.
7. Track friction, drawdown, win/loss quality, and capital utilization.
8. Every change must include:
   - why it is needed
   - what files changed
   - how to test
   - rollback note

Safe validation commands:
python3 -m py_compile app/*.py

python3 - <<'PY'
from app.agent_v2_orchestrator import build_agent_v2_plan
import json
print(json.dumps(build_agent_v2_plan(), indent=2, default=str)[:4000])
PY

python3 - <<'PY'
from app.ig_execution_engine import eligible_decisions
import json
print(json.dumps(eligible_decisions(), indent=2, default=str)[:4000])
PY

Do NOT run:
run_ig_demo_execution()

unless Angad explicitly approves.
