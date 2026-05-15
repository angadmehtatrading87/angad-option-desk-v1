from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class ScheduledTask:
    name: str
    func: Callable
    interval_seconds: int
    last_run: float = 0.0
    enabled: bool = True
    run_count: int = 0


class Scheduler:
    def __init__(self) -> None:
        self._tasks: dict[str, ScheduledTask] = {}

    def add_task(self, name: str, func: Callable, interval_seconds: int, enabled: bool = True) -> None:
        self._tasks[name] = ScheduledTask(
            name=name,
            func=func,
            interval_seconds=interval_seconds,
            enabled=enabled,
        )

    def run_pending(self) -> list[str]:
        now = time.time()
        ran = []
        for task in self._tasks.values():
            if not task.enabled:
                continue
            if now - task.last_run >= task.interval_seconds:
                try:
                    task.func()
                    task.run_count += 1
                except Exception:
                    pass
                task.last_run = now
                ran.append(task.name)
        return ran

    def run_now(self, name: str) -> bool:
        task = self._tasks.get(name)
        if not task:
            return False
        try:
            task.func()
            task.last_run = time.time()
            task.run_count += 1
            return True
        except Exception:
            return False

    def enable(self, name: str) -> None:
        if name in self._tasks:
            self._tasks[name].enabled = True

    def disable(self, name: str) -> None:
        if name in self._tasks:
            self._tasks[name].enabled = False

    def status(self) -> list[dict]:
        now = time.time()
        return [
            {
                "name": t.name,
                "enabled": t.enabled,
                "interval_s": t.interval_seconds,
                "last_run_ago_s": round(now - t.last_run) if t.last_run else None,
                "run_count": t.run_count,
            }
            for t in self._tasks.values()
        ]
