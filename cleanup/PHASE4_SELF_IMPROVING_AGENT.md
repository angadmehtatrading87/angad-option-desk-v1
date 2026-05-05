# Phase 4: Self-improving LLM agent loop

## Why this exists

The bot is now stable, IG-only, and cost-capped. Every 30 seconds it makes
decisions (mostly to *not* trade) and every IG API call is metered. We have
a daily trade log, a journalctl error stream, and a cost-cap snapshot.

That's enough state for an LLM to propose code improvements **every day**,
not after 3 months of accumulated data. We don't have to wait for "enough
trades" — even days with zero trades are informative (why did the bot pass?
were thresholds too tight? was a real setup missed?).

## Three-version rollout

We ship Phase 4 in three iterations to keep risk bounded.

### v1 — daily improvement *suggestions* via Telegram (this session)

A daily worker runs at 02:00 Dubai time:

1. Collects the last 24h of operational state (trades, errors, costs, regime stats)
2. Sends it to Claude API with a prompt: "propose ONE concrete code improvement"
3. Posts Claude's suggestion + rationale + the proposed diff to Telegram
4. **You** decide if it's worth implementing — if yes, ask in chat and I implement it

No code is auto-changed. The LLM is a daily second-pair-of-eyes.

### v2 — daily auto-PRs that you click-merge (1-2 sessions away)

Same daily worker, but instead of just Telegram-posting:

1. Apply the diff to a fresh branch
2. Run pytest
3. If green, push branch and open PR via GitHub API
4. Telegram you the PR link
5. You review on phone, click Merge if good
6. The auto-deploy workflow we built in Phase 2 ships it

If pytest fails, the proposal is discarded silently and logged.

### v3 — selective auto-merge for low-risk changes (future)

A small whitelist of file patterns (e.g. config/*.yaml, threshold tuning,
new tests) where the agent can auto-merge if all of: tests pass, change is
under N lines, file matches whitelist, no kill-switch active. Anything
outside the whitelist still needs your one-click.

This will only happen after v2 has run for 30+ days and the proposal
quality is consistently good.

## Hard safety rules (immutable across all versions)

The agent **cannot** modify:

- `.env` or any environment file
- `config/ig_config.json` (broker creds)
- `app/cost_cap_meter.py` (the limit on its own spend)
- `app/ig_adapter.py` login flow (could lock out)
- Any file under `data/` (trade history, state)
- The `cleanup/remove_tastytrade.sh` script (could resurrect dead code)
- This file (could rewrite its own constraints)

The agent **must**:

- Use only the cost-capped LLM client (`app/agent_ops/llm_client.py`)
- Operate inside the kill-switches (`is_killed("llm_calls_killed")` returns
  true → no API call that day)
- Limit itself to one proposal per day (configurable in
  `config/agent_proposer.yaml`)
- Keep diffs under 200 lines (configurable)
- Provide a written rationale alongside any diff

## Cost model

The cost-cap meter (`app/cost_cap_meter.py`) already has:

- `llm_tokens_per_day`: 200,000
- `llm_usd_per_day`: $5.00
- On breach: `kill_llm_calls` switch flips, no further LLM calls for the day

A Claude Sonnet call for a daily proposal is ~30k tokens in (state pack)
and ~3k tokens out (diff + rationale). That's roughly $0.30/day at current
Anthropic pricing — well under the $5 cap. The cap exists to catch runaway
loops (proposer in a retry storm), not to limit normal use.

## File layout

```
config/
  agent_proposer.yaml           # daily limits, prompt config, safety filters
app/
  agent_ops/
    __init__.py
    llm_client.py               # Anthropic wrapper, cost-capped
    state_collector.py          # builds the daily state pack
    proposal_prompt.py          # prompt template
    code_proposer.py            # orchestration: collect → LLM → output
    daily_worker.py             # systemd entry point (long-running, fires daily)
deploy/systemd/
  angad-code-proposer.service   # systemd unit
```

## What v1 produces — example Telegram message

```
🧠 Daily Improvement Proposal — 2026-05-12

Today the bot took 0 trades across 2,880 loops. The reason: every
candidate hit `confidence_below_threshold` because confidence scores
ranged 47-53 against a 72 floor.

Proposal:
Lower the confidence threshold from 72 → 65, but only when the regime
classifier reports quality_score ≥ 80. This lets us deploy when the
macro picture is clear even if individual setups are merely "good"
not "perfect".

Risk: more trades, but only in well-understood regimes. Adds a 1-line
guard in market_brain_execution_bridge.py.

Diff:
[unified diff, ~10 lines]

Rationale: 12 days of data shows zero trades while 4 of those days
had quality_score > 85. We're being too conservative in tradeable
regimes.

Tap "yes implement" or ignore if you disagree.
```

## v1 deployment

After this lands:

1. You add `ANTHROPIC_API_KEY` to `/etc/angad-option-desk.env` on Lightsail
2. You enable the systemd unit: `sudo systemctl enable --now angad-code-proposer.service`
3. The first proposal arrives the following 02:00 Dubai

That's it. Daily Telegram briefing of what your bot saw + what could be improved.

## Promotion to v2

When v1 has been running for 7+ days with proposals that consistently
look reasonable, the same module just adds: branch creation, pytest
gate, GitHub PR open. Same prompt, same cost cap, same human review —
just delivered as a clickable PR instead of a Telegram message.
