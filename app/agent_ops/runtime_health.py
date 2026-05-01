import json
from datetime import datetime, timezone
from pathlib import Path

def now_iso(): return datetime.now(timezone.utc).isoformat()

DEFAULT={"worker_status":"dead","last_worker_loop_time":None,"last_signal_time":None,"last_intent_time":None,"last_trade_time":None,"last_rejection_reason":None,"market_brain_last_scan_time":None,"dashboard_availability":"unknown","api_data_freshness":"unknown","safety_gate_status":"enabled","two_phase_commit_status":"enabled","execution_mode":"shadow","demo_live_mode":"demo","updated_at":None}

class RuntimeHealthStore:
    def __init__(self,path:Path): self.path=Path(path)
    def load(self):
        state=dict(DEFAULT)
        if self.path.exists(): state.update(json.loads(self.path.read_text()))
        return state
    def save(self,state):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        payload=dict(DEFAULT);payload.update(state);payload['updated_at']=now_iso()
        self.path.write_text(json.dumps(payload,indent=2))
        return payload
