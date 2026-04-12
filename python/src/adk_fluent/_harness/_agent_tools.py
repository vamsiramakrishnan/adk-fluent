"""Agent self-management tools — TodoStore, PlanMode, AskUser, WorktreeManager.

Mirrors the TypeScript ``agent-tools.ts`` module. These are the
"ceremony reducers" that turn a generic LLM into a coding agent: the
model uses ``todo_write`` to track its own task list, ``enter_plan_mode``
to propose changes before touching files, and ``enter_worktree`` to
isolate a speculative refactor on its own branch.
"""

from __future__ import annotations

import subprocess
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

__all__ = [
    "TodoItem",
    "TodoStore",
    "PlanMode",
    "WorktreeManager",
    "make_ask_user_tool",
    "MUTATING_TOOLS",
]

TodoStatus = Literal["pending", "in_progress", "completed"]


@dataclass
class TodoItem:
    content: str
    active_form: str
    status: TodoStatus = "pending"


# ─── TodoStore ────────────────────────────────────────────────────────────


class TodoStore:
    """In-memory todo list with single-in-progress invariant.

    Mirrors Claude Code's ``TodoWriteTool``: the model owns the list and
    sends a full snapshot on every write. The store enforces that at most
    one task is ``in_progress`` at any time.
    """

    def __init__(self) -> None:
        self._items: list[TodoItem] = []

    def list(self) -> list[TodoItem]:
        return list(self._items)

    def replace(self, items: Sequence[dict | TodoItem]) -> None:
        normalized: list[TodoItem] = []
        for raw in items:
            if isinstance(raw, TodoItem):
                normalized.append(TodoItem(raw.content, raw.active_form, raw.status))
            else:
                normalized.append(
                    TodoItem(
                        content=raw["content"],
                        active_form=raw.get("active_form", raw.get("activeForm", "")),
                        status=raw.get("status", "pending"),
                    )
                )
        in_progress = sum(1 for t in normalized if t.status == "in_progress")
        if in_progress > 1:
            raise ValueError(f"TodoStore: at most one task can be 'in_progress' (got {in_progress})")
        self._items = normalized

    def clear(self) -> None:
        self._items = []

    def tools(self) -> list[Callable]:
        store = self

        def todo_write(todos: list[dict]) -> dict:
            """Replace the todo list with a fresh snapshot.

            Args:
                todos: Full list of ``{content, active_form, status}`` dicts.
                    ``status`` is one of ``pending``, ``in_progress``,
                    ``completed``. At most one item may be ``in_progress``.
            """
            store.replace(todos)
            return {
                "count": len(store._items),
                "items": [
                    {"content": t.content, "active_form": t.active_form, "status": t.status} for t in store._items
                ],
            }

        def todo_read() -> dict:
            """Return the current todo list."""
            return {
                "items": [
                    {"content": t.content, "active_form": t.active_form, "status": t.status} for t in store._items
                ]
            }

        todo_write.__name__ = "todo_write"
        todo_read.__name__ = "todo_read"
        return [todo_write, todo_read]


# ─── PlanMode ─────────────────────────────────────────────────────────────


MUTATING_TOOLS = frozenset(
    {
        "write_file",
        "edit_file",
        "bash",
        "run_code",
        "git_commit",
        "start_process",
    }
)


class PlanMode:
    """Plan-mode latch.

    When the latch is in ``planning``, the harness should reject every
    write/edit/exec tool call and surface the proposed plan to the user
    instead. The harness wires the latch into ``PermissionPolicy`` (or a
    ``ToolPolicy`` "ask" action).
    """

    def __init__(self) -> None:
        self._state: Literal["off", "planning", "executing"] = "off"
        self._plan = ""

    @property
    def current(self) -> str:
        return self._state

    @property
    def current_plan(self) -> str:
        return self._plan

    @staticmethod
    def is_mutating(tool_name: str) -> bool:
        return tool_name in MUTATING_TOOLS

    def enter(self) -> None:
        self._state = "planning"
        self._plan = ""

    def exit(self, plan: str) -> None:
        self._state = "executing"
        self._plan = plan

    def reset(self) -> None:
        self._state = "off"
        self._plan = ""

    def tools(self) -> list[Callable]:
        latch = self

        def enter_plan_mode() -> dict:
            """Enter plan mode. The agent should propose a plan, not act."""
            latch.enter()
            return {"state": latch._state}

        def exit_plan_mode(plan: str) -> dict:
            """Exit plan mode with the finalized plan text.

            Args:
                plan: Markdown / numbered list describing the steps.
            """
            latch.exit(plan)
            return {"state": latch._state, "plan": latch._plan}

        enter_plan_mode.__name__ = "enter_plan_mode"
        exit_plan_mode.__name__ = "exit_plan_mode"
        return [enter_plan_mode, exit_plan_mode]


# ─── AskUser ──────────────────────────────────────────────────────────────


AskUserHandler = Callable[[str, list[str] | None], str]


def make_ask_user_tool(handler: AskUserHandler | None = None) -> Callable:
    """Build an ``ask_user_question`` LLM tool.

    The handler is supplied by the embedding application: a CLI harness
    might prompt on stdin, a web UI might push to a websocket. The
    default handler raises so SDK consumers don't silently hang on a
    missing UI.
    """

    def _default_handler(question: str, options: list[str] | None = None) -> str:
        raise RuntimeError(
            "ask_user_question: no handler installed. Pass H.ask_user(lambda q, opts: ...) when wiring the harness."
        )

    cb: AskUserHandler = handler or _default_handler

    def ask_user_question(question: str, options: list[str] | None = None) -> dict:
        """Ask the user a question and return their answer.

        Args:
            question: The natural-language question to put to the user.
            options: Optional list of answer choices to constrain to.
        """
        answer = cb(question, options)
        return {"answer": answer}

    return ask_user_question


# ─── WorktreeManager ──────────────────────────────────────────────────────


class WorktreeManager:
    """Git worktree manager.

    Spawns isolated worktrees of the workspace so the agent can experiment
    on a branch without polluting the main checkout.
    """

    def __init__(self, workspace: str | Path) -> None:
        self.workspace = str(workspace)
        self._created: dict[str, str] = {}

    def enter(self, branch: str, path: str, base_ref: str | None = None) -> str:
        args = ["git", "worktree", "add", "-b", branch, path]
        if base_ref:
            args.append(base_ref)
        subprocess.run(args, cwd=self.workspace, check=True, capture_output=True)
        self._created[branch] = path
        return path

    def exit(self, branch: str, force: bool = False) -> None:
        path = self._created.get(branch)
        if not path:
            raise RuntimeError(f"No worktree for branch '{branch}'")
        args = ["git", "worktree", "remove"]
        if force:
            args.append("--force")
        args.append(path)
        subprocess.run(args, cwd=self.workspace, check=True, capture_output=True)
        del self._created[branch]

    def list(self) -> list[str]:
        return list(self._created.keys())

    def tools(self) -> list[Callable]:
        wm = self

        def enter_worktree(branch: str, path: str, base_ref: str | None = None) -> dict:
            """Create a new git worktree on a fresh branch."""
            wm.enter(branch, path, base_ref)
            return {"branch": branch, "path": path}

        def exit_worktree(branch: str, force: bool = False) -> dict:
            """Remove a previously-created worktree."""
            wm.exit(branch, force=force)
            return {"ok": True}

        def list_worktrees() -> dict:
            """List active worktree branches."""
            return {"branches": wm.list()}

        enter_worktree.__name__ = "enter_worktree"
        exit_worktree.__name__ = "exit_worktree"
        list_worktrees.__name__ = "list_worktrees"
        return [enter_worktree, exit_worktree, list_worktrees]


# Re-exported for type hints
__all__ += ["AskUserHandler", "TodoStatus"]
_ = (Awaitable, Any, field)  # silence import-only warnings
