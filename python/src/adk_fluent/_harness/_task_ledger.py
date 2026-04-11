"""Task lifecycle tracking — the dispatch/join bridge.

``dispatch()`` and ``join()`` are expression-level primitives —
they launch and synchronize agent-scoped background tasks. But a
harness needs tool-level task management: the LLM should be able
to launch a task, check its status, and list running tasks.

``TaskLedger`` bridges this gap. It's a state-backed task tracker
that:
    1. Exposes LLM-callable tools (launch, check, list, cancel)
    2. Emits lifecycle events through the EventBus
    3. Composes with dispatch/join via hooks (not reimplementation)

Design decisions:
    - **State-backed** — task metadata lives in a dict, not a separate
      registry class. This makes it trivially serializable and
      composable with session state.
    - **Tool interface** — ``ledger.tools()`` returns tool functions
      that the LLM can invoke directly.
    - **Event-driven** — emits TaskEvent through EventBus when wired.
    - **Executor-agnostic** — the ledger tracks metadata, not execution.
      The harness runtime (REPL, web server) provides the actual executor.

Usage::

    ledger = H.task_ledger()

    # Get tools for LLM
    agent = Agent("coder").tools(ledger.tools())

    # Or wire to dispatch hooks for auto-tracking
    agent.middleware(M.after_agent(ledger.on_complete_hook()))
"""

from __future__ import annotations

import time
from collections.abc import Callable
from enum import Enum
from typing import Any

__all__ = ["TaskLedger", "TaskState"]


class TaskState(Enum):
    """Lifecycle state of a tracked task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskLedger:
    """State-backed task lifecycle tracker.

    Tracks named tasks through their lifecycle (pending → running →
    complete/failed/cancelled) and provides LLM-callable tools for
    task management.

    Args:
        max_tasks: Maximum concurrent active tasks.
    """

    def __init__(self, *, max_tasks: int = 10) -> None:
        self._tasks: dict[str, dict[str, Any]] = {}
        self._max_tasks = max_tasks
        self._event_bus: Any = None

    # -----------------------------------------------------------------
    # Configuration
    # -----------------------------------------------------------------

    def with_bus(self, bus: Any) -> TaskLedger:
        """Wire an EventBus for task lifecycle events.

        Args:
            bus: An EventBus instance.

        Returns:
            Self for chaining.
        """
        self._event_bus = bus
        return self

    # -----------------------------------------------------------------
    # Lifecycle operations
    # -----------------------------------------------------------------

    def register(self, name: str, description: str = "") -> dict[str, Any]:
        """Register a new task.

        Args:
            name: Unique task name.
            description: Human-readable description.

        Returns:
            Task metadata dict.

        Raises:
            ValueError: If task exists and is active, or max reached.
        """
        if name in self._tasks:
            existing = self._tasks[name]
            if existing["status"] in (TaskState.RUNNING.value, TaskState.PENDING.value):
                raise ValueError(f"Task '{name}' is already {existing['status']}.")

        active = sum(
            1 for t in self._tasks.values() if t["status"] in (TaskState.RUNNING.value, TaskState.PENDING.value)
        )
        if active >= self._max_tasks:
            raise ValueError(f"Maximum concurrent tasks ({self._max_tasks}) reached.")

        task = {
            "name": name,
            "description": description,
            "status": TaskState.PENDING.value,
            "created_at": time.time(),
            "completed_at": None,
            "result": None,
            "error": None,
        }
        self._tasks[name] = task
        self._emit_event(name, TaskState.PENDING.value)
        return task

    def start(self, name: str) -> None:
        """Mark a task as running.

        Args:
            name: Task name.
        """
        task = self._tasks.get(name)
        if task:
            task["status"] = TaskState.RUNNING.value
            self._emit_event(name, TaskState.RUNNING.value)

    def complete(self, name: str, result: str = "") -> None:
        """Mark a task as complete.

        Args:
            name: Task name.
            result: Result summary.
        """
        task = self._tasks.get(name)
        if task:
            task["status"] = TaskState.COMPLETE.value
            task["result"] = result
            task["completed_at"] = time.time()
            self._emit_event(name, TaskState.COMPLETE.value)

    def fail(self, name: str, error: str = "") -> None:
        """Mark a task as failed.

        Args:
            name: Task name.
            error: Error description.
        """
        task = self._tasks.get(name)
        if task:
            task["status"] = TaskState.FAILED.value
            task["error"] = error
            task["completed_at"] = time.time()
            self._emit_event(name, TaskState.FAILED.value)

    def cancel(self, name: str) -> bool:
        """Cancel a pending or running task.

        Args:
            name: Task name.

        Returns:
            True if cancelled, False if not cancellable.
        """
        task = self._tasks.get(name)
        if task and task["status"] in (TaskState.PENDING.value, TaskState.RUNNING.value):
            task["status"] = TaskState.CANCELLED.value
            task["completed_at"] = time.time()
            self._emit_event(name, TaskState.CANCELLED.value)
            return True
        return False

    # -----------------------------------------------------------------
    # Queries
    # -----------------------------------------------------------------

    def get(self, name: str) -> dict[str, Any] | None:
        """Get task metadata by name."""
        return self._tasks.get(name)

    def list_all(self) -> list[dict[str, Any]]:
        """List all task metadata dicts."""
        return list(self._tasks.values())

    @property
    def active_count(self) -> int:
        """Number of pending or running tasks."""
        return sum(1 for t in self._tasks.values() if t["status"] in (TaskState.PENDING.value, TaskState.RUNNING.value))

    @property
    def size(self) -> int:
        """Total number of tracked tasks."""
        return len(self._tasks)

    # -----------------------------------------------------------------
    # Event emission
    # -----------------------------------------------------------------

    def _emit_event(self, task_name: str, status: str) -> None:
        """Emit a TaskEvent through the wired EventBus."""
        if self._event_bus is not None:
            from adk_fluent._harness._events import TaskEvent

            self._event_bus.emit(TaskEvent(task_name=task_name, status=status))

    # -----------------------------------------------------------------
    # LLM-callable tools
    # -----------------------------------------------------------------

    def tools(self) -> list[Callable]:
        """Create LLM-callable task management tools.

        Returns:
            List of [launch_task, check_task, list_tasks, cancel_task].
        """
        ledger = self

        def launch_task(name: str, description: str = "") -> str:
            """Register a background task for execution.

            The harness runtime will execute the task asynchronously.
            Use ``check_task`` to monitor progress.

            Args:
                name: Unique name for the task.
                description: What the task does.
            """
            try:
                ledger.register(name, description)
                return f"Task '{name}' registered. Use check_task('{name}') to monitor."
            except ValueError as e:
                return f"Error: {e}"

        def check_task(name: str) -> str:
            """Check the status of a background task.

            Args:
                name: Task name.
            """
            task = ledger.get(name)
            if task is None:
                names = ", ".join(t["name"] for t in ledger.list_all()) or "none"
                return f"Error: no task named '{name}'. Active tasks: {names}"

            elapsed = (task["completed_at"] or time.time()) - task["created_at"]
            parts = [
                f"Task: {task['name']}",
                f"Status: {task['status']}",
                f"Elapsed: {elapsed:.1f}s",
            ]
            if task["description"]:
                parts.append(f"Description: {task['description']}")
            if task["result"]:
                parts.append(f"Result: {task['result']}")
            if task["error"]:
                parts.append(f"Error: {task['error']}")
            return "\n".join(parts)

        def list_tasks() -> str:
            """List all background tasks and their statuses."""
            tasks = ledger.list_all()
            if not tasks:
                return "No background tasks."
            lines = []
            for t in tasks:
                elapsed = (t["completed_at"] or time.time()) - t["created_at"]
                lines.append(f"  {t['name']}: {t['status']} ({elapsed:.1f}s)")
            return "Background tasks:\n" + "\n".join(lines)

        def cancel_task(name: str) -> str:
            """Cancel a pending or running background task.

            Args:
                name: Task name to cancel.
            """
            if ledger.cancel(name):
                return f"Task '{name}' cancelled."
            return f"Cannot cancel task '{name}' (not active or not found)."

        return [launch_task, check_task, list_tasks, cancel_task]

    # -----------------------------------------------------------------
    # Bridge from legacy TaskRegistry
    # -----------------------------------------------------------------

    @classmethod
    def from_registry(cls, registry: Any) -> TaskLedger:
        """Create a TaskLedger from a legacy TaskRegistry.

        Copies existing task metadata.

        Args:
            registry: A TaskRegistry instance.

        Returns:
            New TaskLedger with copied tasks.
        """
        ledger = cls(max_tasks=getattr(registry, "max_tasks", 10))
        for task_info in getattr(registry, "list_all", lambda: [])():
            name = getattr(task_info, "name", "")
            if name:
                ledger._tasks[name] = {
                    "name": name,
                    "description": getattr(task_info, "description", ""),
                    "status": getattr(task_info, "status", TaskState.PENDING).value
                    if hasattr(getattr(task_info, "status", None), "value")
                    else str(getattr(task_info, "status", "pending")),
                    "created_at": getattr(task_info, "created_at", time.time()),
                    "completed_at": getattr(task_info, "completed_at", None),
                    "result": getattr(task_info, "result", None),
                    "error": getattr(task_info, "error", None),
                }
        return ledger

    def __repr__(self) -> str:
        active = self.active_count
        return f"TaskLedger(tasks={self.size}, active={active})"
