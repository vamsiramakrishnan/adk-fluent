"""Background task management — named async tasks with status tracking.

Claude Code can run agents in the background and get notified on
completion. This module provides tool closures over adk-fluent's
existing ``dispatch()`` / ``join()`` primitives::

    task_tools = H.tasks()  # [launch_task, check_task, list_tasks]

The task registry tracks status and results. This is a tool-level
interface over the existing expression-level dispatch mechanism.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

__all__ = ["TaskRegistry", "TaskStatus", "task_tools"]


class TaskStatus(Enum):
    """Status of a background task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class _TaskInfo:
    """Metadata for a tracked task."""

    name: str
    description: str
    status: TaskStatus
    created_at: float
    completed_at: float | None = None
    result: str | None = None
    error: str | None = None
    _future: Any = field(default=None, repr=False)


class TaskRegistry:
    """Registry of named background tasks.

    Tracks task lifecycle: launch → running → complete/failed.

    Args:
        max_tasks: Maximum number of concurrent tasks.
    """

    def __init__(self, *, max_tasks: int = 10) -> None:
        self.max_tasks = max_tasks
        self._tasks: dict[str, _TaskInfo] = {}

    def register(self, name: str, description: str = "") -> _TaskInfo:
        """Register a new task. Returns the task info."""
        if name in self._tasks:
            existing = self._tasks[name]
            if existing.status in (TaskStatus.RUNNING, TaskStatus.PENDING):
                raise ValueError(f"Task '{name}' is already {existing.status.value}.")
        active = sum(1 for t in self._tasks.values() if t.status in (TaskStatus.RUNNING, TaskStatus.PENDING))
        if active >= self.max_tasks:
            raise ValueError(f"Maximum concurrent tasks ({self.max_tasks}) reached.")
        info = _TaskInfo(
            name=name,
            description=description,
            status=TaskStatus.PENDING,
            created_at=time.time(),
        )
        self._tasks[name] = info
        return info

    def complete(self, name: str, result: str) -> None:
        """Mark a task as complete with a result."""
        info = self._tasks.get(name)
        if info:
            info.status = TaskStatus.COMPLETE
            info.result = result
            info.completed_at = time.time()

    def fail(self, name: str, error: str) -> None:
        """Mark a task as failed with an error."""
        info = self._tasks.get(name)
        if info:
            info.status = TaskStatus.FAILED
            info.error = error
            info.completed_at = time.time()

    def get(self, name: str) -> _TaskInfo | None:
        """Get task info by name."""
        return self._tasks.get(name)

    def list_all(self) -> list[_TaskInfo]:
        """List all tasks."""
        return list(self._tasks.values())

    def cancel(self, name: str) -> bool:
        """Cancel a pending/running task."""
        info = self._tasks.get(name)
        if info and info.status in (TaskStatus.RUNNING, TaskStatus.PENDING):
            info.status = TaskStatus.CANCELLED
            info.completed_at = time.time()
            if info._future and hasattr(info._future, "cancel"):
                info._future.cancel()
            return True
        return False


def task_tools(registry: TaskRegistry | None = None) -> list[Callable]:
    """Create the background task tool set.

    Note: These tools manage task *metadata*. Actual async execution
    depends on the harness runtime (REPL, web server, etc.) wiring
    the task to a real executor.

    Args:
        registry: Optional task registry (creates one if not provided).

    Returns:
        List of [launch_task, check_task, list_tasks] tools.
    """
    if registry is None:
        registry = TaskRegistry()

    def launch_task(name: str, description: str = "") -> str:
        """Register a background task for execution.

        The harness runtime will execute the task asynchronously.
        Use ``check_task`` to monitor progress.

        Args:
            name: Unique name for the task.
            description: Description of what the task does.
        """
        try:
            registry.register(name, description)
            return f"Task '{name}' registered. Use check_task('{name}') to monitor."
        except ValueError as e:
            return f"Error: {e}"

    def check_task(name: str) -> str:
        """Check the status of a background task.

        Args:
            name: Task name.
        """
        info = registry.get(name)
        if info is None:
            names = ", ".join(t.name for t in registry.list_all()) or "none"
            return f"Error: no task named '{name}'. Active tasks: {names}"

        elapsed = (info.completed_at or time.time()) - info.created_at
        parts = [
            f"Task: {info.name}",
            f"Status: {info.status.value}",
            f"Elapsed: {elapsed:.1f}s",
        ]
        if info.description:
            parts.append(f"Description: {info.description}")
        if info.result:
            parts.append(f"Result: {info.result}")
        if info.error:
            parts.append(f"Error: {info.error}")
        return "\n".join(parts)

    def list_tasks() -> str:
        """List all background tasks and their statuses."""
        tasks = registry.list_all()
        if not tasks:
            return "No background tasks."
        lines = []
        for t in tasks:
            elapsed = (t.completed_at or time.time()) - t.created_at
            lines.append(f"  {t.name}: {t.status.value} ({elapsed:.1f}s)")
        return "Background tasks:\n" + "\n".join(lines)

    return [launch_task, check_task, list_tasks]
