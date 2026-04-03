"""Conversation forking — branch and merge session state.

Claude Code maintains conversation context that can be branched for
parallel exploration. This module provides state-level forking:

- ``ForkManager`` manages named branches of session state
- ``fork()`` saves current state as a named branch
- ``switch()`` restores a branch's state
- ``merge()`` combines states from multiple branches

Composes with ADK's session state (``callback_context.state``),
``.reads()``/``.writes()`` data flow, and ``SessionTape`` for
event-level branching.

Usage::

    forks = H.forks()

    # Save current exploration as a branch
    forks.fork("approach_a", current_state)

    # Try another approach
    forks.fork("approach_b", different_state)

    # Compare and merge
    merged = forks.merge("approach_a", "approach_b", strategy="union")

    # Or switch back
    state = forks.switch("approach_a")
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from typing import Any

__all__ = ["ForkManager", "Branch"]


@dataclass
class Branch:
    """A named conversation branch with state snapshot."""

    name: str
    state: dict[str, Any]
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    parent: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ForkManager:
    """Manages named branches of conversation state.

    Each branch is a snapshot of the session state dict (from
    ``callback_context.state``). Branches can be created, restored,
    compared, and merged.

    The manager is state-agnostic — it stores plain dicts. Integration
    with ADK sessions happens via callbacks that read/write the managed
    state.

    Args:
        max_branches: Maximum number of branches (0 = unlimited).
    """

    def __init__(self, *, max_branches: int = 20) -> None:
        self._branches: dict[str, Branch] = {}
        self._active: str | None = None
        self._max_branches = max_branches

    def fork(
        self,
        name: str,
        state: dict[str, Any],
        *,
        messages: list[dict[str, Any]] | None = None,
        parent: str | None = None,
        **metadata: Any,
    ) -> Branch:
        """Create a named branch from current state.

        Args:
            name: Branch name.
            state: Current session state dict (deep-copied).
            messages: Optional message history snapshot.
            parent: Parent branch name (for lineage tracking).
            **metadata: Arbitrary metadata to attach.

        Returns:
            The created Branch.
        """
        if self._max_branches and len(self._branches) >= self._max_branches:
            oldest = min(self._branches.values(), key=lambda b: b.created_at)
            del self._branches[oldest.name]

        branch = Branch(
            name=name,
            state=copy.deepcopy(state),
            messages=list(messages) if messages else [],
            parent=parent or self._active,
            metadata=dict(metadata),
        )
        self._branches[name] = branch
        self._active = name
        return branch

    def switch(self, name: str) -> dict[str, Any]:
        """Switch to a named branch, returning its state.

        Args:
            name: Branch name to restore.

        Returns:
            Deep copy of the branch's state dict.

        Raises:
            KeyError: If branch doesn't exist.
        """
        if name not in self._branches:
            available = ", ".join(sorted(self._branches.keys()))
            raise KeyError(f"Branch '{name}' not found. Available: {available}")

        self._active = name
        return copy.deepcopy(self._branches[name].state)

    def merge(
        self,
        *branch_names: str,
        strategy: str = "union",
        prefer: str | None = None,
    ) -> dict[str, Any]:
        """Merge state from multiple branches.

        Strategies:
            - ``"union"``: Combine all keys. Last branch wins on conflicts.
            - ``"intersection"``: Keep only keys present in all branches.
            - ``"prefer"``: Use ``prefer`` branch for conflicts.

        Args:
            *branch_names: Names of branches to merge.
            strategy: Merge strategy.
            prefer: Branch to prefer on conflicts (for "prefer" strategy).

        Returns:
            Merged state dict.
        """
        if not branch_names:
            branch_names = tuple(self._branches.keys())

        states = []
        for name in branch_names:
            if name not in self._branches:
                raise KeyError(f"Branch '{name}' not found.")
            states.append(self._branches[name].state)

        if not states:
            return {}

        if strategy == "intersection":
            # Keep only keys present in ALL branches
            common_keys = set(states[0].keys())
            for s in states[1:]:
                common_keys &= set(s.keys())
            # Use last branch's values for common keys
            return {k: copy.deepcopy(states[-1][k]) for k in common_keys}

        if strategy == "prefer" and prefer:
            # Start with union, but prefer specific branch on conflicts
            result: dict[str, Any] = {}
            prefer_state = None
            for name, state in zip(branch_names, states):
                result.update(copy.deepcopy(state))
                if name == prefer:
                    prefer_state = state
            if prefer_state:
                result.update(copy.deepcopy(prefer_state))
            return result

        # Default: union (last wins)
        result = {}
        for state in states:
            result.update(copy.deepcopy(state))
        return result

    def diff(self, branch_a: str, branch_b: str) -> dict[str, Any]:
        """Compare two branches and return differences.

        Returns a dict with keys:
            - ``only_a``: keys only in branch A
            - ``only_b``: keys only in branch B
            - ``different``: keys with different values
            - ``same``: keys with identical values

        Args:
            branch_a: First branch name.
            branch_b: Second branch name.
        """
        a = self._branches[branch_a].state
        b = self._branches[branch_b].state

        keys_a = set(a.keys())
        keys_b = set(b.keys())

        return {
            "only_a": {k: a[k] for k in keys_a - keys_b},
            "only_b": {k: b[k] for k in keys_b - keys_a},
            "different": {k: {"a": a[k], "b": b[k]} for k in keys_a & keys_b if a[k] != b[k]},
            "same": {k for k in keys_a & keys_b if a[k] == b[k]},
        }

    def delete(self, name: str) -> None:
        """Delete a branch.

        Args:
            name: Branch name to delete.
        """
        self._branches.pop(name, None)
        if self._active == name:
            self._active = None

    def list_branches(self) -> list[dict[str, Any]]:
        """List all branches with metadata."""
        return [
            {
                "name": b.name,
                "parent": b.parent,
                "keys": len(b.state),
                "messages": len(b.messages),
                "active": b.name == self._active,
                **b.metadata,
            }
            for b in self._branches.values()
        ]

    @property
    def active(self) -> str | None:
        """Name of the currently active branch."""
        return self._active

    @property
    def size(self) -> int:
        """Number of branches."""
        return len(self._branches)

    def get(self, name: str) -> Branch:
        """Get a branch by name.

        Raises:
            KeyError: If branch doesn't exist.
        """
        return self._branches[name]

    def save_callback(self, branch_name: str) -> Any:
        """Create an after_agent callback that auto-saves state to a branch.

        Args:
            branch_name: Branch name to save state to.
        """
        manager = self

        def _auto_fork(callback_context: Any) -> None:
            state = getattr(callback_context, "state", None)
            if state is not None:
                state_dict = dict(state) if hasattr(state, "items") else {}
                manager.fork(branch_name, state_dict)

        return _auto_fork

    def restore_callback(self, branch_name: str) -> Any:
        """Create a before_agent callback that restores state from a branch.

        Args:
            branch_name: Branch name to restore from.
        """
        manager = self

        def _auto_restore(callback_context: Any) -> None:
            if branch_name in manager._branches:
                restored = manager.switch(branch_name)
                state = getattr(callback_context, "state", None)
                if state is not None and hasattr(state, "update"):
                    state.update(restored)

        return _auto_restore
