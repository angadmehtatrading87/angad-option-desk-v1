from datetime import datetime, timezone
from pathlib import Path
from .status_provider import update_runtime, append_runtime_event

KILL_PHRASE = "CONFIRM EMERGENCY SHUTDOWN"
RESUME_PHRASE = "CONFIRM SYSTEM RESUME"


def activate_kill_switch(chat_id: str, phrase: str) -> tuple[bool, str]:
    if phrase.strip() != KILL_PHRASE:
        return False, "Exact confirmation phrase required."
    update_runtime({"kill_switch": True, "execution_mode": "emergency_stopped"})
    append_runtime_event({"type": "kill_switch_activated", "chat_id": str(chat_id), "action": "observe_only"})
    report = Path("reports") / f"emergency_shutdown_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(f"# Emergency Shutdown\n\n- timestamp: {datetime.now(timezone.utc).isoformat()}\n- requester_chat_id: {chat_id}\n- action: kill_switch=true, execution_mode=emergency_stopped\n")
    return True, f"Emergency shutdown activated. Report: {report}"


def resume_system(chat_id: str, phrase: str) -> tuple[bool, str]:
    if phrase.strip() != RESUME_PHRASE:
        return False, "Exact confirmation phrase required."
    update_runtime({"kill_switch": False})
    append_runtime_event({"type": "system_resumed", "chat_id": str(chat_id), "action": "kill_switch_cleared"})
    return True, "System resume recorded. Kill switch override cleared."
