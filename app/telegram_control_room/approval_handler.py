from .status_provider import get_approval, append_runtime_event

APPROVAL_PHRASE = "APPROVE WEEKEND DEPLOYMENT"


def approve_deployment(chat_id: str, phrase: str) -> tuple[bool, str]:
    approval = get_approval()
    if not approval["pending"]:
        return False, "No pending weekend deployment approval request."
    if phrase.strip() != APPROVAL_PHRASE:
        return False, "Exact confirmation phrase required."
    append_runtime_event({"type": "deployment_approved", "chat_id": str(chat_id)})
    return True, "Weekend deployment approved and recorded."


def reject_deployment(chat_id: str) -> str:
    append_runtime_event({"type": "deployment_rejected", "chat_id": str(chat_id)})
    return "Weekend deployment rejected and recorded."
