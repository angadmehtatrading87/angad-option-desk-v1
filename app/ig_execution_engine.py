from app.agent_v2_orchestrator import build_agent_v2_plan
import json
import os
import time

from app.ig_adapter import IGAdapter
from app.ig_api_governor import get_ig_cached_snapshot
from app.ig_decision_engine import infer_ig_signal
from app.ig_execution_sizing import get_execution_sizing_plan, scale_order_size
from app.ig_trade_store import (
    ensure_ig_tables,
    log_ig_decision,
    mark_ig_log,
    recent_ig_trade_log,
)
from app.telegram_alerts import send_ig_trade_alert
from app.ig_smart_trade_brain import evaluate_live_positions, mark_exit_for_reentry, reentry_allowed, size_multiplier
from app.daily_objective_controller import combined_entry_allowed
from app.lane_capital_controller import lane_entry_allowed, ig_lane_snapshot

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POLICY_PATH = os.path.join(BASE_DIR, "config", "ig_risk_policy.json")

def load_ig_policy():
    with open(POLICY_PATH, "r") as f:
        return json.load(f)


def _fx_price_from_level(epic, level):
    try:
        lvl = float(level or 0.0)
    except Exception:
        return 0.0
    if lvl <= 0:
        return 0.0
    if "JPY" in str(epic):
        return lvl / 100.0 if lvl > 500 else lvl
    return lvl / 10000.0 if lvl > 500 else lvl

def _estimate_position_notional_usd(pos):
    epic = str(pos.get("epic") or "")
    symbol = ""
    try:
        symbol = epic.split(".")[2]
    except Exception:
        symbol = epic

    size = float(pos.get("size") or 0.0)
    level = float(pos.get("level") or 0.0)
    px = _fx_price_from_level(epic, level)
    contract_size = 10000.0

    if size <= 0:
        return 0.0

    # For USDXXX pairs, USD notional is simply size * contract size
    if symbol.startswith("USD"):
        return round(size * contract_size, 2)

    # For XXXUSD pairs, convert base notional into USD using price
    if symbol.endswith("USD"):
        return round(size * contract_size * max(px, 0.0), 2)

    # Fallback
    return round(size * contract_size * max(px, 1.0), 2)

def _capital_scaled_controls(policy):
    snap = {}
    try:
        snap = get_ig_cached_snapshot(force_refresh=False) or {}
    except Exception:
        snap = {}

    account = (snap.get("account") or {})
    session_state = (snap.get("session_state") or {})
    positions_block = (snap.get("positions") or {})
    positions = positions_block.get("positions") or []

    balance = float(account.get("balance") or 0.0)
    equity = float(account.get("equity") or balance or 0.0)
    available = float(account.get("available") or 0.0)
    open_pnl = float(account.get("open_pnl") or 0.0)

    capital_base = max(equity, balance, 1.0)

    deployed_notional = round(sum(_estimate_position_notional_usd(p) for p in positions), 2)
    deployment_pct = round((deployed_notional / capital_base) * 100.0, 2) if capital_base > 0 else 0.0

    session_name = (session_state.get("session") or "").lower()
    if session_name in ("asia", "sunday_reopen_probe", "asia_friday"):
        target_deployment_pct = float(policy.get("target_deployment_pct_asia", 20.0))
    elif session_name in ("london",):
        target_deployment_pct = float(policy.get("target_deployment_pct_london", 35.0))
    elif session_name in ("us",):
        target_deployment_pct = float(policy.get("target_deployment_pct_us", 45.0))
    elif session_name in ("late_us",):
        target_deployment_pct = float(policy.get("target_deployment_pct_late_us", 30.0))
    else:
        target_deployment_pct = float(policy.get("target_deployment_pct_default", 25.0))

    deployment_gap_pct = max(target_deployment_pct - deployment_pct, 0.0)

    base_capital = float(policy.get("capital_scaling_base", 1000000.0) or 1000000.0)
    ratio = max(capital_base / base_capital, 0.25)

    # Bigger capital should scale size, but underdeployment should force much stronger expression.
    capital_component = min(max(ratio ** 0.65, 1.0), 3.0)
    deployment_component = min(max(target_deployment_pct / max(deployment_pct, 5.0), 1.0), float(policy.get("deployment_component_cap", 4.5) or 4.5))

    size_factor = min(
        capital_component * deployment_component,
        float(policy.get("capital_scaling_size_cap", 8.0) or 8.0)
    )

    open_factor = min(
        max(ratio * deployment_component, 1.0),
        float(policy.get("capital_scaling_open_cap", 12.0) or 12.0)
    )

    base_max_open = int(policy.get("max_concurrent_positions", 12) or 12)
    base_max_per_epic = int(policy.get("max_positions_per_epic", 3) or 3)

    scaled_max_open = max(1, int(round(base_max_open * open_factor)))
    scaled_max_per_epic = max(
        1,
        min(
            int(round(base_max_per_epic * max(1.0, ratio * 1.75))),
            int(policy.get("capital_scaling_per_epic_cap", 15) or 15),
        ),
    )

    return {
        "capital_source": "ig_live_account",
        "balance": round(balance, 2),
        "equity": round(equity, 2),
        "available": round(available, 2),
        "open_pnl": round(open_pnl, 2),
        "lane_equity": round(capital_base, 2),
        "deployed_notional": round(deployed_notional, 2),
        "deployment_pct": round(deployment_pct, 2),
        "target_deployment_pct": round(target_deployment_pct, 2),
        "deployment_gap_pct": round(deployment_gap_pct, 2),
        "ratio": round(ratio, 4),
        "size_factor": round(size_factor, 4),
        "max_open": scaled_max_open,
        "max_positions_per_epic": scaled_max_per_epic,
        "session": session_name,
    }

def _confidence_size_boost(confidence):
    c = float(confidence or 0.0)
    if c >= 90:
        return 1.9
    if c >= 85:
        return 1.65
    if c >= 80:
        return 1.4
    if c >= 75:
        return 1.2
    if c >= 70:
        return 1.1
    return 1.0

def action_to_direction(action):
    if action == "WATCH_LONG":
        return "BUY"
    if action == "WATCH_SHORT":
        return "SELL"
    return None

def _round_size_for_ig(size, step=0.1, min_size=0.1):
    try:
        size = float(size or 0.0)
    except Exception:
        size = 0.0

    try:
        step = float(step or 0.1)
    except Exception:
        step = 0.1

    try:
        min_size = float(min_size or step or 0.1)
    except Exception:
        min_size = step

    if size <= 0:
        return 0.0

    rounded = round(round(size / step) * step, 4)

    if rounded < min_size:
        rounded = min_size

    return round(rounded, 4)

def opposite_direction(direction):
    return "SELL" if str(direction).upper() == "BUY" else "BUY"

def build_order_params(epic):
    policy = load_ig_policy()
    controls = _capital_scaled_controls(policy)
    base_size = float(policy.get("fixed_size_by_epic", {}).get(epic, 1.0))
    mult = float(size_multiplier())
    capital_factor = float(controls.get("size_factor", 1.0) or 1.0)
    size = round(base_size * mult * capital_factor, 4)
    size = _round_size_for_ig(size, step=0.1, min_size=0.1)    
    stop_distance = float(policy.get("default_stop_distance_points", {}).get(epic, 20))
    limit_distance = float(policy.get("default_limit_distance_points", {}).get(epic, 30))
    return size, stop_distance, limit_distance

def _instrument_currency_code(ig, epic):
    market = ig.market(epic)
    if not market.get("ok"):
        return "USD"
    body = market.get("body") if isinstance(market.get("body"), dict) else {}
    inst = body.get("instrument", {}) or {}
    currencies = inst.get("currencies", []) or []

    for c in currencies:
        if c.get("isDefault"):
            return c.get("code") or "USD"

    if currencies:
        return currencies[0].get("code") or "USD"

    return "USD"

def _positions_list(ig):
    pos = ig.positions()
    if not pos.get("ok"):
        return []
    body = pos.get("body") if isinstance(pos.get("body"), dict) else {}
    return body.get("positions", []) if isinstance(body, dict) else []

def _normalize_positions(rows):
    out = []
    for row in rows:
        market = row.get("market", {}) or {}
        position = row.get("position", {}) or {}
        out.append({
            "epic": market.get("epic"),
            "name": market.get("instrumentName"),
            "deal_id": position.get("dealId"),
            "deal_reference": position.get("dealReference"),
            "direction": str(position.get("direction") or "").upper(),
            "size": float(position.get("size") or 0),
            "level": position.get("level"),
            "entry_level": position.get("level"),
            "stop_level": position.get("stopLevel"),
            "limit_level": position.get("limitLevel"),
            "bid": market.get("bid"),
            "offer": market.get("offer"),
        })
    return out

def _match_position(positions, epic, direction, size, deal_id=None):
    direction = str(direction or "").upper()
    for row in positions:
        market = row.get("market", {}) or {}
        position = row.get("position", {}) or {}
        pos_epic = market.get("epic")
        pos_direction = str(position.get("direction") or "").upper()
        pos_size = position.get("size")
        pos_deal_id = position.get("dealId")

        if deal_id and pos_deal_id == deal_id:
            return row
        if pos_epic == epic and pos_direction == direction:
            try:
                if float(pos_size) == float(size):
                    return row
            except Exception:
                return row
    return None

def _confirm_in_book(ig, epic, direction, size, deal_reference=None):
    confirm_result = None
    confirm_body = {}
    deal_id = None
    deal_status = ""
    reason_text = ""

    if deal_reference:
        for _ in range(4):
            time.sleep(1.5)
            confirm_result = ig.confirm(deal_reference)
            if confirm_result.get("ok"):
                confirm_body = confirm_result.get("body") if isinstance(confirm_result.get("body"), dict) else {}
                deal_status = str(confirm_body.get("dealStatus") or "").upper()
                reason_text = str(confirm_body.get("reason") or "")
                deal_id = confirm_body.get("dealId")
                if deal_status:
                    break

    matched_position = None
    book_positions = []
    for _ in range(5):
        time.sleep(1.5)
        book_positions = _positions_list(ig)
        matched_position = _match_position(book_positions, epic, direction, size, deal_id=deal_id)
        if matched_position:
            break

    return {
        "confirm_result": confirm_result,
        "confirm_body": confirm_body,
        "deal_id": deal_id,
        "deal_status": deal_status,
        "reason_text": reason_text,
        "matched_position": matched_position,
        "book_positions": book_positions,
    }

def _ensure_account(ig, login):
    configured_account = ig.account_id
    current_account = ((login.get("body") or {}).get("currentAccountId"))
    if configured_account and current_account != configured_account:
        sw = ig.switch_account(configured_account)
        if not sw.get("ok"):
            return {"ok": False, "reason": "ig_account_switch_failed", "switch": sw}
        sess = ig.session()
        sess_body = sess.get("body") if isinstance(sess.get("body"), dict) else {}
        if sess_body.get("accountId") != configured_account and sess_body.get("currentAccountId") != configured_account:
            return {"ok": False, "reason": "ig_account_switch_not_confirmed", "session": sess}
    return {"ok": True}

def _same_side_positions(live_positions, epic, direction):
    direction = str(direction or "").upper()
    return [p for p in live_positions if p.get("epic") == epic and str(p.get("direction") or "").upper() == direction]

def _pyramiding_allowed(policy, same_side_positions, signal_confidence):
    if not policy.get("allow_pyramiding", False):
        return False
    if not same_side_positions:
        return False
    if float(signal_confidence or 0) < float(policy.get("pyramid_min_signal_confidence", 68)):
        return False
    if policy.get("pyramid_only_if_profitable", True):
        profitable = False
        for p in same_side_positions:
            entry = float(p.get("level") or p.get("entry_level") or 0)
            bid = float(p.get("bid") or p.get("mark_level") or 0)
            offer = float(p.get("offer") or p.get("mark_level") or 0)
            direction = str(p.get("direction") or "").upper()
            pnl_pts = (bid - entry) if direction == "BUY" else (entry - offer)
            if pnl_pts > 0:
                profitable = True
                break
        return profitable
    return True

def _live_position_summary(ig):
    live_positions = _normalize_positions(_positions_list(ig))
    same_side_keys = {(p["epic"], p["direction"]) for p in live_positions}
    epic_counts = {}
    for p in live_positions:
        epic_counts[p["epic"]] = epic_counts.get(p["epic"], 0) + 1
    return {
        "positions": live_positions,
        "same_side_keys": same_side_keys,
        "epic_counts": epic_counts,
        "count": len(live_positions),
    }


def _build_v2_decisions():
    try:
        plan = build_agent_v2_plan()
    except Exception as e:
        return {
            "ok": False,
            "reason": ["v2_plan_failed", str(e)],
            "decisions": [],
            "skips": [],
            "plan": {},
        }

    candidates = plan.get("candidates", []) or []
    decisions = []
    skips = []

    for c in candidates:
        action = c.get("action")
        epic = c.get("epic")
        if action not in ("WATCH_LONG", "WATCH_SHORT"):
            skips.append({"epic": epic, "reason": "v2_non_actionable"})
            continue

        decisions.append({
            "epic": epic,
            "name": c.get("name") or c.get("symbol"),
            "action": action,
            "reason": c.get("reason", ""),
            "confidence": float(c.get("confidence", 0) or 0),
            "v2_score": c.get("score"),
            "v2_economics": c.get("economics"),
            "v2_explanation": c.get("explanation"),
            "regime": (plan.get("regime") or {}).get("regime"),
            "deployment_mode": (plan.get("deployment") or {}).get("mode"),
        })

    return {
        "ok": True,
        "reason": [],
        "decisions": decisions,
        "skips": skips,
        "plan": plan,
    }


def eligible_decisions(ig=None, login=None):
    policy = load_ig_policy()
    min_conf = float(policy.get("min_confidence", 60))
    controls = _capital_scaled_controls(policy)
    max_open = int(controls.get("max_open", policy.get("max_concurrent_positions", 12)))
    max_positions_per_epic = int(controls.get("max_positions_per_epic", policy.get("max_positions_per_epic", 3)))

    ig_snapshot = get_ig_cached_snapshot(force_refresh=False)
    if not ig_snapshot.get("ok"):
        return {"ok": False, "reason": ["ig_snapshot_failed"], "decisions": [], "skips": []}

    v2 = _build_v2_decisions()
    if v2.get("ok") and v2.get("decisions"):
        decisions = v2.get("decisions", [])
        v2_skips = v2.get("skips", [])
    else:
        v2_skips = [{"reason": "v2_no_candidates_or_failed", "detail": v2.get("reason", [])}]
        watchlist = (ig_snapshot.get("watchlist") or {}).get("markets") or []
        decisions = []

        for m in watchlist:
            epic = m.get("epic")
            body = ((m.get("snapshot") or {}).get("body") or {})
            sig = infer_ig_signal(body)
            if not isinstance(sig, dict):
                continue
            decisions.append({
                "epic": epic,
                "name": ((body.get("instrument") or {}).get("name")),
                "action": sig.get("action", "NO_TRADE"),
                "reason": sig.get("reason", ""),
                "confidence": float(sig.get("confidence", 0) or 0),
            })

    if ig is None:
        ig = IGAdapter()

    ig = ig or IGAdapter()
    login = login or (ig_snapshot.get("login") or {})

    if not login.get("ok"):
        login = ig.login()

    if not login.get("ok"):
        return {"ok": False, "reason": ["ig_login_failed_on_execution"], "submitted": [], "closed": [], "skips": []}

    ig.cst = login.get("cst")
    ig.x_security_token = login.get("x_security_token")

    if not ig.cst or not ig.x_security_token:
        login = ig.login()
        if not login.get("ok"):
            return {"ok": False, "reason": ["ig_login_failed_on_execution"], "submitted": [], "closed": [], "skips": []}
    acc = _ensure_account(ig, login)
    if not acc.get("ok"):
        return {"ok": False, "reason": [acc["reason"]], "decisions": [], "skips": []}

    allowed, why = combined_entry_allowed()
    soft_locked = (why in ("combined_daily_target_hit_soft_lock", "combined_daily_target_hit_soft_lock_bypassed"))

    if not allowed and why not in (
        "combined_capital_usage_cap_reached",
        "combined_daily_target_hit_soft_lock",
        "combined_daily_target_hit_soft_lock_bypassed",
    ):
        return {"ok": False, "reason": [why], "decisions": [], "skips": []}

    live = _live_position_summary(ig)
    live_positions = live["positions"]

    picked = []
    skips = list(v2_skips) if 'v2_skips' in locals() else []

    for d in decisions:
        action = d.get("action")
        conf = float(d.get("confidence", 0) or 0)
        epic = d.get("epic")
        direction = action_to_direction(action)

        if action not in ("WATCH_LONG", "WATCH_SHORT"):
            skips.append({"epic": epic, "reason": "signal_not_actionable"})
            continue

        if conf < min_conf:
            skips.append({"epic": epic, "reason": "signal_faded", "confidence": conf})
            continue

        same_side = _same_side_positions(live_positions, epic, direction)
        epic_total = int(live["epic_counts"].get(epic, 0))

        if epic_total >= max_positions_per_epic:
            skips.append({"epic": epic, "direction": direction, "reason": "epic_at_cap"})
            continue

        re_ok, re_reason = reentry_allowed(epic)
        if not re_ok:
            skips.append({"epic": epic, "direction": direction, "reason": re_reason})
            continue

        if (epic, direction) in live["same_side_keys"]:
            force_scale = (
                float(controls.get("deployment_gap_pct", 0) or 0) >= float(policy.get("deployment_force_scale_gap_pct", 10.0) or 10.0)
                and conf >= float(policy.get("deployment_force_scale_min_confidence", 75.0) or 75.0)
            )
            if force_scale or _pyramiding_allowed(policy, same_side, conf):
                picked.append(d)
            else:
                skips.append({"epic": epic, "direction": direction, "reason": "already_in_book"})
            continue

        if live["count"] >= max_open:
            skips.append({"epic": epic, "direction": direction, "reason": "book_at_cap"})
            continue

        picked.append(d)

    return {"ok": True, "reason": [], "decisions": picked, "skips": skips}

def _close_conflicting_positions(ig, decisions):
    smart = evaluate_live_positions()
    live_positions = smart.get("managed_positions", [])
    closed = []

    desired_map = {}
    for d in decisions:
        desired_map[d["epic"]] = action_to_direction(d["action"])

    for p in live_positions:
        desired = desired_map.get(p["epic"])
        smart_action = p.get("agent_action")

        should_close = False
        close_reason = p.get("agent_reason", "Agent close decision")
        close_size = p["size"]

        if smart_action in ("CLOSE_NOW", "TAKE_PROFIT"):
            should_close = True
        elif smart_action == "TAKE_PARTIAL":
            should_close = True
            close_size = p.get("partial_size", p["size"])
        elif desired and desired != p["direction"]:
            should_close = True
            close_reason = "Conflicted with new agent signal"

        if not should_close:
            continue

        close_result = ig.close_position(
            deal_id=p["deal_id"],
            direction=opposite_direction(p["direction"]),
            size=close_size,
            expiry="-"
        )

        body = close_result.get("body") if isinstance(close_result.get("body"), dict) else {}
        deal_ref = body.get("dealReference") if isinstance(body, dict) else None

        if close_result.get("ok"):
            mark_exit_for_reentry(p["epic"])
            send_ig_trade_alert(
                "IG FX Position Closed",
                [
                    f"Market: {p['name']}",
                    f"EPIC: {p['epic']}",
                    f"Direction Closed: {p['direction']}",
                    f"Size: {close_size}",
                    f"Deal Ref: {deal_ref or '-'}",
                    f"Reason: {close_reason}"
                ]
            )
            closed.append({
                "epic": p["epic"],
                "deal_id": p["deal_id"],
                "status": "CLOSE_SUBMITTED",
                "deal_reference": deal_ref,
                "reason": close_reason
            })
        else:
            closed.append({
                "epic": p["epic"],
                "deal_id": p["deal_id"],
                "status": "CLOSE_REJECTED",
                "error": close_result.get("body")
            })
    return closed


def run_ig_demo_execution(precomputed_pick=None, ig=None, login=None):
    ensure_ig_tables()
    policy = load_ig_policy()
    auto_execute = bool(policy.get("auto_execute", False))
    demo_only = bool(policy.get("demo_only", True))

    allowed, why = combined_entry_allowed()
    soft_locked = (not allowed and why == "combined_daily_target_hit_soft_lock")

    # hard-stop style blockers still stop everything
    if not allowed and why not in ("combined_capital_usage_cap_reached", "combined_daily_target_hit_soft_lock", "combined_daily_target_hit_soft_lock_bypassed"):
        return {"ok": False, "reason": [why], "submitted": [], "closed": [], "skips": []}

    sizing_plan = get_execution_sizing_plan()

    if precomputed_pick is not None:
        pick = precomputed_pick
        if not pick.get("ok"):
            return {"ok": False, "reason": pick.get("reason", []), "submitted": [], "closed": [], "skips": pick.get("skips", [])}
        if not pick.get("decisions") and not soft_locked:
            return {"ok": True, "reason": ["no_eligible_decisions"], "submitted": [], "closed": [], "skips": pick.get("skips", [])}

    ig_snapshot = get_ig_cached_snapshot(force_refresh=False)
    if not ig_snapshot.get("ok"):
        return {"ok": False, "reason": ["ig_snapshot_failed_on_execution"], "submitted": [], "closed": [], "skips": []}

    ig = ig or IGAdapter()
    login = login or (ig_snapshot.get("login") or {})

    if not login.get("ok"):
        login = ig.login()

    if not login.get("ok"):
        return {"ok": False, "reason": ["ig_login_failed_on_execution"], "submitted": [], "closed": [], "skips": []}
    acc = _ensure_account(ig, login)
    if not acc.get("ok"):
        return {"ok": False, "reason": [acc["reason"]], "submitted": [{"account_error": acc}], "closed": [], "skips": []}

    # in soft-lock profit harvest mode, do NOT check lane-entry permission for new deployment
    if not soft_locked:
        lane_ok, lane_reason = lane_entry_allowed("ig")
        if not lane_ok and lane_reason not in ("ig_lane_cap_reached", "ig_lane_snapshot_failed"):
            return {"ok": False, "reason": [lane_reason], "submitted": [], "closed": [], "skips": []}
        sizing_block_reasons = sizing_plan.get("block_reasons", []) or []

        if not sizing_plan.get("entry_allowed", True):
            only_regime_block = (
                len(sizing_block_reasons) == 1 and
                "regime_conviction_too_low" in sizing_block_reasons
            )

            if not only_regime_block:
                return {
                    "ok": False,
                    "reason": sizing_block_reasons or ["entry_blocked"],
                    "submitted": [],
                    "closed": closed if 'closed' in locals() else [],
                    "skips": []
                }
    pick = precomputed_pick if precomputed_pick is not None else eligible_decisions(ig=ig, login=login)
    if not pick.get("ok"):
        pick_reason = pick.get("reason", [])
        if "combined_daily_target_hit_soft_lock" in pick_reason:
            pick = {"ok": True, "decisions": [], "skips": pick.get("skips", [])}
        else:
            return {"ok": False, "reason": pick_reason, "submitted": [], "closed": [], "skips": pick.get("skips", [])}

    original_decisions = pick.get("decisions", [])
    decision_list = [] if soft_locked else original_decisions

    # always allow exit/harvest management, even in soft lock
    closed = _close_conflicting_positions(ig, original_decisions)
    submitted = []
    skips = list(pick.get("skips", []))

    if not decision_list:
        return {
            "ok": True,
            "reason": ["soft_lock_close_only"] if soft_locked else ["no_eligible_decisions"],
            "submitted": [],
            "closed": closed,
            "skips": skips
        }

    live = _live_position_summary(ig)
    controls = _capital_scaled_controls(policy)
    max_open = int(controls.get("max_open", policy.get("max_concurrent_positions", 12)))
    max_positions_per_epic = int(controls.get("max_positions_per_epic", policy.get("max_positions_per_epic", 3)))

    for d in decision_list:
        epic = d.get("epic")
        name = d.get("name")
        action = d.get("action")
        confidence = d.get("confidence")
        reason = d.get("reason")
        direction = action_to_direction(action)
        size, stop_distance, limit_distance = build_order_params(epic)

        trade_sizing_plan = dict(sizing_plan)
        trade_block_reasons = trade_sizing_plan.get("block_reasons", []) or []
        only_trade_regime_block = (
            (not trade_sizing_plan.get("entry_allowed", True)) and
            len(trade_block_reasons) == 1 and
            "regime_conviction_too_low" in trade_block_reasons
        )

        if only_trade_regime_block:
            trade_sizing_plan["entry_allowed"] = True
            trade_sizing_plan["size_multiplier"] = max(
                float(trade_sizing_plan.get("size_multiplier") or 0.0),
                0.35
            )
        if trade_sizing_plan.get("deployment_mode") == "v2_expand_probe":
            trade_sizing_plan["entry_allowed"] = True
            trade_sizing_plan["size_multiplier"] = max(
                float(trade_sizing_plan.get("size_multiplier") or 0.0),
                0.35
            )

        original_size = size
        size = scale_order_size(size, trade_sizing_plan)
        size = round(size * _confidence_size_boost(confidence), 4)
        size = _round_size_for_ig(size, step=0.1, min_size=0.1)
        if size <= 0:
            skips.append({"epic": epic, "direction": direction, "reason": "size_scaled_to_zero"})
            submitted.append({
                "epic": epic,
                "direction": direction,
                "size": 0,
                "status": "SKIPPED_SIZE_SCALED_TO_ZERO"
            })
            continue

        live = _live_position_summary(ig)

        if live["count"] >= max_open:
            skips.append({"epic": epic, "direction": direction, "reason": "book_at_cap"})
            submitted.append({
                "epic": epic,
                "direction": direction,
                "size": size,
                "status": "SKIPPED_BOOK_AT_CAP"
            })
            continue

        same_side = _same_side_positions(live["positions"], epic, direction)

        if int(live["epic_counts"].get(epic, 0)) >= max_positions_per_epic:
            skips.append({"epic": epic, "direction": direction, "reason": "epic_at_cap"})
            submitted.append({
                "epic": epic,
                "direction": direction,
                "size": size,
                "status": "SKIPPED_EPIC_AT_CAP"
            })
            continue

        re_ok, re_reason = reentry_allowed(epic)
        if not re_ok:
            skips.append({"epic": epic, "direction": direction, "reason": re_reason})
            submitted.append({
                "epic": epic,
                "direction": direction,
                "size": size,
                "status": "SKIPPED_REENTRY_COOLDOWN",
                "reason": re_reason
            })
            continue

        if (epic, direction) in live["same_side_keys"] and not _pyramiding_allowed(policy, same_side, confidence):
            skips.append({"epic": epic, "direction": direction, "reason": "already_in_book"})
            submitted.append({
                "epic": epic,
                "direction": direction,
                "size": size,
                "status": "SKIPPED_ALREADY_IN_BOOK"
            })
            continue

        row_id = log_ig_decision(
            epic=epic,
            market_name=name,
            action=action,
            confidence=confidence,
            reason=reason,
            direction=direction,
            size=size,
            stop_distance=stop_distance,
            limit_distance=limit_distance,
            status="SIMULATED" if not auto_execute else "SUBMITTING"
        )

        if not auto_execute:
            submitted.append({
                "log_id": row_id,
                "epic": epic,
                "name": name,
                "direction": direction,
                "size": size,
                "base_size": original_size,
                "deployment_mode": trade_sizing_plan.get("deployment_mode"),
                "size_multiplier": trade_sizing_plan.get("size_multiplier"),
                "adaptive_behavior": trade_sizing_plan.get("adaptive_behavior", {}),
                "stop_distance": stop_distance,
                "limit_distance": limit_distance,
                "status": "SIMULATED",
                "account_id": ig.account_id,
                "demo_only": demo_only
            })
            continue

        trade_ccy = _instrument_currency_code(ig, epic)

        result = ig.open_position(
            epic=epic,
            direction=direction,
            size=size,
            stop_distance=stop_distance,
            limit_distance=limit_distance,
            currency_code=trade_ccy,
            expiry="-"
        )

        body = result.get("body") if isinstance(result.get("body"), dict) else {}
        deal_ref = body.get("dealReference") if isinstance(body, dict) else None

        if not result.get("ok"):
            mark_ig_log(
                row_id,
                status="REJECTED",
                raw_response=json.dumps(result.get("body", {}))
            )
            submitted.append({
                "log_id": row_id,
                "epic": epic,
                "direction": direction,
                "size": size,
                "status": "REJECTED",
                "error": result.get("body")
            })
            continue

        recon = _confirm_in_book(ig, epic, direction, size, deal_reference=deal_ref)
        confirm_body = recon.get("confirm_body", {}) or {}
        deal_id = recon.get("deal_id")
        deal_status = recon.get("deal_status", "")
        reason_text = recon.get("reason_text", "")
        matched_position = recon.get("matched_position")

        if matched_position:
            mark_ig_log(
                row_id,
                status="CONFIRMED_IN_BOOK",
                deal_reference=deal_ref,
                deal_id=deal_id,
                raw_response=json.dumps({
                    "confirm": confirm_body,
                    "matched_position": matched_position
                })
            )
            send_ig_trade_alert(
                "IG FX Position Opened",
                [
                    f"Market: {name}",
                    f"EPIC: {epic}",
                    f"Direction: {direction}",
                    f"Size: {size}",
                    f"Deal Ref: {deal_ref or '-'}",
                    f"Deal ID: {deal_id or '-'}",
                    f"Reason: {reason}"
                ]
            )
            submitted.append({
                "log_id": row_id,
                "epic": epic,
                "direction": direction,
                "size": size,
                "status": "CONFIRMED_IN_BOOK",
                "deal_reference": deal_ref,
                "deal_id": deal_id,
            })
        elif deal_status == "ACCEPTED":
            mark_ig_log(
                row_id,
                status="ACCEPTED_NOT_VISIBLE_IN_BOOK",
                deal_reference=deal_ref,
                deal_id=deal_id,
                raw_response=json.dumps({
                    "confirm": confirm_body,
                    "book_positions": recon.get("book_positions", [])
                })
            )
            submitted.append({
                "log_id": row_id,
                "epic": epic,
                "direction": direction,
                "size": size,
                "status": "ACCEPTED_NOT_VISIBLE_IN_BOOK",
                "deal_reference": deal_ref,
                "deal_id": deal_id,
                "reason_text": reason_text
            })
        elif deal_status:
            mark_ig_log(
                row_id,
                status="CONFIRM_REJECTED",
                deal_reference=deal_ref,
                deal_id=deal_id,
                raw_response=json.dumps(confirm_body)
            )
            submitted.append({
                "log_id": row_id,
                "epic": epic,
                "direction": direction,
                "size": size,
                "status": "CONFIRM_REJECTED",
                "deal_reference": deal_ref,
                "deal_id": deal_id,
                "reason_text": reason_text,
                "confirm": confirm_body
            })
        else:
            mark_ig_log(
                row_id,
                status="NOT_VISIBLE_IN_BOOK",
                deal_reference=deal_ref,
                deal_id=deal_id,
                raw_response=json.dumps({
                    "confirm": confirm_body,
                    "book_positions": recon.get("book_positions", [])
                })
            )
            submitted.append({
                "log_id": row_id,
                "epic": epic,
                "direction": direction,
                "size": size,
                "status": "NOT_VISIBLE_IN_BOOK",
                "deal_reference": deal_ref,
                "deal_id": deal_id
            })

    return {"ok": True, "reason": [], "submitted": submitted, "closed": closed, "skips": skips}

def get_ig_execution_snapshot():
    return {
        "policy": load_ig_policy(),
        "recent_log": recent_ig_trade_log(50)
    }
