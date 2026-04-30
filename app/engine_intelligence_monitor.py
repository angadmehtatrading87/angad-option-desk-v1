import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path("/home/ubuntu/angad-option-desk-v1")
REPORT_DIR = BASE_DIR / "data" / "engine_monitor_reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

WATCH_FILES = [
    "app/ig_execution_engine.py",
    "app/ig_execution_sizing.py",
    "app/agent_v2_orchestrator.py",
    "app/market_regime_engine.py",
    "app/multi_timeframe_structure_engine.py",
    "app/deployment_doctrine_engine.py",
    "app/pair_edge_engine.py",
    "app/book_construction_engine.py",
    "app/opportunity_ranking_engine.py",
    "app/friction_engine.py",
    "app/loss_state_governor.py",
    "app/position_lifecycle_engine.py",
    "app/explainability_engine.py",
    "config/ig_risk_policy.json",
]


def sh(cmd):
    try:
        out = subprocess.check_output(
            cmd,
            shell=True,
            cwd=str(BASE_DIR),
            stderr=subprocess.STDOUT,
            timeout=30,
            text=True,
        )
        return {"ok": True, "output": out[-6000:]}
    except subprocess.CalledProcessError as e:
        return {"ok": False, "output": str(e.output)[-6000:]}
    except Exception as e:
        return {"ok": False, "output": str(e)}


def file_state():
    rows = []
    for rel in WATCH_FILES:
        p = BASE_DIR / rel
        if not p.exists():
            rows.append({"file": rel, "exists": False})
            continue
        rows.append({
            "file": rel,
            "exists": True,
            "size": p.stat().st_size,
            "mtime": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(),
        })
    return rows


def collect():
    ts = datetime.now(timezone.utc).isoformat()

    report = {
        "ts": ts,
        "file_state": file_state(),
        "compile": sh(
            "python3 -m py_compile "
            "app/ig_execution_engine.py "
            "app/ig_execution_sizing.py "
            "app/agent_v2_orchestrator.py "
            "app/market_regime_engine.py "
            "app/multi_timeframe_structure_engine.py "
            "app/deployment_doctrine_engine.py "
            "app/pair_edge_engine.py "
            "app/book_construction_engine.py "
            "app/opportunity_ranking_engine.py "
            "app/friction_engine.py "
            "app/loss_state_governor.py "
            "app/position_lifecycle_engine.py "
            "app/explainability_engine.py"
        ),
        "ig_service_status": sh("systemctl status angad-ig-execution.service --no-pager -l | tail -80"),
        "app_service_status": sh("systemctl status angad-option-desk.service --no-pager -l | tail -80"),
        "ig_recent_logs": sh("journalctl -u angad-ig-execution.service -n 80 --no-pager -l"),
        "v2_plan": sh(
            "python3 - << 'PY'\n"
            "from app.agent_v2_orchestrator import build_agent_v2_plan\n"
            "import json\n"
            "x=build_agent_v2_plan()\n"
            "print(json.dumps({\n"
            " 'ok': x.get('ok'),\n"
            " 'regime': x.get('regime'),\n"
            " 'deployment': x.get('deployment'),\n"
            " 'loss_governor': x.get('loss_governor'),\n"
            " 'book_directive': x.get('book_directive'),\n"
            " 'candidates': x.get('candidates'),\n"
            "}, indent=2, default=str))\n"
            "PY"
        ),
        "eligible_decisions": sh(
            "python3 - << 'PY'\n"
            "from app.ig_execution_engine import eligible_decisions\n"
            "import json\n"
            "print(json.dumps(eligible_decisions(), indent=2, default=str))\n"
            "PY"
        ),
        "positions": sh(
            "python3 - << 'PY'\n"
            "from app.ig_api_governor import get_ig_cached_snapshot\n"
            "import json\n"
            "x=get_ig_cached_snapshot(force_refresh=True)\n"
            "print(json.dumps(x.get('positions', {}), indent=2, default=str))\n"
            "PY"
        ),
    }

    out = REPORT_DIR / f"engine_monitor_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(report, indent=2, default=str))
    latest = REPORT_DIR / "latest.json"
    latest.write_text(json.dumps(report, indent=2, default=str))
    print(str(out))


if __name__ == "__main__":
    collect()
