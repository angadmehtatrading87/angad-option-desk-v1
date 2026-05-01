from datetime import datetime, timezone
from pathlib import Path


def write_brief(base: Path, summary: dict):
    d = datetime.now(timezone.utc).strftime("%Y%m%d")
    p = base / f"reports/codex_improvement_brief_{d}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# Codex Improvement Brief\n\n" + str(summary), encoding="utf-8")
    return p
