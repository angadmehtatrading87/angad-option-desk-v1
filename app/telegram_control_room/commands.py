from .status_provider import get_status, get_performance, get_github_report, get_approval


def render_status() -> str:
    s = get_status()
    lines = ["Control Room Status"] + [f"{k}: {v}" for k, v in s.items()]
    return "\n".join(lines)


def render_performance() -> str:
    p = get_performance()
    return "\n".join(["Performance"] + [f"{k}: {v if v is not None else 'unavailable'}" for k, v in p.items()])


def render_github() -> str:
    g = get_github_report()
    return "\n".join(["GitHub/Deployment"] + [f"{k}: {v}" for k, v in g.items()])


def render_approval() -> str:
    a = get_approval()
    if not a["pending"]:
        return "No pending weekend deployment approval request."
    return f"Pending deployment approval:\n{a['path']}\n\n{a['text']}"


def render_help() -> str:
    return (
        "Telegram Control Room commands:\n"
        "/status /trades_today /performance /intelligence /research /github /report /approval\n"
        "/approve_deploy /reject_deploy /kill_switch /system_resume /help\n\n"
        "Telegram is for monitoring, deployment approval, and emergency controls only. "
        "It is not a trade approval terminal."
    )
