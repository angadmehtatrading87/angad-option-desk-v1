import argparse
from datetime import datetime, timezone
from pathlib import Path

from .controller import AgentOpsController
from .email_approval import maybe_send
from .weekend_deployer import run as weekend_run


def _write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def weekly_report(base: Path):
    s = AgentOpsController(base).collect()
    d = datetime.now(timezone.utc).strftime("%Y%m%d")
    p = base / f"reports/weekly_agent_report_{d}.md"
    txt = f"""# Weekly Agent Report

## Executive Summary
Generated automatically.

## Trading Performance
{s['trading_performance']}

## Capital Utilization
See trading section.

## Monthly 4%–5% Target Progress
{s['trading_performance'].get('target_progress')}

## Market Brain Intelligence Status
{s['market_brain']}

## Runtime Health
{s['runtime_health']}

## Development Progress
{s['development']}

## Tests / Code Health
unavailable

## Problems Found
- Data may be unavailable

## Recommended Next PRs
- Improve data adapters

## Deployment Recommendation
Weekend only with approval.

## Approval Required / Not Required
Approval Required
"""
    return _write(p, txt)


def request_approval(base: Path):
    d = datetime.now(timezone.utc).strftime("%Y%m%d")
    p = base / f"reports/weekend_deployment_approval_{d}.md"
    body = """# Weekend Deployment Approval Request

## Approval options
- APPROVE WEEKEND DEPLOYMENT
- REJECT DEPLOYMENT
- APPROVE REPORTING ONLY / NO CODE DEPLOYMENT
"""
    _write(p, body)
    status = maybe_send("Weekend Deployment Approval", body)
    return p, status


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("weekly-report")
    sub.add_parser("request-weekend-approval")
    d = sub.add_parser("weekend-deploy")
    d.add_argument("--force", action="store_true")
    d.add_argument("--approved", action="store_true")
    a = ap.parse_args()
    base = Path(__file__).resolve().parents[2]
    if a.cmd == "weekly-report":
        print(weekly_report(base))
    elif a.cmd == "request-weekend-approval":
        print(request_approval(base))
    elif a.cmd == "weekend-deploy":
        print(weekend_run(base, approved=a.approved, force=a.force))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
