"""SubagentRegistry — dict-like store of :class:`SubagentSpec` keyed by role."""

from __future__ import annotations

from collections.abc import Iterator

from adk_fluent._subagents._spec import SubagentSpec

__all__ = ["SubagentRegistry"]


class SubagentRegistry:
    """A mutable registry of subagent specs keyed by role name.

    The registry is intentionally simple — it is just a typed dict with
    a couple of helpers to build documentation and enforce role
    uniqueness. Thread-safety is not a concern because the registry is
    populated during agent construction, before any invocation runs.
    """

    def __init__(self, specs: list[SubagentSpec] | None = None) -> None:
        self._specs: dict[str, SubagentSpec] = {}
        for spec in specs or []:
            self.register(spec)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def register(self, spec: SubagentSpec) -> None:
        """Register ``spec``. Raises if a spec for the same role exists."""
        if spec.role in self._specs:
            raise ValueError(f"Subagent role {spec.role!r} is already registered; use .replace() to overwrite.")
        self._specs[spec.role] = spec

    def replace(self, spec: SubagentSpec) -> None:
        """Register ``spec``, overwriting any existing entry with the same role."""
        self._specs[spec.role] = spec

    def unregister(self, role: str) -> None:
        """Remove the spec for ``role``. Silent if absent."""
        self._specs.pop(role, None)

    def get(self, role: str) -> SubagentSpec | None:
        """Return the spec for ``role`` or ``None`` if not registered."""
        return self._specs.get(role)

    def require(self, role: str) -> SubagentSpec:
        """Return the spec for ``role`` or raise :class:`KeyError`."""
        if role not in self._specs:
            raise KeyError(f"Unknown subagent role {role!r}. Known roles: {sorted(self._specs)}")
        return self._specs[role]

    # ------------------------------------------------------------------
    # Iteration / introspection
    # ------------------------------------------------------------------

    def roles(self) -> list[str]:
        """Return registered role names in insertion order."""
        return list(self._specs)

    def __iter__(self) -> Iterator[SubagentSpec]:
        return iter(self._specs.values())

    def __len__(self) -> int:
        return len(self._specs)

    def __contains__(self, role: object) -> bool:
        return role in self._specs

    # ------------------------------------------------------------------
    # Documentation helper
    # ------------------------------------------------------------------

    def roster(self) -> str:
        """Render a human-readable roster of all registered specialists.

        Used by :func:`adk_fluent._subagents.make_task_tool` to build the
        task tool's docstring so the parent LLM can pick a role.
        """
        if not self._specs:
            return "(no subagents registered)"
        lines = []
        for spec in self._specs.values():
            desc = spec.description or spec.instruction.splitlines()[0]
            lines.append(f"- {spec.role}: {desc}")
        return "\n".join(lines)
