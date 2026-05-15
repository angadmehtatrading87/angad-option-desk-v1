from __future__ import annotations

import argparse
import json
import sys
import threading
from datetime import datetime, timezone


def cmd_start(args: argparse.Namespace) -> None:
    from app.autonomous_cto.supervisor import CTOSupervisor
    from app.autonomous_cto.telegram_control import run_telegram_loop
    from app.autonomous_cto import state_store
    state_store.ensure_tables()
    supervisor = CTOSupervisor()
    t = threading.Thread(target=run_telegram_loop, daemon=True)
    t.start()
    supervisor.run_forever()


def cmd_run_once(args: argparse.Namespace) -> None:
    from app.autonomous_cto.supervisor import CTOSupervisor
    from app.autonomous_cto import state_store
    state_store.ensure_tables()
    supervisor = CTOSupervisor()
    result = supervisor.run_diagnostic_cycle()
    print(json.dumps(result, default=str, indent=2))


def cmd_status(args: argparse.Namespace) -> None:
    from app.autonomous_cto import state_store, diagnostics_engine
    state_store.ensure_tables()
    killed = state_store.get_kv("cto_killed", False)
    events = state_store.get_recent_events(hours=24)
    decisions = state_store.get_recent_decisions(limit=5)
    patches = state_store.patches_today()
    print(json.dumps({
        "status": "killed" if killed else "active",
        "patches_today": patches,
        "events_24h": len(events),
        "recent_decisions": decisions[:3],
    }, default=str, indent=2))


def cmd_tasks(args: argparse.Namespace) -> None:
    from app.autonomous_cto import state_store
    state_store.ensure_tables()
    tasks = state_store.get_all_tasks(limit=20)
    print(json.dumps(tasks, default=str, indent=2))


def cmd_telegram(args: argparse.Namespace) -> None:
    from app.autonomous_cto import state_store
    from app.autonomous_cto.telegram_control import run_telegram_loop
    state_store.ensure_tables()
    print(json.dumps({"ts": datetime.now(timezone.utc).isoformat(), "cto": "telegram_loop_start"}))
    run_telegram_loop()


def cmd_diagnose(args: argparse.Namespace) -> None:
    from app.autonomous_cto import state_store, diagnostics_engine
    state_store.ensure_tables()
    diagnosis = diagnostics_engine.run_full_diagnosis()
    issues = diagnostics_engine.identify_top_issues(diagnosis)
    print(json.dumps({"diagnosis": diagnosis, "top_issues": issues}, default=str, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Autonomous CTO Agent")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("start", help="Run supervisor forever (with Telegram thread)")
    sub.add_parser("run-once", help="Run single diagnostic cycle and exit")
    sub.add_parser("status", help="Print current agent state")
    sub.add_parser("tasks", help="List all improvement tasks")
    sub.add_parser("telegram", help="Run Telegram handler only")
    sub.add_parser("diagnose", help="Run and print full diagnosis")

    args = parser.parse_args()

    if args.command == "start":
        cmd_start(args)
    elif args.command == "run-once":
        cmd_run_once(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "tasks":
        cmd_tasks(args)
    elif args.command == "telegram":
        cmd_telegram(args)
    elif args.command == "diagnose":
        cmd_diagnose(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
