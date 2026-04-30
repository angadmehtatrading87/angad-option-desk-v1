from app.ig_smart_trade_brain import evaluate_live_positions

def build_forced_flatten_plan(max_batch=3):
    smart = evaluate_live_positions()
    managed = smart.get("managed_positions", []) or []
    carry_policy = smart.get("carry_policy", {}) or {}
    session_state = smart.get("session_state", {}) or {}

    flatten_all = bool(carry_policy.get("flatten_all"))
    reduce_only = bool(carry_policy.get("reduce_only"))

    candidates = []
    for p in managed:
        action = p.get("final_management_action") or p.get("agent_action")
        if flatten_all and action in ("CLOSE_NOW", "TAKE_PROFIT", "TAKE_PARTIAL"):
            candidates.append(p)
        elif reduce_only and action in ("TAKE_PROFIT", "TAKE_PARTIAL", "CLOSE_NOW"):
            candidates.append(p)

    candidates = sorted(
        candidates,
        key=lambda x: float(x.get("close_priority", 0) or 0),
        reverse=True
    )

    batch = candidates[:max_batch]

    return {
        "session_state": session_state,
        "carry_policy": carry_policy,
        "total_candidates": len(candidates),
        "batch_size": len(batch),
        "batch": batch
    }
