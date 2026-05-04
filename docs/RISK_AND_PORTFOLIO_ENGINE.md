# Risk and Portfolio Engine

Blocking controls:
- execution safety guard (session, liquidity reserve, stale snapshot, burst guard)
- portfolio block-new protections (existing module)
- poor regime protection (CHOP/NO_TRADE)
- stale/missing data protection

Operational behavior:
- blocked trades carry structured reasons for logs/dashboard/Telegram surfaces.
