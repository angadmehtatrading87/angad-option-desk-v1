from app.ig_broker_transition_watcher import evaluate_broker_transition
from app.ig_execution_sizing import get_execution_sizing_plan
from app.ig_asia_open_playbook import evaluate_asia_open_playbook
from app.ig_close_reconciliation import summarize_reconciliation

def build_monday_monitor():
    watcher = evaluate_broker_transition()
    sizing = get_execution_sizing_plan()
    asia = evaluate_asia_open_playbook()
    recon = summarize_reconciliation()

    ready_for_deploy = bool(
        watcher.get("deploy_gate_open") and
        sizing.get("entry_allowed") and
        asia.get("probe_allowed", False) or asia.get("scale_allowed", False)
    )

    return {
        "watcher": watcher,
        "execution_sizing": sizing,
        "asia_playbook": asia,
        "close_reconciliation": recon,
        "ready_for_deploy": ready_for_deploy
    }
