import json
from datetime import datetime, timezone
from pathlib import Path


class ResearchMemory:
    def __init__(self, path: Path):
        self.path = Path(path)

    def append(self, entry: dict):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        row = dict(entry)
        row.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")

    def latest(self):
        if not self.path.exists():
            return None
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return json.loads(lines[-1]) if lines else None
