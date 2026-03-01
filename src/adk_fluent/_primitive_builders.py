"""Primitive builder classes for adk-fluent expression language.

Contains ``PrimitiveBuilderBase`` which eliminates repeated scaffolding,
plus all primitive builder classes and factory functions.

Extracted from ``_base.py`` to keep it focused on ``BuilderBase``.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable
from typing import Any, ClassVar, Self

from adk_fluent._base import BuilderBase

__all__ = [
    "PrimitiveBuilderBase",
    # Builders
    "_FnStepBuilder",
    "_CaptureBuilder",
    "_ArtifactBuilder",
    "_FallbackBuilder",
    "_TapBuilder",
    "_MapOverBuilder",
    "_TimeoutBuilder",
    "_GateBuilder",
    "_RaceBuilder",
    "_DispatchBuilder",
    "_JoinBuilder",
    # Factory functions
    "tap",
    "expect",
    "map_over",
    "gate",
    "race",
    "dispatch",
    "join",
    # Internal helpers
    "_fn_step",
]


# ======================================================================
# DRY base class for primitive builders
# ======================================================================


class PrimitiveBuilderBase(BuilderBase):
    """Eliminates repeated scaffolding for primitive builders.

    Subclasses declare ``_CUSTOM_ATTRS`` and only implement ``build()`` + ``to_ir()``.
    The base handles ``__init__`` boilerplate and ``_fork_for_operator``.
    """

    _ALIASES: ClassVar[dict[str, str]] = {}
    _CALLBACK_ALIASES: ClassVar[dict[str, str]] = {}
    _ADDITIVE_FIELDS: ClassVar[set[str]] = set()
    _CUSTOM_ATTRS: ClassVar[tuple[str, ...]] = ()

    def __init__(self, name: str, **kw: Any):
        self._config: dict[str, Any] = {"name": name}
        self._callbacks: dict[str, list] = {}
        self._lists: dict[str, list] = {}
        for attr in self._CUSTOM_ATTRS:
            setattr(self, attr, kw.get(attr))

    def _fork_for_operator(self) -> Self:
        clone = super()._fork_for_operator()
        for attr in self._CUSTOM_ATTRS:
            val = getattr(self, attr)
            if isinstance(val, list):
                val = list(val)
            setattr(clone, attr, val)
        return clone


# ======================================================================
# Primitive: _fn_step (pure function wrapper)
# ======================================================================

_fn_step_counter = itertools.count(1)


def _fn_step(fn: Callable) -> BuilderBase:
    """Wrap a pure function as a zero-cost workflow step.

    The function receives a dict (snapshot of session state) and returns
    a dict of updates to merge back into state.
    """
    # Check for artifact operation (A module)
    artifact_op = getattr(fn, "_artifact_op", None)
    if artifact_op is not None:
        name = getattr(fn, "__name__", f"artifact_{artifact_op}")
        if not name.isidentifier():
            name = f"artifact_{artifact_op}"
        return _ArtifactBuilder(name, _atransform=fn)

    # Check for capture_key (S.capture())
    capture_key = getattr(fn, "_capture_key", None)
    if capture_key is not None:
        name = getattr(fn, "__name__", f"capture_{capture_key}")
        if not name.isidentifier():
            name = f"capture_{capture_key}"
        return _CaptureBuilder(name, _capture_key=capture_key)

    name = getattr(fn, "__name__", "_transform")
    if not name.isidentifier():
        name = f"fn_step_{next(_fn_step_counter)}"

    return _FnStepBuilder(name, _fn=fn)


class _FnStepBuilder(PrimitiveBuilderBase):
    """Builder wrapper for a pure function in the expression language."""

    _CUSTOM_ATTRS = ("_fn",)

    def build(self):
        from adk_fluent._primitives import FnAgent

        return FnAgent(name=self._config["name"], fn=self._fn)

    def to_ir(self):
        from adk_fluent._ir import TransformNode

        writes = getattr(self._fn, "_writes_keys", None)
        reads = getattr(self._fn, "_reads_keys", None)

        return TransformNode(
            name=self._config.get("name", "fn_step"),
            fn=self._fn,
            semantics="merge",
            affected_keys=writes,
            reads_keys=reads,
        )


class _CaptureBuilder(PrimitiveBuilderBase):
    """Builder wrapper for S.capture() in the expression language."""

    _CUSTOM_ATTRS = ("_capture_key",)

    def build(self):
        from adk_fluent._primitives import CaptureAgent

        return CaptureAgent(name=self._config["name"], key=self._capture_key)

    def to_ir(self):
        from adk_fluent._ir import CaptureNode

        return CaptureNode(
            name=self._config.get("name", "capture"),
            key=self._capture_key,
        )


class _ArtifactBuilder(PrimitiveBuilderBase):
    """Builder for artifact operations. Created by _fn_step() when it detects _artifact_op."""

    _CUSTOM_ATTRS = ("_atransform",)

    def build(self):
        from adk_fluent._primitives import ArtifactAgent

        return ArtifactAgent(name=self._config["name"], atransform=self._atransform)

    def to_ir(self):
        from adk_fluent._ir import ArtifactNode

        at = self._atransform
        return ArtifactNode(
            name=self._config.get("name", at._name),
            op=at._op,
            bridges_state=at._bridges_state,
            filename=at._filename,
            from_key=at._from_key,
            into_key=at._into_key,
            mime=at._mime,
            scope=at._scope,
            version=at._version,
            produces_artifact=at._produces_artifact,
            consumes_artifact=at._consumes_artifact,
            produces_state=at._produces_state,
            consumes_state=at._consumes_state,
        )


# ======================================================================
# Primitive: fallback (try children in order)
# ======================================================================


class _FallbackBuilder(PrimitiveBuilderBase):
    """Builder for a fallback chain: a // b // c.

    Tries each child in order. First success wins.
    """

    _CUSTOM_ATTRS = ("_children",)

    def build(self):
        from adk_fluent._primitives import FallbackAgent

        built_children = []
        for child in self._children:
            if isinstance(child, BuilderBase):
                built_children.append(child.build())
            else:
                built_children.append(child)

        return FallbackAgent(
            name=self._config["name"],
            sub_agents=built_children,
        )

    def to_ir(self):
        from adk_fluent._ir import FallbackNode

        children = tuple(c.to_ir() if isinstance(c, BuilderBase) else c for c in self._children)
        return FallbackNode(
            name=self._config.get("name", "fallback"),
            children=children,
        )


# ======================================================================
# Primitive: tap (observe without mutating)
# ======================================================================

_tap_counter = itertools.count(1)


def tap(fn: Callable) -> BuilderBase:
    """Create a pure observation step. Reads state, runs side-effect, never mutates.

    Usage:
        pipeline = writer >> tap(lambda s: print(s["draft"])) >> reviewer
    """
    name = getattr(fn, "__name__", "_tap")
    if not name.isidentifier():
        name = f"tap_{next(_tap_counter)}"
    return _TapBuilder(name, _fn=fn)


class _TapBuilder(PrimitiveBuilderBase):
    """Builder for a pure observation step. No state mutation, no LLM."""

    _CUSTOM_ATTRS = ("_fn",)

    def build(self):
        from adk_fluent._primitives import TapAgent

        return TapAgent(name=self._config["name"], fn=self._fn)

    def to_ir(self):
        from adk_fluent._ir import TapNode

        return TapNode(
            name=self._config.get("name", "tap"),
            fn=self._fn,
        )


# ======================================================================
# Primitive: expect (typed state assertion)
# ======================================================================

_expect_counter = itertools.count(1)


def expect(predicate: Callable, message: str = "State assertion failed") -> BuilderBase:
    """Assert a state contract at this pipeline step. Raises ValueError if not met.

    Usage:
        pipeline = writer >> expect(lambda s: "draft" in s, "Draft must exist") >> reviewer
    """
    name = f"expect_{next(_expect_counter)}"

    def _assert_fn(state: dict) -> dict:
        if not predicate(state):
            raise ValueError(message)
        return {}

    _assert_fn.__name__ = name
    return _FnStepBuilder(name, _fn=_assert_fn)


# ======================================================================
# Primitive: map_over (iterate agent over list items)
# ======================================================================

_map_over_counter = itertools.count(1)


def map_over(key: str, agent, *, item_key: str = "_item", output_key: str = "summaries") -> BuilderBase:
    """Iterate over a list in session state, running an agent for each item.

    Usage:
        map_over("items", summarizer, output_key="summaries")
    """
    name = f"map_over_{key}_{next(_map_over_counter)}"
    return _MapOverBuilder(name, _agent=agent, _list_key=key, _item_key=item_key, _output_key=output_key)


class _MapOverBuilder(PrimitiveBuilderBase):
    """Builder for iterating an agent over list items in state."""

    _CUSTOM_ATTRS = ("_agent", "_list_key", "_item_key", "_output_key")

    def build(self):
        from adk_fluent._primitives import MapOverAgent

        sub_agent = self._agent
        if isinstance(sub_agent, BuilderBase):
            sub_agent = sub_agent.build()

        return MapOverAgent(
            name=self._config["name"],
            sub_agents=[sub_agent],
            list_key=self._list_key,
            item_key=self._item_key,
            output_key=self._output_key,
        )

    def to_ir(self):
        from adk_fluent._ir import MapOverNode

        body = self._agent.to_ir() if isinstance(self._agent, BuilderBase) else self._agent
        return MapOverNode(
            name=self._config.get("name", "map_over"),
            list_key=self._list_key,
            body=body,
            item_key=self._item_key,
            output_key=self._output_key,
        )


# ======================================================================
# Primitive: timeout (time-bound agent execution)
# ======================================================================

_timeout_counter = itertools.count(1)


class _TimeoutBuilder(PrimitiveBuilderBase):
    """Builder that wraps an agent with a time limit."""

    _CUSTOM_ATTRS = ("_agent", "_seconds")

    def build(self):
        from adk_fluent._primitives import TimeoutAgent

        sub_agent = self._agent
        if isinstance(sub_agent, BuilderBase):
            sub_agent = sub_agent.build()

        return TimeoutAgent(
            name=self._config["name"],
            sub_agents=[sub_agent],
            seconds=self._seconds,
        )

    def to_ir(self):
        from adk_fluent._ir import TimeoutNode

        body = self._agent.to_ir() if isinstance(self._agent, BuilderBase) else self._agent
        return TimeoutNode(
            name=self._config.get("name", "timeout"),
            body=body,
            seconds=self._seconds,
        )


# ======================================================================
# Primitive: gate (human-in-the-loop approval)
# ======================================================================

_gate_counter = itertools.count(1)


def gate(predicate: Callable, *, message: str = "Approval required", gate_key: str | None = None) -> BuilderBase:
    """Create a human-in-the-loop approval gate.

    Usage:
        gate(lambda s: s.get("risk") == "high", message="Approve high-risk action?")
    """
    name = f"gate_{next(_gate_counter)}"
    if gate_key is None:
        gate_key = f"_{name}"
    return _GateBuilder(name, _predicate=predicate, _message=message, _gate_key=gate_key)


class _GateBuilder(PrimitiveBuilderBase):
    """Builder for a human-in-the-loop approval gate."""

    _CUSTOM_ATTRS = ("_predicate", "_message", "_gate_key")

    def build(self):
        from adk_fluent._primitives import GateAgent

        return GateAgent(
            name=self._config["name"],
            predicate=self._predicate,
            message=self._message,
            gate_key=self._gate_key,
        )

    def to_ir(self):
        from adk_fluent._ir import GateNode

        return GateNode(
            name=self._config.get("name", "gate"),
            predicate=self._predicate,
            message=self._message,
            gate_key=self._gate_key,
        )


# ======================================================================
# Primitive: race (first-to-finish wins)
# ======================================================================


def race(*agents) -> BuilderBase:
    """Run agents concurrently, keep only the first to finish.

    Usage:
        result = race(fast_agent, slow_agent, alternative_agent)
    """
    names = []
    for a in agents:
        if hasattr(a, "_config"):
            names.append(a._config.get("name", "?"))
        else:
            names.append("?")
    name = "race_" + "_".join(names)
    return _RaceBuilder(name, _agents=list(agents))


class _RaceBuilder(PrimitiveBuilderBase):
    """Builder for a race: first sub-agent to finish wins."""

    _CUSTOM_ATTRS = ("_agents",)

    def build(self):
        from adk_fluent._primitives import RaceAgent

        built_agents = []
        for a in self._agents:
            if isinstance(a, BuilderBase):
                built_agents.append(a.build())
            else:
                built_agents.append(a)

        return RaceAgent(
            name=self._config["name"],
            sub_agents=built_agents,
        )

    def to_ir(self):
        from adk_fluent._ir import RaceNode

        children = tuple(a.to_ir() if isinstance(a, BuilderBase) else a for a in self._agents)
        return RaceNode(
            name=self._config.get("name", "race"),
            children=children,
        )


# ======================================================================
# Dispatch/Join builders and factory functions
# ======================================================================

_dispatch_counter = itertools.count(1)
_join_counter = itertools.count(1)


def dispatch(
    *agents,
    names: list[str] | None = None,
    on_complete: Callable | None = None,
    on_error: Callable | None = None,
    stream_to: str | None = None,
    max_tasks: int | None = None,
    # Deprecated aliases
    progress_key: str | None = None,
    task_budget: int | None = None,
) -> BuilderBase:
    """Dispatch agents as background tasks. Pipeline continues immediately.

    Args:
        agents: Builders to run as background tasks.
        names: Explicit task names (derived from agent names if omitted).
        on_complete: Callback ``fn(task_name, result_text)`` on success.
        on_error: Callback ``fn(task_name, exception)`` on failure.
        stream_to: State key for partial result streaming.
        max_tasks: Max concurrent tasks (default 50).
        progress_key: Deprecated alias for *stream_to*.
        task_budget: Deprecated alias for *max_tasks*.

    Usage:
        writer >> dispatch(email_sender, audit_logger) >> formatter >> join()
    """
    _stream_to = stream_to or progress_key
    _max_tasks = max_tasks or task_budget

    task_names = []
    for i, a in enumerate(agents):
        if names and i < len(names):
            task_names.append(names[i])
        elif hasattr(a, "_config"):
            task_names.append(a._config.get("name", f"task_{i}"))
        else:
            task_names.append(f"task_{i}")
    name = f"dispatch_{next(_dispatch_counter)}"
    return _DispatchBuilder(
        name,
        _agents=list(agents),
        _task_names=tuple(task_names),
        _on_complete=on_complete,
        _on_error=on_error,
        _stream_to=_stream_to,
        _max_tasks=_max_tasks,
    )


def join(
    *names: str,
    timeout: float | None = None,
) -> BuilderBase:
    """Wait for dispatched background tasks to complete.

    Usage:
        join()                  # wait for all dispatched tasks
        join("email")           # wait only for the "email" task
        join("a", "b")          # wait for tasks "a" and "b"
        join(timeout=30)        # wait max 30s, continue with whatever completed
    """
    target_names = tuple(names) if names else None
    name = f"join_{next(_join_counter)}"
    return _JoinBuilder(name, _target_names=target_names, _timeout=timeout)


class _DispatchBuilder(PrimitiveBuilderBase):
    """Builder for fire-and-continue dispatch."""

    _CUSTOM_ATTRS = ("_agents", "_task_names", "_on_complete", "_on_error", "_stream_to", "_max_tasks")

    def max_tasks(self, n: int) -> Self:
        """Set the max concurrent tasks for this dispatch (and nested dispatches)."""
        self._max_tasks = n
        return self

    # Deprecated alias
    def task_budget(self, n: int) -> Self:
        """Deprecated: use ``max_tasks()`` instead."""
        return self.max_tasks(n)

    def build(self):
        from adk_fluent._primitives import DispatchAgent

        built_agents = []
        for a in self._agents:
            if isinstance(a, BuilderBase):
                built_agents.append(a.build())
            else:
                built_agents.append(a)

        return DispatchAgent(
            name=self._config["name"],
            sub_agents=built_agents,
            task_names=self._task_names,
            on_complete=self._on_complete,
            on_error=self._on_error,
            stream_to=self._stream_to,
            max_tasks=self._max_tasks,
        )

    def to_ir(self):
        from adk_fluent._ir import DispatchNode

        children = tuple(a.to_ir() if isinstance(a, BuilderBase) else a for a in self._agents)
        return DispatchNode(
            name=self._config.get("name", "dispatch"),
            children=children,
            task_names=self._task_names,
            progress_key=self._stream_to,
        )


class _JoinBuilder(PrimitiveBuilderBase):
    """Builder for dispatch synchronization barrier."""

    _CUSTOM_ATTRS = ("_target_names", "_timeout")

    def build(self):
        from adk_fluent._primitives import JoinAgent

        return JoinAgent(
            name=self._config["name"],
            target_names=self._target_names,
            timeout=self._timeout,
        )

    def to_ir(self):
        from adk_fluent._ir import JoinNode

        return JoinNode(
            name=self._config.get("name", "join"),
            target_names=self._target_names,
            timeout=self._timeout,
        )
