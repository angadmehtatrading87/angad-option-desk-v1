# Autonomous Trader Architecture

Demo-only pipeline:
Market Scanner -> Market Brain -> Opportunity Scoring -> Capital Allocation -> Portfolio Risk -> Execution Safety Guard -> Two-Phase Commit -> IG Demo Execution.

Key guarantees:
- Demo/simulation mode required.
- Missing data or stale data blocks execution with explicit reasons.
- Trade thesis and capital rationale required per candidate.
- CHOP/NO_TRADE regimes suppress deployment.
