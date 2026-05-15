from __future__ import annotations

from app.autonomous_cto import llm_router, state_store

_SYSTEM = """You are a CTO agent for a live FX trading bot. Convert user feedback into a structured engineering task.

Respond ONLY with valid JSON (no markdown fences):
{
  "title": "short task title (under 60 chars)",
  "description": "detailed engineering task description",
  "priority": 1-10 (1=urgent, 10=nice-to-have),
  "area": "trading|risk|infra|monitoring|reporting|broker|config",
  "affected_modules": ["app/module.py"]
}

Examples of feedback → tasks:
- "bot is not trading" → investigate and tune rejection thresholds
- "too many losses on GBPUSD" → add GBPUSD to disabled epics or reduce position size
- "I want daily P&L reports" → build daily P&L report to Telegram
- "API keeps timing out" → improve session resilience and retry logic"""


def extract_engineering_task(feedback: str) -> dict:
    result = llm_router.route_quick(
        prompt=f"User feedback: {feedback}\n\nConvert to engineering task JSON.",
        system=_SYSTEM,
        max_tokens=400,
    )
    if not result.get("ok"):
        return {
            "title": f"User feedback: {feedback[:50]}",
            "description": feedback,
            "priority": 5,
            "area": "general",
            "affected_modules": [],
        }
    import json
    try:
        return json.loads(result["text"])
    except Exception:
        return {
            "title": f"User feedback: {feedback[:50]}",
            "description": feedback,
            "priority": 5,
            "area": "general",
            "affected_modules": [],
        }


def ingest_feedback(text: str, source: str = "telegram") -> dict:
    task = extract_engineering_task(text)
    task_id = state_store.add_task(
        title=task.get("title", text[:60]),
        description=task.get("description", text),
        priority=int(task.get("priority", 5)),
        source=source,
    )
    state_store.log_event("feedback_ingested", "info", f"task_id={task_id} source={source} title={task.get('title')}")
    return {**task, "task_id": task_id}


def add_feedback_task(feedback: str, source: str = "telegram") -> int:
    result = ingest_feedback(feedback, source)
    return int(result.get("task_id", 0))
