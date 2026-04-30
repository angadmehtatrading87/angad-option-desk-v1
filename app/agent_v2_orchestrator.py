from __future__ import annotations

from app.ig_api_governor import get_ig_cached_snapshot
from app.market_regime_engine import classify_market_regime
from app.multi_timeframe_structure_engine import infer_structure_view
from app.deployment_doctrine_engine import build_deployment_doctrine
from app.pair_edge_engine import build_pair_edge_profile
from app.book_construction_engine import construct_book_directive
from app.opportunity_ranking_engine import rank_opportunity
from app.friction_engine import evaluate_trade_economics
from app.loss_state_governor import govern_after_losses
from app.explainability_engine import build_trade_explanation
from app.signal_persistence_engine import SignalPersistenceTracker
from app.ig_trade_store import recent_ig_trade_log


PAIR_EDGE_DEFAULTS = {
    "USDCHF": {"expectancy": 8.0, "win_rate": 48.0, "avg_hold_minutes": 90.0, "preferred_sessions": ["london", "us", "late_us"]},
    "USDCAD": {"expectancy": 18.0, "win_rate": 55.0, "avg_hold_minutes": 120.0, "preferred_sessions": ["us", "late_us"]},
    "EURUSD": {"expectancy": -3.0, "win_rate": 38.0, "avg_hold_minutes": 70.0, "preferred_sessions": ["london", "us"]},
    "GBPUSD": {"expectancy": 6.0, "win_rate": 46.0, "avg_hold_minutes": 85.0, "preferred_sessions": ["london", "us"]},
    "USDJPY": {"expectancy": 7.0, "win_rate": 47.0, "avg_hold_minutes": 95.0, "preferred_sessions": ["asia", "london", "us"]},
}

_PERSISTENCE_TRACKER = SignalPersistenceTracker(maxlen=24, min_aligned_cycles=3)


def _extract_symbol(epic: str) -> str:
    try:
        return str(epic).split(".")[2]
    except Exception:
        return str(epic)


def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def _build_simple_tf_data(body: dict) -> dict:
    snap = body.get("snapshot") or {}
    bid = _safe_float(snap.get("bid"))
    offer = _safe_float(snap.get("offer"))
    mid = (bid + offer) / 2.0 if bid > 0 and offer > 0 else max(bid, offer, 0.0)
    pct = _safe_float(snap.get("percentageChange"))
    high = _safe_float(snap.get("high"))
    low = _safe_float(snap.get("low"))

    slope_5m = pct / 3.0
    slope_15m = pct / 2.0
    slope_1h = pct
    slope_4h = pct * 1.15

    trend = 1 if pct > 0 else -1 if pct < 0 else 0
    breakout = abs(pct) > 0.20
    hhhl = pct > 0.10
    lllh = pct < -0.10

    support = low if low > 0 else None
    resistance = high if high > 0 else None

    return {
        "5m": {
            "trend": trend,
            "slope": slope_5m,
            "hhhl": hhhl,
            "lllh": lllh,
            "breakout": breakout,
            "last_price": mid,
            "support": support,
            "resistance": resistance,
        },
        "15m": {
            "trend": trend,
            "slope": slope_15m,
            "hhhl": hhhl,
            "lllh": lllh,
            "breakout": breakout,
            "last_price": mid,
            "support": support,
            "resistance": resistance,
        },
        "1h": {
            "trend": trend,
            "slope": slope_1h,
            "hhhl": hhhl,
            "lllh": lllh,
            "breakout": breakout,
            "last_price": mid,
            "support": support,
            "resistance": resistance,
        },
        "4h": {
            "trend": trend,
            "slope": slope_4h,
            "hhhl": hhhl,
            "lllh": lllh,
            "breakout": breakout,
            "last_price": mid,
            "support": support,
            "resistance": resistance,
        },
    }


def _estimate_persistence_score(watchlist: list[dict]) -> float:
    vals = []
    for m in watchlist:
        body = ((m.get("snapshot") or {}).get("body") or {})
        pct = abs(_safe_float(((body.get("snapshot") or {}).get("percentageChange"))))
        vals.append(min(100.0, pct * 250.0))
    if not vals:
        return 25.0
    return round(sum(vals) / len(vals), 2)


def _estimate_realized_vol(watchlist: list[dict]) -> float:
    vals = []
    for m in watchlist:
        body = ((m.get("snapshot") or {}).get("body") or {})
        snap = body.get("snapshot") or {}
        pct = abs(_safe_float(snap.get("percentageChange")))
        vals.append(pct)
    if not vals:
        return 0.1
    return round(sum(vals) / len(vals), 4)


def _estimate_range_expansion(watchlist: list[dict]) -> float:
    vals = []
    for m in watchlist:
        body = ((m.get("snapshot") or {}).get("body") or {})
        snap = body.get("snapshot") or {}
        high = _safe_float(snap.get("high"))
        low = _safe_float(snap.get("low"))
        bid = _safe_float(snap.get("bid"))
        offer = _safe_float(snap.get("offer"))
        mid = (bid + offer) / 2.0 if bid > 0 and offer > 0 else max(bid, offer, 0.0)
        if high > 0 and low > 0 and mid > 0:
            vals.append((high - low) / mid)
    if not vals:
        return 0.1
    return round(sum(vals) / len(vals), 4)


def _estimate_current_deployment_pct(account: dict) -> float:
    equity = _safe_float(account.get("equity"))
    available = _safe_float(account.get("available"))
    if equity <= 0:
        return 0.0
    used = max(equity - available, 0.0)
    return round((used / equity) * 100.0, 2)


def _estimate_recent_drawdown_pct(account: dict) -> float:
    equity = _safe_float(account.get("equity"))
    open_pnl = _safe_float(account.get("open_pnl"))
    if equity <= 0:
        return 0.0
    return round((open_pnl / equity) * 100.0, 4)


def _estimate_recent_realized_pnl(account: dict) -> float:
    return _safe_float(account.get("open_pnl"))


def _estimate_losing_streak(account: dict) -> int:
    open_pnl = _safe_float(account.get("open_pnl"))
    return 1 if open_pnl < 0 else 0


def _portfolio_fit_score(symbol: str, positions: list[dict]) -> float:
    same_symbol = 0
    usd_exposure = 0
    for p in positions:
        psym = _extract_symbol(p.get("epic", ""))
        if psym == symbol:
            same_symbol += 1
        if "USD" in psym:
            usd_exposure += 1

    fit = 85.0
    fit -= same_symbol * 18.0
    if usd_exposure >= 4:
        fit -= 12.0
    return max(20.0, min(100.0, fit))


def _trade_log_edge_memory(limit: int = 300) -> dict[str, dict]:
    memory: dict[str, dict] = {}
    try:
        rows = recent_ig_trade_log(limit=limit) or []
    except Exception:
        return memory

    for row in rows:
        epic = str(row.get("epic") or "")
        symbol = _extract_symbol(epic)
        if not symbol:
            continue
        bucket = memory.setdefault(symbol, {"n": 0, "wins": 0, "conf_sum": 0.0, "notes": []})
        bucket["n"] += 1
        conf = _safe_float(row.get("confidence"), 0.0)
        bucket["conf_sum"] += conf
        status = str(row.get("status") or "").upper()
        if status in ("CONFIRMED_IN_BOOK", "ACCEPTED_NOT_VISIBLE_IN_BOOK"):
            bucket["wins"] += 1

    for symbol, bucket in memory.items():
        n = max(int(bucket.get("n", 0)), 1)
        wins = int(bucket.get("wins", 0))
        win_rate = (wins / n) * 100.0
        avg_conf = _safe_float(bucket.get("conf_sum")) / n
        expectancy_adj = ((win_rate - 50.0) * 0.35) + ((avg_conf - 65.0) * 0.15)
        size_weight = max(0.5, min(1.6, 1.0 + (expectancy_adj / 100.0)))
        bucket["win_rate"] = round(win_rate, 2)
        bucket["avg_confidence"] = round(avg_conf, 2)
        bucket["expectancy_adj"] = round(expectancy_adj, 2)
        bucket["size_weight"] = round(size_weight, 2)
        bucket["sample_size"] = n

    return memory


def build_agent_v2_plan():
    snap = get_ig_cached_snapshot(force_refresh=False) or {}
    account = snap.get("account") or {}
    watchlist = ((snap.get("watchlist") or {}).get("markets") or [])
    positions = ((snap.get("positions") or {}).get("positions") or [])
    session_state = snap.get("session_state") or {}
    session_name = (session_state.get("session") or "").lower()

    persistence_score = _estimate_persistence_score(watchlist)
    realized_vol = _estimate_realized_vol(watchlist)
    range_expansion = _estimate_range_expansion(watchlist)

    mtf_slopes = {}
    structures = {}
    for m in watchlist:
        epic = m.get("epic")
        body = ((m.get("snapshot") or {}).get("body") or {})
        tf_data = _build_simple_tf_data(body)
        sv = infer_structure_view(tf_data)
        structures[epic] = sv.to_dict()
        mtf_slopes[epic] = _safe_float(tf_data.get("1h", {}).get("slope"))

    regime = classify_market_regime(
        mtf_slopes=mtf_slopes,
        realized_vol=realized_vol,
        range_expansion=range_expansion,
        session=session_name,
        persistence_score=persistence_score,
    ).to_dict()

    current_deployment_pct = _estimate_current_deployment_pct(account)
    recent_drawdown_pct = _estimate_recent_drawdown_pct(account)

    deployment = build_deployment_doctrine(
        regime=regime.get("regime", "MIXED"),
        quality_score=_safe_float(regime.get("quality_score")),
        current_deployment_pct=current_deployment_pct,
        recent_drawdown_pct=recent_drawdown_pct,
    ).to_dict()

    book_directive = construct_book_directive(
        target_deployment_pct=_safe_float(deployment.get("target_pct")),
        quality_score=_safe_float(regime.get("quality_score")),
    ).to_dict()

    loss_governor = govern_after_losses(
        recent_realized_pnl=_estimate_recent_realized_pnl(account),
        losing_streak=_estimate_losing_streak(account),
    ).to_dict()

    pair_edges = {}
    edge_memory = _trade_log_edge_memory(limit=300)
    ranked = []
    explanations = {}
    economic_candidates = []

    for m in watchlist:
        epic = m.get("epic")
        symbol = _extract_symbol(epic)
        body = ((m.get("snapshot") or {}).get("body") or {})
        snap_row = body.get("snapshot") or {}

        structure = structures.get(epic, {})
        bias = structure.get("bias", "NEUTRAL")
        if bias == "NEUTRAL":
            continue

        direction = "BUY" if bias == "LONG" else "SELL"
        persistence_state = _PERSISTENCE_TRACKER.update(symbol=symbol, direction=direction, aligned=True).to_dict()
        if not persistence_state.get("tradable"):
            continue

        defaults = PAIR_EDGE_DEFAULTS.get(symbol, {
            "expectancy": 5.0,
            "win_rate": 45.0,
            "avg_hold_minutes": 90.0,
            "preferred_sessions": ["london", "us", "late_us"],
        })

        pep = build_pair_edge_profile(
            symbol=symbol,
            expectancy=defaults["expectancy"],
            win_rate=defaults["win_rate"],
            avg_hold_minutes=defaults["avg_hold_minutes"],
            preferred_sessions=defaults["preferred_sessions"],
        ).to_dict()
        mem = edge_memory.get(symbol) or {}
        mem_size_weight = _safe_float(mem.get("size_weight"), 1.0)
        pep["size_weight"] = round(_safe_float(pep.get("size_weight"), 1.0) * mem_size_weight, 2)
        if mem:
            pep.setdefault("notes", []).append(
                f"edge_memory sample={int(mem.get('sample_size', 0))} win_rate={_safe_float(mem.get('win_rate')):.1f}%"
            )
        pair_edges[symbol] = pep

        if not pep.get("enabled", True):
            continue

        structure_strength = _safe_float(structure.get("strength"))
        pair_weight = _safe_float(pep.get("size_weight"), 1.0)
        portfolio_fit = _portfolio_fit_score(symbol, positions)

        bid = _safe_float(snap_row.get("bid"))
        offer = _safe_float(snap_row.get("offer"))
        spread_bps = 0.0
        if bid > 0 and offer > 0:
            mid = (bid + offer) / 2.0
            spread_bps = ((offer - bid) / mid) * 10000.0 if mid > 0 else 0.0

        score_obj = rank_opportunity(
            symbol=symbol,
            direction=direction,
            structure_strength=structure_strength,
            persistence_score=min(
                100.0,
                _safe_float(persistence_state.get("persistence_score")) / _safe_float(loss_governor.get("evidence_multiplier", 1.0), 1.0),
            ),
            regime_quality=_safe_float(regime.get("quality_score")),
            friction_penalty=spread_bps,
            pair_size_weight=pair_weight,
            portfolio_fit=portfolio_fit,
        ).to_dict()

        ranked.append(score_obj)

        if current_deployment_pct < _safe_float(deployment.get("floor_pct")):
            target_notional = _safe_float(account.get("equity")) * 0.10
        else:
            target_notional = _safe_float(account.get("equity")) * 0.05

        econ = evaluate_trade_economics(
            notional_usd=target_notional,
            expected_move_bps=max(14.0, structure_strength / 3.5),
            spread_bps=max(spread_bps, 1.0),
            admin_fee_usd=0.0,
            financing_usd=max(2.0, target_notional * 0.00003),
            min_net_edge_usd=max(90.0, target_notional * 0.0012),
        ).to_dict()

        if not econ.get("tradable", False):
            continue

        candidate = {
            "epic": epic,
            "symbol": symbol,
            "name": (body.get("instrument") or {}).get("name"),
            "action": "WATCH_LONG" if direction == "BUY" else "WATCH_SHORT",
            "direction": direction,
            "confidence": min(95.0, max(55.0, _safe_float(score_obj.get("total_score")))),
            "reason": "; ".join(score_obj.get("reasons", [])),
            "score": _safe_float(score_obj.get("total_score")),
            "structure": structure,
            "pair_edge": pep,
            "persistence": persistence_state,
            "economics": econ,
        }

        explanation = build_trade_explanation(
            symbol=symbol,
            direction=direction,
            regime=regime.get("regime", "MIXED"),
            deployment_mode=deployment.get("mode", "MAINTAIN"),
            score=_safe_float(score_obj.get("total_score")),
            reasons=score_obj.get("reasons", []),
            size=1.0,
        )
        explanations[epic] = explanation
        candidate["explanation"] = explanation
        economic_candidates.append(candidate)

    economic_candidates = sorted(economic_candidates, key=lambda x: x.get("score", 0), reverse=True)

    target_count = int(book_directive.get("target_position_count", 3) or 3)
    final_candidates = economic_candidates[:target_count]

    return {
        "ok": True,
        "session_state": session_state,
        "account": account,
        "regime": regime,
        "deployment": deployment,
        "loss_governor": loss_governor,
        "book_directive": book_directive,
        "structures": structures,
        "pair_edges": pair_edges,
        "edge_memory": edge_memory,
        "ranked": ranked,
        "candidates": final_candidates,
    }
