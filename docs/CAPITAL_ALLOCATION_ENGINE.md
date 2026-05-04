# Capital Allocation Engine

Inputs:
- total equity
- used capital
- score-derived conviction
- regime multiplier
- drawdown multiplier

Constraints:
- 30% liquidity reserve always retained.
- Minimum useful trade size enforced.
- Under-utilization flag raised when deployable capital is high but recommendation stays too small.

Output:
- recommended_notional + full allocation reason string.
