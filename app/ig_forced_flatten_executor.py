from app.ig_adapter import IGAdapter
from app.ig_forced_flatten_controller import build_forced_flatten_plan
from app.ig_learning_memory import log_trade_memory
from app.ig_throttle_guard import throttle_status, set_throttle_cooldown, mark_flatten_pending
from app.ig_close_reconciliation import add_pending_close, pending_close_for_deal

def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

def run_forced_flatten(max_batch=3):
    t = throttle_status()
    if t.get("active"):
        return {
            "ok": False,
            "reason": ["ig_throttle_cooldown_active"],
            "throttle": t,
            "plan": build_forced_flatten_plan(max_batch=max_batch),
            "submitted": []
        }

    plan = build_forced_flatten_plan(max_batch=max_batch)
    batch = plan.get("batch", []) or []

    if not batch:
        mark_flatten_pending(False)
        return {
            "ok": True,
            "reason": ["no_flatten_candidates"],
            "plan": plan,
            "submitted": []
        }

    ig = IGAdapter()
    login = ig.login()
    if not login.get("ok"):
        body = login.get("body") if isinstance(login.get("body"), dict) else {}
        err = body.get("errorCode") if isinstance(body, dict) else None
        if err == "error.public-api.exceeded-api-key-allowance":
            set_throttle_cooldown(minutes=20, reason="error.public-api.exceeded-api-key-allowance")
            mark_flatten_pending(True)
            return {
                "ok": False,
                "reason": ["ig_login_failed_for_flatten", "api_throttled_flatten_queued"],
                "throttle": throttle_status(),
                "plan": plan,
                "submitted": []
            }
        return {
            "ok": False,
            "reason": ["ig_login_failed_for_flatten"],
            "plan": plan,
            "submitted": []
        }

    submitted = []

    for p in batch:
        deal_id = p.get("deal_id")
        existing_pending = pending_close_for_deal(deal_id)
        if existing_pending:
            submitted.append({
                "epic": p.get("epic"),
                "deal_id": deal_id,
                "requested_action": p.get("final_management_action") or p.get("agent_action"),
                "close_size": _safe_float(p.get("size")),
                "status": "SKIPPED_PENDING_RECONCILIATION",
                "deal_reference": existing_pending.get("deal_reference"),
                "close_priority": p.get("close_priority"),
                "management_tags": p.get("management_tags", [])
            })
            continue

        action = p.get("final_management_action") or p.get("agent_action")
        size = _safe_float(p.get("size"))
        partial_size = _safe_float(p.get("partial_size"))

        close_size = size
        if action == "TAKE_PARTIAL" and partial_size > 0:
            close_size = min(size, partial_size)

        result = ig.close_position(deal_id=deal_id, direction=p.get("direction"), size=close_size)
        body = result.get("body") if isinstance(result.get("body"), dict) else {}
        deal_ref = body.get("dealReference") if isinstance(body, dict) else None

        row = {
            "epic": p.get("epic"),
            "deal_id": deal_id,
            "requested_action": action,
            "close_size": close_size,
            "status": "CLOSE_SUBMITTED" if result.get("ok") else "CLOSE_REJECTED",
            "deal_reference": deal_ref,
            "close_priority": p.get("close_priority"),
            "management_tags": p.get("management_tags", [])
        }

        if result.get("ok"):
            add_pending_close(
                epic=p.get("epic"),
                deal_id=deal_id,
                direction=p.get("direction"),
                close_size=close_size,
                deal_reference=deal_ref,
                requested_action=action,
                meta={
                    "close_priority": p.get("close_priority"),
                    "management_tags": p.get("management_tags", []),
                    "pnl_points": p.get("pnl_points", 0.0),
                }
            )
        submitted.append(row)

        if result.get("ok"):
            try:
                add_pending_close(
                    epic=p.get("epic"),
                    deal_id=deal_id,
                    direction=p.get("direction"),
                    close_size=close_size,
                    deal_reference=deal_ref,
                    requested_action=action,
                    meta={
                        "close_priority": p.get("close_priority"),
                        "management_tags": p.get("management_tags", []),
                        "pnl_points": p.get("pnl_points", 0.0),
                    }
                )
            except Exception as e:
                row["reconciliation_error"] = str(e)

        try:
            log_trade_memory("forced_flatten", {
                "epic": p.get("epic"),
                "deal_id": deal_id,
                "direction": p.get("direction"),
                "requested_action": action,
                "close_size": close_size,
                "status": row["status"],
                "close_priority": p.get("close_priority"),
                "management_tags": p.get("management_tags", []),
                "pnl_points": p.get("pnl_points", 0.0),
                "regime": p.get("regime"),
                "regime_conviction": p.get("regime_conviction"),
            })
        except Exception:
            pass

    mark_flatten_pending(False)
    return {
        "ok": True,
        "reason": [],
        "plan": plan,
        "submitted": submitted,
        "throttle": throttle_status()
    }
