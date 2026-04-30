from collections import defaultdict
from app.ig_profit_capture_engine import build_profit_capture_decision
from app.ig_exit_registry import record_exit_event

def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

def rank_managed_positions(managed_positions, session_state=None, carry_policy=None):
    session = (session_state or {}).get("session", "")
    flatten_all = bool((carry_policy or {}).get("flatten_all"))
    reduce_only = bool((carry_policy or {}).get("reduce_only"))

    by_epic = defaultdict(list)
    for p in managed_positions:
        by_epic[p.get("epic")].append(p)

    ranked = []
    for epic, items in by_epic.items():
        # strongest runner in each epic gets a small preservation bias
        best_runner_id = None
        best_runner_score = -10**9
        for p in items:
            score = (
                _safe_float(p.get("pnl_points")) * 10.0 +
                _safe_float(p.get("signal_confidence")) * 1.0 +
                abs(_safe_float(p.get("percentage_change"))) * 100.0
            )
            if score > best_runner_score:
                best_runner_score = score
                best_runner_id = p.get("deal_id")

        for p in items:
            pnl = _safe_float(p.get("pnl_points"))
            conf = _safe_float(p.get("signal_confidence"))
            pct = abs(_safe_float(p.get("percentage_change")))
            size = _safe_float(p.get("size"))
            action = p.get("agent_action", "HOLD")

            priority = 0.0
            tags = []

            if flatten_all:
                priority += 1000
                tags.append("weekend_flatten")

            if reduce_only:
                priority += 200
                tags.append("session_reduce")

            if action == "CLOSE_NOW":
                priority += 500
                tags.append("close_now")
            elif action == "TAKE_PROFIT":
                priority += 300
                tags.append("take_profit")
            elif action == "TAKE_PARTIAL":
                priority += 200
                tags.append("take_partial")

            # duplicates: close weaker duplicates first
            if len(items) > 1:
                if p.get("deal_id") != best_runner_id:
                    priority += 150
                    tags.append("duplicate_weaker")
                else:
                    priority -= 75
                    tags.append("best_runner")

            # weak losers get pushed out
            if pnl < 0:
                priority += min(abs(pnl) * 12.0, 180.0)
                tags.append("loser_cleanup")

            # strong winners can be harvested
            if pnl > 0:
                priority += min(pnl * 8.0, 120.0)
                tags.append("winner_harvest")

            # low confidence positions are less worth carrying
            priority += max(0.0, 70.0 - conf) * 1.5

            # late/closed session penalizes larger positions
            if session in ("friday_reduction", "friday_close_window", "weekend_closed", "sunday_reopen_probe"):
                priority += size * 8.0
                tags.append("session_size_penalty")

            # preserve one strong runner if not hard flatten
            if (not flatten_all) and p.get("deal_id") == best_runner_id and pnl > 5 and conf >= 75 and pct >= 0.08:
                priority -= 120
                tags.append("preserve_runner")
            pnl_points = float(p.get("pnl_points", 0) or 0)
            current_action = p.get("agent_action", "HOLD")
            tags = list(tags or [])

            if pnl_points >= 5 and current_action not in ("CLOSE_NOW", "TAKE_PROFIT", "TAKE_PARTIAL"):
                if pnl_points >= 12:
                    p["agent_action"] = "CLOSE_NOW"
                    p["agent_reason"] = "Locked profit after strong favorable move."
                    if "profit_lock_full" not in tags:
                        tags.append("profit_lock_full")
                else:
                    p["agent_action"] = "TAKE_PARTIAL"
                    p["agent_reason"] = "Locked profit after favorable move; reduce and reassess."
                    if "profit_lock_partial" not in tags:
                        tags.append("profit_lock_partial")
            ranked.append({
                **p,
                "close_priority": round(priority, 2),
                "management_tags": tags
            })

    ranked.sort(key=lambda x: x.get("close_priority", 0), reverse=True)
    return ranked

def choose_management_actions(ranked_positions, session_state=None, carry_policy=None):
    flatten_all = bool((carry_policy or {}).get("flatten_all"))
    max_carry_positions = int((carry_policy or {}).get("max_carry_positions", 0))

    actions = []
    kept = 0

    for p in ranked_positions:
        action = p.get("agent_action", "HOLD")
        final_action = action

        if flatten_all:
            if kept < max_carry_positions and "best_runner" in p.get("management_tags", []) and p.get("pnl_points", 0) > 8:
                final_action = "TAKE_PARTIAL"
                kept += 1
            else:
                final_action = "CLOSE_NOW"

        actions.append({
            **p,
            "final_management_action": final_action
        })

    return actions
def manage_positions(managed_positions, session_state=None, carry_policy=None):
    ranked = rank_managed_positions(
        managed_positions,
        session_state=session_state,
        carry_policy=carry_policy
    )
    actions = choose_management_actions(
        ranked,
        session_state=session_state,
        carry_policy=carry_policy
    )
    return actions
