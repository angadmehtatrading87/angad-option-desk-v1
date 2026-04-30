from app.ig_trade_scorecard import all_scorecards

def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

def build_context_performance():
    items = all_scorecards()
    complete = [x for x in items if x.get("outcome_state") in ("WIN", "LOSS", "SCRATCH")]

    by_symbol = {}
    by_session = {}
    by_regime = {}
    by_entry_style = {}

    def bump(bucket, key, pnl, win):
        if key not in bucket:
            bucket[key] = {"count": 0, "wins": 0, "pnl": 0.0}
        bucket[key]["count"] += 1
        bucket[key]["wins"] += win
        bucket[key]["pnl"] += pnl

    for x in complete:
        pnl = _safe_float(x.get("realized_pnl_points", 0.0))
        win = 1 if pnl > 0 else 0

        bump(by_symbol, x.get("epic", "UNKNOWN"), pnl, win)
        bump(by_session, x.get("entry_session", "unknown"), pnl, win)
        bump(by_regime, x.get("entry_regime", "unknown"), pnl, win)
        bump(by_entry_style, x.get("entry_style", "unknown"), pnl, win)

    return {
        "by_symbol": by_symbol,
        "by_session": by_session,
        "by_regime": by_regime,
        "by_entry_style": by_entry_style,
        "completed_count": len(complete)
    }

def rank_context_bucket(bucket, key_name):
    rows = [{"name": k, **v} for k, v in bucket.items()]
    rows.sort(key=lambda x: x.get("pnl", 0.0), reverse=True)
    best = rows[:5]
    worst = sorted(rows, key=lambda x: x.get("pnl", 0.0))[:5]
    return {"key_name": key_name, "best": best, "worst": worst}
