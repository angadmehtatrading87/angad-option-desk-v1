# Trading Engine Readiness

Readiness checks:
- Worker no longer crashes on missing snapshot/account/positions/watchlist.
- Every skipped candidate includes explicit rejection reason(s).
- Capital sizing uses equity, reserve, deployable, conviction, regime multipliers.
- Safety guard and two-phase commit remain mandatory before demo execution.

Known limitations:
- News/macro adapter currently neutral fallback if unavailable.
- Regime classification is price-action based and should be expanded with event feeds.
