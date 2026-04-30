# Agent V2 Integration Blueprint

## Objective
Evolve V1 from a short-horizon signal executor into a conviction-ranked capital allocator.

## Add these modules under `app/`
- market_regime_engine.py
- multi_timeframe_structure_engine.py
- signal_persistence_engine.py
- deployment_doctrine_engine.py
- pair_edge_engine.py
- opportunity_ranking_engine.py
- book_construction_engine.py
- friction_engine.py
- loss_state_governor.py
- position_lifecycle_engine.py
- explainability_engine.py

## Integration order

### Step 1: pre-trade orchestration layer
Create a new orchestration function, e.g. `build_agent_v2_plan()`, which:
1. fetches live IG snapshot
2. builds regime decision
3. builds structure views per pair
4. updates persistence tracker
5. reads pair-specific edge profiles
6. builds deployment doctrine
7. computes portfolio/book directive
8. ranks opportunities
9. returns only top-ranked, economically tradable candidates

### Step 2: execution engine
Wire `run_ig_demo_execution()` to consume the V2 plan instead of raw snapshot momentum.

### Step 3: position management
Replace simple open/close reactions with `position_lifecycle_engine`.

### Step 4: learning loop
Persist pair-level expectancy, churn stats, and explanation logs after every closed trade.

## Concrete policy shifts
- Fewer trades, larger notional
- Minimum deployment target by session/regime
- Minimum expected net edge in USD
- Higher evidence threshold after losses
- Pair-specific enable/disable logic
- Explainable trade logs
