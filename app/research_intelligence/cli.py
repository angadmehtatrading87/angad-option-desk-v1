import argparse
from datetime import datetime, timezone
from pathlib import Path

from .codex_feedback_generator import write_brief
from .market_researcher import build_research_context
from .research_memory import ResearchMemory
from .strategy_gap_analyzer import analyze
from .trade_review import review
from app.telegram_control_room.status_provider import update_runtime


def daily(base: Path):
    d = datetime.now(timezone.utc).strftime("%Y%m%d")
    p = base / f"reports/daily_research_{d}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    ctx = build_research_context()
    gaps = analyze(ctx)
    p.write_text(f"# Daily Research\n\n## Market regime\n{ctx['market_bias']}\n\n## Suggested improvements\n{gaps}")
    ResearchMemory(base / "data/research_journal.jsonl").append(
        {"session": "daily", "market_regime": ctx["market_bias"], "news_sentiment_availability": "unavailable"}
    )
    update_runtime({
        "research_intelligence_status": "ok",
        "research_last_daily_time": datetime.now(timezone.utc).isoformat(),
        "research_daily_report_path": str(p),
        "research_latest_report_path": str(p),
    })
    return p


def weekly(base: Path):
    d = datetime.now(timezone.utc).strftime("%Y%m%d")
    p = base / f"reports/weekly_strategy_review_{d}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    rv = review()
    ctx = build_research_context()
    gaps = analyze(ctx)
    p.write_text("# Weekly Strategy Review\n\n" + str(rv) + "\n" + str(gaps))
    brief = write_brief(base, {"review": rv, "gaps": gaps})
    update_runtime({
        "research_intelligence_status": "ok",
        "research_last_weekly_strategy_review_time": datetime.now(timezone.utc).isoformat(),
        "research_weekly_report_path": str(p),
        "research_latest_report_path": str(brief),
    })
    return p, brief


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd")
    sp.add_parser("daily-research")
    sp.add_parser("weekly-strategy-review")
    a = ap.parse_args()
    base = Path(__file__).resolve().parents[2]
    if a.cmd == "daily-research":
        print(daily(base))
    elif a.cmd == "weekly-strategy-review":
        print(weekly(base))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
