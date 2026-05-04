from .status_provider import (
    get_status,
    get_performance,
    get_github_report,
    get_approval,
    get_positions,
    get_capital,
    get_risk,
    get_why_no_trade,
    get_trades_today,
)


def _render_block(title: str, payload: dict) -> str:
    if payload.get("unavailable_reason"):
        command = payload.get("command")
        prefix = f"{title}\ncommand: {command}\n" if command else f"{title}\n"
        return f"{prefix}unavailable_reason: {payload['unavailable_reason']}"
    lines = [title] + [f"{k}: {v if v is not None else 'unavailable'}" for k, v in payload.items()]
    return "\n".join(lines)


def render_status() -> str:
    return _render_block("Control Room Status", get_status())


def render_performance() -> str:
    return _render_block("Performance", get_performance())


def render_github() -> str:
    return _render_block("GitHub/Deployment", get_github_report())


def render_approval() -> str:
    a = get_approval()
    if not a["pending"]:
        return "No pending weekend deployment approval request."
    return f"Pending deployment approval:\n{a['path']}\n\n{a['text']}"


def render_help() -> str:
    return (
        "Telegram Control Room commands:\n"
        "/status /trades_today /performance /positions /capital /risk /why_no_trade /github /approval /help\n"
        "/approve_deploy /reject_deploy /kill_switch /system_resume\n\n"
        "Telegram is for monitoring, deployment approval, and emergency controls only. "
        "It is not a trade approval terminal."
    )


def render_positions() -> str:
    payload = get_positions()
    if payload.get("open_positions") == 0:
        return "Positions: no open positions."
    return _render_block("Positions", payload)


def render_capital() -> str:
    return _render_block("Capital", get_capital())


def render_risk() -> str:
    return _render_block("Risk", get_risk())


def render_why_no_trade() -> str:
    return _render_block("Why No Trade", get_why_no_trade())


def render_trades_today() -> str:
    return _render_block("Trades Today", get_trades_today())
