# Agent V2 Build Pack

This folder contains the next-stage intelligence modules for the FX agent.

## What V2 changes
- Multi-timeframe structure awareness
- Signal persistence gating
- Deployment doctrine based on regime
- Pair-specific edge weighting
- Opportunity ranking
- Book construction
- Friction-aware economics
- Loss-state governor
- Position lifecycle management
- Explainability logs

## Why
Your transaction review showed:
- too many small trades
- too little capital deployment
- too much churn relative to trade quality
- edge concentrated in only a few pairs

V2 is designed to trade less often, deploy more intentionally, and size by conviction.

## Suggested first build sequence
1. Add modules from this pack into your server `app/`
2. Create `build_agent_v2_plan()` orchestration layer
3. Feed V2 plan into execution engine
4. Feed pair-level realized P&L into `pair_edge_engine`
5. Replace simple exits with `position_lifecycle_engine`

## Market Brain (Shadow Mode)
See `docs/market_brain_architecture.md` for architecture, data flow, and rollout path.

Current state: Market Brain is broker/product-agnostic via adapters. The only active broker is **IG (demo account)** for FX/CFD trading. The Tastytrade options integration was removed in 2026-05; the broker layer, OAuth flow, virtual livebook, and the entire legacy options-trading stack (option_chain, quote_engine, spread_builder, order_preview, manual_ticket, market_scanner, plus the parallel `execution_engine`/`execution_brain` pipeline) have all been deleted. The live trader is `app/ig_execution_worker.py`. See `cleanup/remove_tastytrade.sh` for the deletion manifest.
