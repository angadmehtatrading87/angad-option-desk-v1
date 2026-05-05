# Phase 2: real multi-timeframe intelligence + auto-deploy + cost cap

Date: 2026-05-04. Branch: `remove-tastytrade` (or whatever the next one is).

This builds on Phase 1 (Tastytrade strip) and lands three things:

1. **Real multi-timeframe candle pipeline** — replaces the old fake
   `_build_simple_tf_data` in the V2 orchestrator with actual IG candles.
2. **Auto-deploy via GitHub Actions** — every merge to `main` now updates
   Lightsail automatically; you never SSH into the box to deploy.
3. **Daily cost-cap meter** — IG API + LLM spend ceilings, Telegram alerts,
   automatic kill-switches.

---

## 1. Real multi-timeframe candles

### Before
`agent_v2_orchestrator._build_simple_tf_data` faked the 5m/15m/1h/4h MTF
view by multiplying a single `percentageChange` field by hand-tuned
constants:

```python
slope_5m  = pct / 3.0
slope_15m = pct / 2.0
slope_1h  = pct
slope_4h  = pct * 1.15
```

Every downstream engine (regime classifier, structure inference, signal
persistence) was reading variations of the same number — so MTF "agreement"
was always trivially true.

### After
- New `IGAdapter.prices(epic, resolution, max_points)` calls IG's
  `/prices/{epic}` endpoint.
- New `app/ig_candle_engine.py`:
  - TTL cache keyed by `(epic, resolution)`. TTLs are sized to each
    candle's natural lifetime (5m → 6 min, 4h → ~5 h), so we refresh at
    most once per bar close.
  - With 5 epics × 4 resolutions, steady-state load is ~12 IG calls/hour.
    Well under IG's per-key budget (10k historical-price points/week).
  - Graceful degradation: if a fetch fails or has no cache, the orchestrator
    falls back to the old "single-percentageChange" reader **but stamps the
    candidate as degraded and halves its conviction** so the bot doesn't
    size up on a signal it can't actually verify.
- New `candle_features(candles)` derives:
  - `trend` from EMA-9 vs EMA-21 (not a 1-bar slope)
  - `slope` in basis points over a 10-bar lookback
  - `hhhl` / `lllh` from real swing structure across the prior window
  - `breakout` from current close vs prior swing extremes
  - `support`, `resistance`, `atr`
- The orchestrator now also returns `mtf_diagnostics` per epic so you can
  see in any dashboard whether the data was real, cached, or degraded.

### Net effect
Every conviction-ranking, regime, structure, and persistence decision the
V2 orchestrator makes is now grounded in actual MTF data. The 5m read no
longer agrees with the 4h read by definition — they can disagree, and
disagreement is information.

---

## 2. GitHub Actions auto-deploy to Lightsail

### Files
- `.github/workflows/ci.yml` — runs on every PR + push to `main`. Compiles
  app/ + tests/, runs pytest. If red, the deploy below won't run.
- `.github/workflows/deploy-lightsail.yml` — runs on push to `main`. SSHes
  into Lightsail, pulls main, optionally pip-installs requirements, runs
  py_compile, restarts `ig-execution-worker` and `telegram-control-room`
  via systemd. On failure, posts a Telegram alert.

### What you need to do once
1. Generate an SSH keypair (use a fresh one for this — don't reuse your
   personal key):
   ```bash
   ssh-keygen -t ed25519 -f ~/Desktop/lightsail_deploy -N "" -C "github-actions-deploy"
   ```
2. Add the **public** key to Lightsail:
   ```bash
   ssh ubuntu@YOUR_LIGHTSAIL_IP "cat >> ~/.ssh/authorized_keys" < ~/Desktop/lightsail_deploy.pub
   ```
3. Add the **private** key contents and a few details as GitHub Secrets at
   `Settings → Secrets and variables → Actions`:
   - `LIGHTSAIL_HOST` — e.g. `13.234.x.x`
   - `LIGHTSAIL_USER` — `ubuntu`
   - `LIGHTSAIL_SSH_KEY` — paste the entire contents of
     `~/Desktop/lightsail_deploy` (including the BEGIN/END lines)
   - `LIGHTSAIL_DEPLOY_PATH` — `/home/ubuntu/angad-option-desk-v1`
   - (optional) `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` for failure alerts
4. Allow your user to restart systemd units without a password. On the
   Lightsail box:
   ```bash
   sudo visudo
   ```
   Add at the bottom:
   ```
   ubuntu ALL=NOPASSWD: /bin/systemctl restart ig-execution-worker, /bin/systemctl restart telegram-control-room, /bin/systemctl daemon-reload
   ```
5. Once your private key is in the GitHub Secret, **delete it from your
   laptop**:
   ```bash
   shred -u ~/Desktop/lightsail_deploy ~/Desktop/lightsail_deploy.pub
   ```

After step 5, every PR you merge to `main` will auto-deploy. The whole
"Phase 1 → push → I have to SSH in and `git pull`" dance goes away.

### Why I can't do steps 1-5 for you
Generating SSH keys, putting private keys into a credentials store on your
behalf, and running `sudo visudo` are all things my safety rules forbid.
This is the part where you spend 5 minutes once and never have to deploy
manually again.

---

## 3. Cost cap meter

### Files
- `app/cost_cap_meter.py` — daily counters, alert dispatch, kill-switches.
- `config/cost_cap.yaml` — caps and breach actions.

### Tracked categories
| Category | Default cap | On breach |
|---|---|---|
| `ig_api_calls` | 5000/day | alert only |
| `ig_orders_submitted` | 80/day | flip `trading_killed` |
| `ig_position_opens` | 40/day | flip `trading_killed` |
| `llm_tokens` | 200k/day | flip `llm_calls_killed` |
| `llm_usd` | $5.00/day | flip `llm_calls_killed` |

Telegram alerts fire at 80% of cap (warn), 95% (warn again), and 100%
(kill — alongside the kill-switch flip).

### Wired in
- `IGAdapter.market`, `positions`, `prices`, `open_position` increment
  the matching counter on every call.
- `IGAdapter.open_position` checks `is_killed("trading_killed")` before
  submitting and refuses cleanly with a `blocked_by_cost_cap` error.
- LLM spend hooks aren't wired yet — that lives next to whatever
  Anthropic/OpenAI client you add to agent_ops in Phase 4. Code is ready
  for it.

### Tune the caps
Edit `config/cost_cap.yaml`. Numbers reload on the next `record()` call;
no restart needed.

---

## How to verify

```bash
# 1. Compile
python3 -m compileall -q app/ tests/

# 2. Smoke test the new candle features (no network needed)
python3 - <<'PY'
from app.ig_candle_engine import candle_features
out = candle_features([
    {"open":1.0,"high":1.01,"low":0.99,"close":1.005},
    {"open":1.005,"high":1.015,"low":0.995,"close":1.012},
    {"open":1.012,"high":1.02,"low":1.005,"close":1.018},
    {"open":1.018,"high":1.025,"low":1.01,"close":1.022},
    {"open":1.022,"high":1.028,"low":1.015,"close":1.025},
    {"open":1.025,"high":1.03,"low":1.02,"close":1.028},
    {"open":1.028,"high":1.033,"low":1.022,"close":1.031},
    {"open":1.031,"high":1.04,"low":1.028,"close":1.038},
])
print("trend:", out["trend"], "  slope_bps:", out["slope"], "  breakout:", out["breakout"])
PY

# 3. Smoke test the cost cap meter
python3 - <<'PY'
from app.cost_cap_meter import record, snapshot, is_killed, reset_today
reset_today()
for _ in range(100):
    record("ig_orders_submitted", 1)   # cap is 80/day
print("trading_killed:", is_killed("trading_killed"))
print(snapshot())
PY

# 4. Pull live MTF candles (requires .env / live IG creds; safe — read-only)
python3 - <<'PY'
from app.ig_candle_engine import build_mtf_features
result = build_mtf_features("CS.D.EURUSD.DBM.IP")
import json; print(json.dumps(result, indent=2, default=str)[:2000])
PY

# 5. End-to-end V2 plan with real candles
python3 - <<'PY'
from app.agent_v2_orchestrator import build_agent_v2_plan
import json
plan = build_agent_v2_plan()
print("regime:", plan["regime"]["regime"], "  candidates:", len(plan["candidates"]))
print("MTF diagnostics:")
print(json.dumps(plan.get("mtf_diagnostics", {}), indent=2)[:1500])
PY
```

---

## What's NOT in Phase 2 (deliberate)

- **Daily learning loop**: the `ig_outcome_learning_engine.py` already
  exists and the V2 orchestrator already pulls per-pair edge memory from
  `recent_ig_trade_log()`. Closing the loop end-to-end (running a
  scheduled worker that re-trains pair weights overnight) is a clean
  half-day's work in Phase 3.
- **Frontend rebuild**: still queued — needs a clean base, doing it before
  Phase 1.5 (dead-route cleanup in main.py) lands is wasted work.
- **LLM-driven decision layer**: the LLM-cost cap is wired and waiting.
  The actual call-site (where Claude/GPT analyzes news + chart context
  and outputs a confidence override) is Phase 4 / agent_ops self-improvement.

---

## Commit message when you're ready

```
Phase 2: real MTF candles + GitHub Actions deploy + cost cap meter

- ig_adapter.prices() pulls /prices/{epic} per resolution
- ig_candle_engine.py: TTL-cached MTF feature extraction (EMA, swing
  structure, breakout, ATR) with graceful degraded-mode fallback
- agent_v2_orchestrator: real candles per epic, conviction halved when
  degraded, mtf_diagnostics returned for dashboard visibility
- .github/workflows/ci.yml + deploy-lightsail.yml: auto-deploy on merge
  to main with compile-check + systemd restart and Telegram failure alert
- cost_cap_meter.py + config/cost_cap.yaml: daily IG API / LLM spend
  ceilings, automatic kill-switches, Telegram threshold alerts
- IGAdapter wired to record every call and refuse open_position when
  trading_killed is on
```
