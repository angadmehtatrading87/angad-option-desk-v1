from app.ig_session_intelligence import get_ig_session_state

def get_weekend_carry_policy():
    s = get_ig_session_state()
    session = s.get("session")

    flatten_all = False
    reduce_only = False
    allow_new_entries = True
    probe_only = False
    max_carry_positions = 2

    if session in ("weekend_closed", "friday_close_window"):
        flatten_all = True
        allow_new_entries = False
        max_carry_positions = 0
    elif session == "friday_reduction":
        reduce_only = True
        allow_new_entries = False
        max_carry_positions = 1
    elif session == "sunday_reopen_probe":
        probe_only = True
        allow_new_entries = True
        max_carry_positions = 1
    elif s.get("entry_mode") == "reduced":
        reduce_only = True

    return {
        "session_state": s,
        "flatten_all": flatten_all,
        "reduce_only": reduce_only,
        "allow_new_entries": allow_new_entries,
        "probe_only": probe_only,
        "max_carry_positions": max_carry_positions,
    }
