# Market Brain (Shadow Mode)

## Why needed
Current execution flow is reactive and can under-deploy capital. Market Brain adds a conviction-ranked allocator that scans, scores, ranks, and explains opportunities before any execution path.

## What changed
- Added `app/market_brain/` package with typed models and orchestration.
- Added scanner, candle features, regime classifier, scoring, capital allocation, monthly objective tracker, thesis generator, and learning record model scaffolding.
- Integrated Market Brain output into dashboard state as `market_brain` in shadow recommendation mode.
- Added tests in `tests/test_market_brain.py`.

## Shadow mode behavior
- Produces recommendations only.
- Does not submit orders.
- Does not bypass safety gate or two-phase commit.

## Promotion path to execution (later)
1. Keep safety guard and two-phase commit mandatory.
2. Gate by feature flag.
3. Start with top-1 recommendation with strict friction and liquidity thresholds.

## Rollback
- Revert commit containing `app/market_brain/*`, dashboard wiring, and tests.
- Existing execution engine remains unchanged.
