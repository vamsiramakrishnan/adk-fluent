"""BuilderBase mixin -- shared capabilities for all generated fluent builders."""

from __future__ import annotations

import asyncio as _asyncio
import itertools
from collections.abc import Callable
from typing import Any, Self

__all__ = [
    "BuilderBase",
    "BuilderError",
    "ADKFluentError",
    "PrimitiveBuilderBase",
    "until",
    "tap",
    "expect",
    "map_over",
    "gate",
    "race",
    "dispatch",
    "join",
    "get_execution_mode",
    "FnAgent",
    "TapAgent",
    "CaptureAgent",
    "FallbackAgent",
    "MapOverAgent",
    "TimeoutAgent",
    "GateAgent",
    "RaceAgent",
    "DispatchAgent",
    "JoinAgent",
]

# ---------------------------------------------------------------------------
# Re-exports from _primitives (runtime agents, ContextVars, get_execution_mode)
# ---------------------------------------------------------------------------
from adk_fluent._primitives import (
    CaptureAgent as CaptureAgent,
    DispatchAgent as DispatchAgent,
    FallbackAgent as FallbackAgent,
    FnAgent as FnAgent,
    GateAgent as GateAgent,
    JoinAgent as JoinAgent,
    MapOverAgent as MapOverAgent,
    RaceAgent as RaceAgent,
    TapAgent as TapAgent,
    TimeoutAgent as TimeoutAgent,
    _DEFAULT_MAX_TASKS as _DEFAULT_MAX_TASKS,
    _DEFAULT_TASK_BUDGET as _DEFAULT_TASK_BUDGET,
    _dispatch_tasks as _dispatch_tasks,
    _execution_mode as _execution_mode,
    _global_task_budget as _global_task_budget,
    _middleware_dispatch_hooks as _middleware_dispatch_hooks,
    get_execution_mode as get_execution_mode,
)

# ======================================================================
# Sentinel for "not set" — distinct from None
# ======================================================================


class _UnsetType:
    """Sentinel for 'not set' — distinct from None."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __bool__(self):
        return False

    def __repr__(self):
        return "_UNSET"


_UNSET = _UnsetType()


# ======================================================================
# Callback composition helper
# ======================================================================


def _resolve_guard_tuple(spec: tuple) -> Callable:
    """Convert a guard spec tuple into a real async ADK callback.

    Guard tuples have the form ``("guard:<kind>", config)`` where config
    varies by guard type.  These are produced by ``G.xxx()._compile()``
    and need to be resolved into callables before ``_compose_callbacks``
    can chain them.
    """
    kind: str = spec[0]
    config = spec[1]

    if kind == "guard:json":

        async def _guard_json(*, callback_context, llm_response, **_kw):
            import json as _json

            text = _extract_response_text(llm_response)
            if text is None:
                return None
            try:
                _json.loads(text)
            except _json.JSONDecodeError as exc:
                from adk_fluent._exceptions import GuardViolation

                raise GuardViolation("json", "post_model", f"model output is not valid JSON: {exc}") from exc
            return None

        _guard_json.__name__ = "guard_json"
        return _guard_json

    if kind == "guard:length":
        min_len = config["min"]
        max_len = config["max"]

        async def _guard_length(*, callback_context, llm_response, **_kw):
            text = _extract_response_text(llm_response)
            if text is None:
                return None
            n = len(text)
            if n < min_len:
                from adk_fluent._exceptions import GuardViolation

                raise GuardViolation("length", "post_model", f"output too short ({n} < {min_len})")
            if n > max_len:
                from adk_fluent._exceptions import GuardViolation

                raise GuardViolation("length", "post_model", f"output too long ({n} > {max_len})")
            return None

        _guard_length.__name__ = "guard_length"
        return _guard_length

    if kind == "guard:output":
        schema_cls = config

        async def _guard_output(*, callback_context, llm_response, **_kw):
            import json as _json

            from pydantic import ValidationError

            text = _extract_response_text(llm_response)
            if text is None:
                return None
            try:
                data = _json.loads(text)
                schema_cls.model_validate(data)
            except (_json.JSONDecodeError, ValidationError) as exc:
                from adk_fluent._exceptions import GuardViolation

                raise GuardViolation("output", "post_model", f"schema validation failed: {exc}") from exc
            return None

        _guard_output.__name__ = "guard_output"
        return _guard_output

    if kind == "guard:input":
        schema_cls = config

        async def _guard_input(*, callback_context, llm_request, **_kw):
            # Validate input against schema — applied as before_model_callback
            return None  # Input schema validation is advisory

        _guard_input.__name__ = "guard_input"
        return _guard_input

    if kind == "guard:budget":
        max_tokens = config["max_tokens"]
        _budget_used = {"total": 0}

        async def _guard_budget(*, callback_context, llm_response, **_kw):
            usage = getattr(llm_response, "usage_metadata", None)
            if usage:
                prompt_tokens = getattr(usage, "prompt_token_count", 0) or 0
                output_tokens = getattr(usage, "candidates_token_count", 0) or 0
                _budget_used["total"] += prompt_tokens + output_tokens
            if _budget_used["total"] > max_tokens:
                from adk_fluent._exceptions import GuardViolation

                raise GuardViolation(
                    "budget", "post_model", f"token budget exceeded ({_budget_used['total']} > {max_tokens})"
                )
            return None

        _guard_budget.__name__ = "guard_budget"
        return _guard_budget

    if kind == "guard:rate_limit":
        # Rate limiting is best-effort via pre-model check
        async def _guard_rate_limit(*, callback_context, llm_request, **_kw):
            return None  # Rate limiting is advisory in the current impl

        _guard_rate_limit.__name__ = "guard_rate_limit"
        return _guard_rate_limit

    if kind == "guard:max_turns":
        max_n = config["n"]

        async def _guard_max_turns(*, callback_context, llm_request, **_kw):
            session = getattr(callback_context, "session", None)
            if session is None:
                return None
            events = getattr(session, "events", [])
            turn_count = sum(1 for e in events if getattr(e, "author", None) == "user")
            if turn_count > max_n:
                from adk_fluent._exceptions import GuardViolation

                raise GuardViolation("max_turns", "pre_model", f"exceeded {max_n} turns (current: {turn_count})")
            return None

        _guard_max_turns.__name__ = "guard_max_turns"
        return _guard_max_turns

    if kind == "guard:pii":
        detector = config["detector"]
        action = config["action"]
        threshold = config["threshold"]
        replacement = config["replacement"]

        async def _guard_pii(*, callback_context, llm_response, **_kw):
            text = _extract_response_text(llm_response)
            if text is None:
                return None
            findings = await detector.detect(text)
            flagged = [f for f in findings if f.confidence >= threshold]
            if not flagged:
                return None
            if action == "block":
                from adk_fluent._exceptions import GuardViolation

                kinds = ", ".join(f.kind for f in flagged)
                raise GuardViolation("pii", "post_model", f"detected PII ({kinds})")
            # action == "redact": modify response text
            redacted = text
            for f in sorted(flagged, key=lambda x: x.start, reverse=True):
                redacted = redacted[: f.start] + replacement + redacted[f.end :]
            return _replace_response_text(llm_response, redacted)

        _guard_pii.__name__ = "guard_pii"
        return _guard_pii

    if kind == "guard:toxicity":
        judge = config["judge"]
        threshold = config["threshold"]

        async def _guard_toxicity(*, callback_context, llm_response, **_kw):
            text = _extract_response_text(llm_response)
            if text is None:
                return None
            result = await judge.judge(text, {"mode": "toxicity"})
            if not result.passed or result.score >= threshold:
                from adk_fluent._exceptions import GuardViolation

                raise GuardViolation(
                    "toxicity",
                    "post_model",
                    f"content flagged (score={result.score:.2f}, threshold={threshold}, reason={result.reason})",
                )
            return None

        _guard_toxicity.__name__ = "guard_toxicity"
        return _guard_toxicity

    if kind == "guard:topic":
        deny_list = config["deny"]

        async def _guard_topic(*, callback_context, llm_response, **_kw):
            text = _extract_response_text(llm_response)
            if text is None:
                return None
            text_lower = text.lower()
            for topic in deny_list:
                if topic.lower() in text_lower:
                    from adk_fluent._exceptions import GuardViolation

                    raise GuardViolation("topic", "post_model", f"denied topic '{topic}' found in output")
            return None

        _guard_topic.__name__ = "guard_topic"
        return _guard_topic

    if kind == "guard:grounded":
        sources_key = config["sources_key"]

        async def _guard_grounded(*, callback_context, llm_response, **_kw):
            # Grounding check uses LLM judge with sources from state
            text = _extract_response_text(llm_response)
            if text is None:
                return None
            session = getattr(callback_context, "session", None)
            sources = ""
            if session:
                sources = str(session.state.get(sources_key, ""))
            if not sources:
                return None  # No sources to check against
            from adk_fluent._guards import _LLMJudge

            judge = _LLMJudge()
            result = await judge.judge(text, {"mode": "hallucination", "sources": sources})
            if not result.passed:
                from adk_fluent._exceptions import GuardViolation

                raise GuardViolation(
                    "grounded", "post_model", f"content not grounded (score={result.score:.2f}, reason={result.reason})"
                )
            return None

        _guard_grounded.__name__ = "guard_grounded"
        return _guard_grounded

    if kind == "guard:hallucination":
        judge = config["judge"]
        threshold = config["threshold"]
        sources_key = config.get("sources_key", "sources")

        async def _guard_hallucination(*, callback_context, llm_response, **_kw):
            text = _extract_response_text(llm_response)
            if text is None:
                return None
            session = getattr(callback_context, "session", None)
            sources = ""
            if session:
                sources = str(session.state.get(sources_key, ""))
            result = await judge.judge(text, {"mode": "hallucination", "sources": sources})
            if not result.passed or result.score >= threshold:
                from adk_fluent._exceptions import GuardViolation

                raise GuardViolation(
                    "hallucination",
                    "post_model",
                    f"content flagged (score={result.score:.2f}, threshold={threshold}, reason={result.reason})",
                )
            return None

        _guard_hallucination.__name__ = "guard_hallucination"
        return _guard_hallucination

    # Unknown guard type — pass through as no-op with warning
    import logging as _logging

    _logging.getLogger(__name__).warning("Unknown guard type %r — ignored", kind)

    async def _noop(**_kw):
        return None

    return _noop


def _extract_response_text(llm_response) -> str | None:
    """Extract text from an ADK LlmResponse."""
    content = getattr(llm_response, "content", None)
    if content is None:
        return None
    parts = getattr(content, "parts", None)
    if not parts:
        return None
    texts = [getattr(p, "text", "") for p in parts if getattr(p, "text", None)]
    return "\n".join(texts) if texts else None


def _replace_response_text(llm_response, new_text: str):
    """Return a modified LlmResponse with replaced text."""
    from google.genai import types

    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=new_text)],
                ),
            )
        ]
    )


def _compose_callbacks(fns: list) -> Callable:
    """Chain multiple callbacks into a single callable.

    Each runs in order. First non-None return value wins (short-circuit).
    Handles both sync and async callbacks, and resolves guard spec tuples
    into real async callbacks.
    """
    if not fns:
        raise ValueError("_compose_callbacks requires at least one callback")

    # Resolve guard tuples into callables
    resolved = []
    for fn in fns:
        if isinstance(fn, tuple) and len(fn) == 2 and isinstance(fn[0], str) and fn[0].startswith("guard:"):
            resolved.append(_resolve_guard_tuple(fn))
        else:
            resolved.append(fn)

    if len(resolved) == 1:
        return resolved[0]

    async def _composed(*args, **kwargs):
        for fn in resolved:
            result = fn(*args, **kwargs)
            if _asyncio.iscoroutine(result) or _asyncio.isfuture(result):
                result = await result
            if result is not None:
                return result
        return None

    _composed.__name__ = f"composed_{'_'.join(getattr(f, '__name__', '?') for f in resolved)}"
    return _composed


# ======================================================================
# Expression language primitives (defined before BuilderBase, no deps)
# ======================================================================


class _UntilSpec:
    """Specifies conditional loop exit for the * operator.

    Usage:
        from adk_fluent import until
        quality_ok = until(lambda s: s["quality"] == "good", max=5)
        pipeline = (writer >> reviewer) * quality_ok
    """

    __slots__ = ("predicate", "max")

    def __init__(self, predicate: Callable, *, max: int = 10):
        self.predicate = predicate
        self.max = max

    def __repr__(self) -> str:
        return f"until({self.predicate}, max={self.max})"


def until(predicate: Callable, *, max: int = 10) -> _UntilSpec:
    """Create a conditional loop exit spec for the * operator.

    Usage:
        quality_ok = until(lambda s: s["quality"] == "good", max=5)
        pipeline = (writer >> reviewer) * quality_ok
    """
    return _UntilSpec(predicate, max=max)


# Re-export from canonical location for backward compatibility
from adk_fluent._exceptions import BuilderError as BuilderError  # noqa: E402
from adk_fluent._exceptions import ADKFluentError as ADKFluentError  # noqa: E402


class BuilderBase:
    """Mixin base class providing shared builder capabilities.

    All generated builders inherit from this class.
    """

    _ALIASES: dict[str, str]
    _CALLBACK_ALIASES: dict[str, str]
    _ADDITIVE_FIELDS: set[str]
    _ADK_TARGET_CLASS: type | None = None
    _KNOWN_PARAMS: set[str] | None = None

    # Instance attributes — declared here for pyright; initialized in subclass __init__
    _config: dict[str, Any]
    _callbacks: dict[str, list[Callable]]
    _lists: dict[str, list]

    def build(self) -> Any:
        """Build this builder into a native ADK object. Subclasses must override."""
        raise NotImplementedError(f"{type(self).__name__} must implement build()")

    # ------------------------------------------------------------------
    # Copy-on-Write: frozen builders
    # ------------------------------------------------------------------

    def _freeze(self) -> None:
        """Mark this builder as frozen. Next mutation will fork."""
        self._frozen = True

    def _maybe_fork_for_mutation(self) -> Self:
        """If frozen, deep-clone and return unfrozen copy. Otherwise return self."""
        if getattr(self, "_frozen", False):
            from adk_fluent._helpers import deep_clone_builder

            clone = deep_clone_builder(self, self._config.get("name", ""))
            clone._frozen = False
            return clone
        return self

    # ------------------------------------------------------------------
    # Shared __getattr__: dynamic field forwarding
    # ------------------------------------------------------------------

    def __getattr__(self, name: str):
        """Forward unknown attribute access to a config-setter for chaining.

        Validates field names against the ADK target class (Pydantic mode)
        or a static _KNOWN_PARAMS set (init_signature mode). If neither is
        configured (composite/standalone/primitive builders), any field is
        accepted.
        """
        if name.startswith("_"):
            raise AttributeError(name)

        _ALIASES = self.__class__._ALIASES
        _CALLBACK_ALIASES = self.__class__._CALLBACK_ALIASES
        _ADDITIVE_FIELDS = self.__class__._ADDITIVE_FIELDS

        field_name = _ALIASES.get(name, name)

        # Check if it's a callback alias
        if name in _CALLBACK_ALIASES:
            cb_field = _CALLBACK_ALIASES[name]

            def _cb_setter(fn: Callable) -> Self:
                target = self._maybe_fork_for_mutation()
                target._callbacks[cb_field].append(fn)
                return target

            return _cb_setter

        # Validate field name
        _ADK_TARGET_CLASS = self.__class__._ADK_TARGET_CLASS
        _KNOWN_PARAMS = self.__class__._KNOWN_PARAMS

        if _ADK_TARGET_CLASS is not None:
            # Pydantic mode: validate against model_fields
            if field_name not in _ADK_TARGET_CLASS.model_fields:
                available = sorted(
                    set(_ADK_TARGET_CLASS.model_fields.keys()) | set(_ALIASES.keys()) | set(_CALLBACK_ALIASES.keys())
                )
                cls_name = _ADK_TARGET_CLASS.__name__
                raise AttributeError(
                    f"'{name}' is not a recognized field on {cls_name}. Available: {', '.join(available)}"
                )
        elif _KNOWN_PARAMS is not None and field_name not in _KNOWN_PARAMS:
            # init_signature mode: validate against static param set
            available = sorted(_KNOWN_PARAMS | set(_ALIASES.keys()) | set(_CALLBACK_ALIASES.keys()))
            cls_name = self.__class__.__name__
            raise AttributeError(
                f"'{name}' is not a recognized parameter on {cls_name}. Available: {', '.join(available)}"
            )
        # else: composite/standalone/primitive — accept any field

        # Return a setter that stores value and returns self for chaining
        def _setter(value: Any) -> Self:
            target = self._maybe_fork_for_mutation()
            if field_name in _ADDITIVE_FIELDS:
                target._callbacks[field_name].append(value)
            else:
                target._config[field_name] = value
            return target

        return _setter

    # ------------------------------------------------------------------
    # __dir__: REPL autocomplete support
    # ------------------------------------------------------------------

    def __dir__(self):
        base = set(super().__dir__())
        adk_cls = getattr(self.__class__, "_ADK_TARGET_CLASS", None)
        if adk_cls is not None and hasattr(adk_cls, "model_fields"):
            base.update(adk_cls.model_fields.keys())
        known = getattr(self.__class__, "_KNOWN_PARAMS", None)
        if known is not None:
            base.update(known)
        base.update(getattr(self.__class__, "_ALIASES", {}).keys())
        base.update(getattr(self.__class__, "_CALLBACK_ALIASES", {}).keys())
        return sorted(base)

    # ------------------------------------------------------------------
    # __repr__
    # ------------------------------------------------------------------

    @staticmethod
    def _format_value(v: Any) -> str:
        """Format a value for repr display, truncating long strings."""
        if isinstance(v, str):
            if len(v) > 80:
                v = v[:77] + "..."
            return repr(v)
        if isinstance(v, BuilderBase):
            return v._config.get("name", repr(v))
        if callable(v):
            return getattr(v, "__name__", getattr(v, "__qualname__", repr(v)))
        if hasattr(v, "name"):
            return v.name
        return repr(v)

    def _reverse_alias(self, field_name: str) -> str:
        """Return the short alias for a canonical field name, or the field name itself."""
        aliases = getattr(self.__class__, "_ALIASES", {})
        for alias, canonical in aliases.items():
            if canonical == field_name:
                return alias
        return field_name

    def _reverse_callback_alias(self, field_name: str) -> str:
        """Return the short callback alias for a canonical callback field name."""
        cb_aliases = getattr(self.__class__, "_CALLBACK_ALIASES", {})
        for alias, canonical in cb_aliases.items():
            if canonical == field_name:
                return alias
        return field_name

    def __repr__(self) -> str:
        cls_name = self.__class__.__name__
        name = self._config.get("name", "")
        lines = [f'{cls_name}("{name}")']

        # Config fields (skip name and internal _ fields)
        for field, value in self._config.items():
            if field == "name" or field.startswith("_"):
                continue
            display_name = self._reverse_alias(field)
            lines.append(f"  .{display_name}({self._format_value(value)})")

        # Callbacks
        for field, fns in self._callbacks.items():
            if not fns:
                continue
            display_name = self._reverse_callback_alias(field)
            for fn in fns:
                fn_name = self._format_value(fn)
                lines.append(f"  .{display_name}({fn_name})")

        # Lists (tools, sub_agents)
        for field, items in self._lists.items():
            if not items:
                continue
            item_strs = [self._format_value(item) for item in items]
            lines.append(f"  .{field}({', '.join(item_strs)})")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Task 3: Operator Composition (>>, |, *)
    # ------------------------------------------------------------------

    def _fork_for_operator(self) -> Self:
        """Create an operator-safe fork. Shares sub-builders (safe: operators never mutate children)."""
        new = object.__new__(type(self))
        new._config = dict(self._config)
        new._callbacks = {k: list(v) for k, v in self._callbacks.items()}
        new._lists = {k: list(v) for k, v in self._lists.items()}
        if hasattr(self, "_middlewares"):
            new._middlewares = list(self._middlewares)
        return new

    def __rshift__(self, other) -> BuilderBase:
        """Create or extend a Pipeline: a >> b >> c.

        Accepts:
        - BuilderBase (agents, pipelines, etc.)
        - callable (pure function, wrapped as zero-cost step)
        - dict (shorthand for deterministic Route)
        - Route (deterministic branching)
        """
        self._freeze()
        from adk_fluent._routing import Route
        from adk_fluent.workflow import Pipeline

        # Callable operand: wrap as zero-cost FnStep
        if callable(other) and not isinstance(other, BuilderBase | Route | type):
            other = _fn_step(other)

        # Reject unsupported operands (e.g. raw types like int)
        if not isinstance(other, BuilderBase | Route | dict) and not hasattr(other, "build"):
            return NotImplemented

        # Dict operand: convert to deterministic Route
        if isinstance(other, dict):
            output_key = self._config.get("output_key")
            if not output_key:
                raise ValueError(
                    "Left side of >> dict must have .writes() set so the router knows which state key to check."
                )
            route = Route(output_key)
            for value, agent_builder in other.items():
                route.eq(value, agent_builder)
            other = route  # Fall through to Route handling

        # Route operand: store Route directly so to_ir() can produce RouteNode
        if isinstance(other, Route):
            my_name = self._config.get("name", "")
            p = Pipeline(f"{my_name}_routed")
            if isinstance(self, Pipeline):
                for item in self._lists.get("sub_agents", []):
                    p._lists["sub_agents"].append(item)
            else:
                p._lists["sub_agents"].append(self)
            p._lists["sub_agents"].append(other)  # Store Route directly
            # Propagate middleware from self to result
            self_mw = getattr(self, "_middlewares", [])
            if self_mw:
                p._middlewares = list(self_mw)
            return p

        my_name = self._config.get("name", "")
        other_name = other._config.get("name", "") if hasattr(other, "_config") else ""
        if isinstance(self, Pipeline):
            # Clone, then append — original Pipeline unchanged
            clone = self._fork_for_operator()
            clone.step(other)  # type: ignore[arg-type]  # accepts BuilderBase; auto-built at build()
            clone._config["name"] = f"{my_name}_then_{other_name}"
            result = clone
        else:
            name = f"{my_name}_then_{other_name}"
            p = Pipeline(name)
            p.step(self)  # type: ignore[arg-type]  # accepts BuilderBase; auto-built at build()
            p.step(other)  # type: ignore[arg-type]
            result = p

        # Propagate middleware from operands to result
        merged_mw = list(getattr(self, "_middlewares", []))
        other_mw = getattr(other, "_middlewares", []) if isinstance(other, BuilderBase) else []
        for mw in other_mw:
            if mw not in merged_mw:
                merged_mw.append(mw)
        if merged_mw:
            result._middlewares = merged_mw
        return result

    def __rrshift__(self, other) -> BuilderBase:
        """Support callable >> agent syntax."""
        if callable(other) and not isinstance(other, BuilderBase | type):
            left = _fn_step(other)
            return left >> self
        return NotImplemented

    def __or__(self, other: BuilderBase) -> BuilderBase:
        """Create or extend a FanOut: a | b | c."""
        self._freeze()
        from adk_fluent.workflow import FanOut

        my_name = self._config.get("name", "")
        other_name = other._config.get("name", "")
        if isinstance(self, FanOut):
            # Clone, then add branch — original FanOut unchanged
            clone = self._fork_for_operator()
            clone.branch(other)  # type: ignore[arg-type]  # accepts BuilderBase; auto-built at build()
            clone._config["name"] = f"{my_name}_and_{other_name}"
            result = clone
        else:
            name = f"{my_name}_and_{other_name}"
            f = FanOut(name)
            f.branch(self)  # type: ignore[arg-type]  # accepts BuilderBase; auto-built at build()
            f.branch(other)  # type: ignore[arg-type]
            result = f

        # Propagate middleware from operands to result
        merged_mw = list(getattr(self, "_middlewares", []))
        other_mw = getattr(other, "_middlewares", []) if isinstance(other, BuilderBase) else []
        for mw in other_mw:
            if mw not in merged_mw:
                merged_mw.append(mw)
        if merged_mw:
            result._middlewares = merged_mw
        return result

    def __mul__(self, other) -> BuilderBase:
        """Create a Loop: agent * 3 or agent * until(pred)."""
        self._freeze()
        from adk_fluent.workflow import Loop, Pipeline

        # Handle until() spec: agent * until(pred)
        if isinstance(other, _UntilSpec):
            loop = self.__mul__(other.max)
            loop._config["_until_predicate"] = other.predicate
            return loop

        iterations = other
        my_name = self._config.get("name", "")
        name = f"{my_name}_x{iterations}"
        loop = Loop(name)
        loop._config["max_iterations"] = iterations
        if isinstance(self, Pipeline):
            # Move Pipeline's sub_agents into the Loop
            for item in self._lists.get("sub_agents", []):
                loop._lists["sub_agents"].append(item)
        else:
            loop.step(self)  # type: ignore[arg-type]  # accepts BuilderBase; auto-built at build()
        return loop

    def __rmul__(self, iterations: int) -> BuilderBase:
        """Support int * agent syntax."""
        return self.__mul__(iterations)

    def __matmul__(self, schema: type) -> BuilderBase:
        """Bind structured output schema: ``agent @ Schema``.

        Shorthand for ``.returns(Schema)``. Forces the LLM to respond
        with JSON matching this Pydantic model. The agent **cannot use
        tools** when this is set.

        Equivalent to ``.returns(Schema)`` or ``.output(Schema)``.
        """
        self._freeze()
        clone = self._fork_for_operator()
        clone._config["_output_schema"] = schema
        return clone

    def __floordiv__(self, other) -> BuilderBase:
        """Create a fallback chain: agent_a // agent_b.

        Tries each agent in order. First success wins.
        """
        self._freeze()
        from adk_fluent._routing import _make_fallback_builder

        # Callable on right side: wrap it
        if callable(other) and not isinstance(other, BuilderBase | type):
            other = _fn_step(other)

        # Collect children from existing fallback chains
        children: list[Any] = []
        if isinstance(self, _FallbackBuilder):
            children.extend(getattr(self, "_children", []))
        else:
            children.append(self)
        if isinstance(other, _FallbackBuilder):
            children.extend(getattr(other, "_children", []))
        else:
            children.append(other)

        return _make_fallback_builder(children)

    # ------------------------------------------------------------------
    # Task 4: validate() and explain()
    # ------------------------------------------------------------------

    def _safe_build(self, target_class: type, config: dict) -> Any:
        """Wrap target_class(**config) with clear error reporting."""
        try:
            return target_class(**config)
        except Exception as exc:
            import pydantic

            name = self._config.get("name", "?")
            builder_type = self.__class__.__name__
            if isinstance(exc, pydantic.ValidationError):
                field_errors = []
                for err in exc.errors():
                    loc = ".".join(str(x) for x in err.get("loc", []))
                    msg = err.get("msg", str(err))
                    field_errors.append(f"{loc}: {msg}" if loc else msg)
                raise BuilderError(name, builder_type, field_errors, exc) from exc
            raise BuilderError(name, builder_type, [str(exc)], exc) from exc

    def native(self, fn: Callable) -> Self:
        """Post-build hook: fn receives the built ADK object for direct manipulation. Escape hatch for ADK features not yet exposed by the fluent API."""
        target = self._maybe_fork_for_mutation()
        hooks = target._config.setdefault("_native_hooks", [])
        hooks.append(fn)
        return target

    def _apply_native_hooks(self, obj):
        """Run all registered native hooks on the built ADK object."""
        hooks = self._config.get("_native_hooks", [])
        for hook in hooks:
            hook(obj)
        return obj

    def with_raw_config(self, **kwargs: Any) -> Self:
        """Set arbitrary fields on the native ADK object after build.

        Use when the fluent builder doesn't expose a specific ADK parameter.
        This is the recommended escape hatch for edge cases::

            agent = (
                Agent("x", "gemini-2.5-flash")
                .instruct("You are helpful.")
                .with_raw_config(
                    disallow_transfer_to_parent=True,
                    include_contents="none",
                )
                .build()
            )

        Warns at build time if the target ADK object doesn't have the
        specified attribute, preventing silent misconfiguration.

        See Also:
            ``.native(fn)`` for full programmatic access to the ADK object.
        """

        def _apply(obj: Any) -> None:
            for key, value in kwargs.items():
                if not hasattr(obj, key):
                    import warnings

                    attrs = sorted(a for a in dir(obj) if not a.startswith("_"))
                    warnings.warn(
                        f"ADK object {type(obj).__name__} has no attribute '{key}'. "
                        f"Did you mean one of: {', '.join(attrs[:10])}?",
                        UserWarning,
                        stacklevel=2,
                    )
                setattr(obj, key, value)

        return self.native(_apply)

    def validate(self) -> Self:
        """Try to build; raise ValueError with clear message on failure. Returns self."""
        try:
            self.build()
        except Exception as exc:
            name = self._config.get("name", "?")
            raise ValueError(f"Validation failed for {self.__class__.__name__}('{name}'): {exc}") from exc
        return self

    def _explain_plain(self) -> str:
        """Plain-text explain fallback (no rich dependency).

        Shows what the agent does, what data it reads/writes, how it sees
        conversation history, what tools it has, and any contract issues.
        Designed to be immediately useful for debugging data flow problems.
        """
        cls_name = self.__class__.__name__
        name = self._config.get("name", "?")
        lines = [f"{cls_name}: {name}"]

        # Model
        model = self._config.get("model")
        if model:
            lines.append(f"  Model: {model}")

        # Instruction summary
        instruction = self._config.get("instruction", "")
        if instruction:
            if callable(instruction):
                lines.append("  Instruction: <dynamic provider>")
            elif isinstance(instruction, str):
                import re

                # Show first 80 chars + template variables
                preview = instruction[:80].replace("\n", " ")
                if len(instruction) > 80:
                    preview += "..."
                lines.append(f"  Instruction: {preview}")

                # Extract template variables
                template_vars = re.findall(r"\{(\w+)\??\}", instruction)
                if template_vars:
                    required = [v for v in template_vars if f"{{{v}?}}" not in instruction]
                    optional = [v for v in template_vars if f"{{{v}?}}" in instruction]
                    parts = []
                    if required:
                        parts.append(f"required: {', '.join(required)}")
                    if optional:
                        parts.append(f"optional: {', '.join(optional)}")
                    lines.append(f"  Template vars: {'; '.join(parts)}")

        # Data flow: unified five-concern view
        context_spec = self._config.get("_context_spec")
        input_schema = self._config.get("input_schema")
        output_schema = self._config.get("_output_schema") or self._config.get("output_schema")
        output_key = self._config.get("output_key")
        produces_schema = self._config.get("_produces")
        consumes_schema = self._config.get("_consumes")

        lines.append("  Data flow:")

        # reads (context)
        if context_spec is not None:
            from adk_fluent.testing.contracts import _context_description

            lines.append(f"    reads:    {_context_description(context_spec)}")
        else:
            lines.append("    reads:    full conversation history (default)")

        # accepts (input)
        if input_schema is not None:
            schema_name = getattr(input_schema, "__name__", str(input_schema))
            lines.append(f"    accepts:  {schema_name} (tool-mode input validation)")
        else:
            lines.append("    accepts:  (not set — accepts any input as tool)")

        # returns (output)
        if output_schema is not None:
            schema_name = getattr(output_schema, "__name__", str(output_schema))
            lines.append(f"    returns:  {schema_name} (structured JSON — tools disabled)")
        else:
            lines.append("    returns:  plain text (default — can use tools)")

        # writes (storage)
        if output_key:
            lines.append(f'    writes:   state["{output_key}"]')
        else:
            lines.append("    writes:   (not set — response only in conversation)")

        # contract
        contract_parts = []
        if produces_schema:
            fields = list(produces_schema.model_fields.keys())
            contract_parts.append(f"produces {produces_schema.__name__}({', '.join(fields)})")
        if consumes_schema:
            fields = list(consumes_schema.model_fields.keys())
            contract_parts.append(f"consumes {consumes_schema.__name__}({', '.join(fields)})")
        if contract_parts:
            lines.append(f"    contract: {', '.join(contract_parts)}")
        else:
            lines.append("    contract: (not set)")

        # Tools
        tools = list(self._config.get("tools", []))
        tools.extend(self._lists.get("tools", []))
        if tools:
            tool_names = []
            for t in tools:
                if hasattr(t, "name"):
                    tool_names.append(t.name)
                elif hasattr(t, "__name__"):
                    tool_names.append(t.__name__)
                else:
                    tool_names.append(type(t).__name__)
            lines.append(f"  Tools ({len(tools)}): {', '.join(tool_names)}")

        for field, fns in self._callbacks.items():
            if fns:
                alias = self._reverse_callback_alias(field)
                lines.append(f"  Callback '{alias}': {len(fns)} registered")

        # Sub-agents
        children_raw = list(self._config.get("sub_agents", []))
        children_raw.extend(self._lists.get("sub_agents", []))
        if children_raw:
            child_names = [
                getattr(c, "_config", {}).get("name", "?") if hasattr(c, "_config") else str(c) for c in children_raw
            ]
            lines.append(f"  Children ({len(children_raw)}): {', '.join(child_names)}")

        # Other list fields
        for field, items in self._lists.items():
            if items and field != "sub_agents":
                lines.append(f"  {field}: {len(items)} items")

        # Contract issues (if IR is available)
        try:
            ir = self.to_ir()
            from adk_fluent.testing.contracts import check_contracts

            issues = check_contracts(ir)
            if issues:
                lines.append("  Contract issues:")
                for issue in issues:
                    if isinstance(issue, str):
                        lines.append(f"    - {issue}")
                    else:
                        level = issue.get("level", "?")
                        agent = issue.get("agent", "?")
                        msg = issue.get("message", "?")
                        hint = issue.get("hint", "")
                        marker = "ERROR" if level == "error" else "INFO"
                        lines.append(f"    [{marker}] {agent}: {msg}")
                        if hint:
                            lines.append(f"           Hint: {hint}")
        except (NotImplementedError, Exception):
            pass  # IR not available or conversion failed

        return "\n".join(lines)

    def _build_rich_tree(self):
        """Build a rich.tree.Tree representing this builder's state."""
        import re

        from rich.tree import Tree  # type: ignore[reportMissingImports]

        cls_name = self.__class__.__name__
        name = self._config.get("name", "?")
        tree = Tree(f"[bold]{cls_name}[/bold]: {name}")

        # Model
        model = self._config.get("model")
        if model:
            tree.add(f"[cyan]Model[/cyan]: {model}")

        # Instruction summary
        instruction = self._config.get("instruction", "")
        if instruction:
            if callable(instruction):
                tree.add("[cyan]Instruction[/cyan]: <dynamic provider>")
            elif isinstance(instruction, str):
                preview = instruction[:80].replace("\n", " ")
                if len(instruction) > 80:
                    preview += "..."
                tree.add(f"[cyan]Instruction[/cyan]: {preview}")

                template_vars = re.findall(r"\{(\w+)\??\}", instruction)
                if template_vars:
                    required = [v for v in template_vars if f"{{{v}?}}" not in instruction]
                    optional = [v for v in template_vars if f"{{{v}?}}" in instruction]
                    parts = []
                    if required:
                        parts.append(f"required: {', '.join(required)}")
                    if optional:
                        parts.append(f"optional: {', '.join(optional)}")
                    tree.add(f"[cyan]Template vars[/cyan]: {'; '.join(parts)}")

        # Data flow: unified five-concern view
        context_spec = self._config.get("_context_spec")
        input_schema = self._config.get("input_schema")
        output_schema = self._config.get("_output_schema") or self._config.get("output_schema")
        output_key = self._config.get("output_key")
        produces_schema = self._config.get("_produces")
        consumes_schema = self._config.get("_consumes")

        df_branch = tree.add("[blue]Data flow[/blue]")

        # reads (context)
        if context_spec is not None:
            from adk_fluent.testing.contracts import _context_description

            df_branch.add(f"[magenta]reads[/magenta]:    {_context_description(context_spec)}")
        else:
            df_branch.add("[dim]reads:    full conversation history (default)[/dim]")

        # accepts (input)
        if input_schema is not None:
            schema_name = getattr(input_schema, "__name__", str(input_schema))
            df_branch.add(f"[cyan]accepts[/cyan]:  {schema_name} (tool-mode input validation)")
        else:
            df_branch.add("[dim]accepts:  (not set)[/dim]")

        # returns (output)
        if output_schema is not None:
            schema_name = getattr(output_schema, "__name__", str(output_schema))
            df_branch.add(f"[cyan]returns[/cyan]:  {schema_name} (structured JSON — tools disabled)")
        else:
            df_branch.add("[dim]returns:  plain text (default — can use tools)[/dim]")

        # writes (storage)
        if output_key:
            df_branch.add(f'[green]writes[/green]:   state["{output_key}"]')
        else:
            df_branch.add("[dim]writes:   (not set — response only in conversation)[/dim]")

        # contract
        contract_parts = []
        if produces_schema:
            fields = list(produces_schema.model_fields.keys())
            contract_parts.append(f"produces {produces_schema.__name__}({', '.join(fields)})")
        if consumes_schema:
            fields = list(consumes_schema.model_fields.keys())
            contract_parts.append(f"consumes {consumes_schema.__name__}({', '.join(fields)})")
        if contract_parts:
            df_branch.add(f"[yellow]contract[/yellow]: {', '.join(contract_parts)}")
        else:
            df_branch.add("[dim]contract: (not set)[/dim]")

        # Tools
        tools = list(self._config.get("tools", []))
        tools.extend(self._lists.get("tools", []))
        if tools:
            tool_names = []
            for t in tools:
                if hasattr(t, "name"):
                    tool_names.append(t.name)
                elif hasattr(t, "__name__"):
                    tool_names.append(t.__name__)
                else:
                    tool_names.append(type(t).__name__)
            tree.add(f"[yellow]Tools ({len(tools)})[/yellow]: {', '.join(tool_names)}")

        # Other config fields (not already shown)
        _shown = {
            "name",
            "model",
            "instruction",
            "_produces",
            "_consumes",
            "output_key",
            "_context_spec",
            "include_contents",
            "_output_schema",
            "output_schema",
            "input_schema",
            "tools",
        }
        other_fields = {k: v for k, v in self._config.items() if k not in _shown and not k.startswith("_")}
        if other_fields:
            cfg_branch = tree.add("[cyan]Config[/cyan]")
            for k, v in other_fields.items():
                display_name = self._reverse_alias(k)
                cfg_branch.add(f"{display_name}: {self._format_value(v)}")

        # Callbacks
        for field, fns in self._callbacks.items():
            if fns:
                alias = self._reverse_callback_alias(field)
                cb_branch = tree.add(f"[green]Callback '{alias}'[/green]: {len(fns)} registered")
                for fn in fns:
                    cb_branch.add(self._format_value(fn))

        # Sub-agents and other list fields
        children_raw = list(self._config.get("sub_agents", []))
        children_raw.extend(self._lists.get("sub_agents", []))
        if children_raw:
            children_branch = tree.add(f"[yellow]Children ({len(children_raw)})[/yellow]")
            for child in children_raw:
                if isinstance(child, BuilderBase):
                    children_branch.add(child._build_rich_tree())
                else:
                    children_branch.add(self._format_value(child))

        for field, items in self._lists.items():
            if items and field != "sub_agents":
                list_branch = tree.add(f"[yellow]{field}[/yellow]: {len(items)} items")
                for item in items:
                    if isinstance(item, BuilderBase):
                        list_branch.add(item._build_rich_tree())
                    else:
                        list_branch.add(self._format_value(item))

        # Contract issues
        try:
            ir = self.to_ir()
            from adk_fluent.testing.contracts import check_contracts

            issues = check_contracts(ir)
            if issues:
                issues_branch = tree.add("[red]Contract issues[/red]")
                for issue in issues:
                    if isinstance(issue, str):
                        issues_branch.add(issue)
                    else:
                        level = issue.get("level", "?")
                        agent = issue.get("agent", "?")
                        msg = issue.get("message", "?")
                        hint = issue.get("hint", "")
                        marker = "[red]ERROR[/red]" if level == "error" else "[yellow]INFO[/yellow]"
                        node = issues_branch.add(f"{marker} {agent}: {msg}")
                        if hint:
                            node.add(f"[dim]Hint: {hint}[/dim]")
        except (NotImplementedError, Exception):
            pass  # IR not available or conversion failed

        return tree

    # Docs base URL — override with ADKFLUENT_DOCS_URL env var or docs_url= parameter
    _DOCS_BASE_URL = "https://vamsiramakrishnan.github.io/adk-fluent"

    # Map builder class names to their API reference doc page
    _DOCS_PAGE_MAP: dict[str, str] = {
        "Agent": "api/agent",
        "BaseAgent": "api/agent",
        "Pipeline": "api/workflow",
        "Loop": "api/workflow",
        "FanOut": "api/workflow",
        "Runner": "api/runtime",
        "InMemoryRunner": "api/runtime",
        "App": "api/runtime",
    }

    def _docs_url_for(self, base_url: str | None = None) -> str:
        """Return the docs URL for this builder's API reference page."""
        import os

        base = base_url or os.environ.get("ADKFLUENT_DOCS_URL", self._DOCS_BASE_URL)
        base = base.rstrip("/")
        cls_name = self.__class__.__name__
        page = self._DOCS_PAGE_MAP.get(cls_name)
        if page is None:
            # Infer from class name suffix
            if cls_name.endswith("Config"):
                page = "api/config"
            elif cls_name.endswith("Service"):
                page = "api/service"
            elif cls_name.endswith("Tool") or cls_name.endswith("Toolset"):
                page = "api/tool"
            elif cls_name.endswith("Plugin"):
                page = "api/plugin"
            elif cls_name.endswith("Planner"):
                page = "api/planner"
            elif cls_name.endswith("Executor"):
                page = "api/executor"
            else:
                page = "api"
        return f"{base}/{page}/"

    def explain(
        self,
        *,
        format: str = "text",
        docs_url: str | None = None,
        open_browser: bool = False,
    ) -> str | dict:
        """Return a multi-line summary of this builder's state.

        Parameters
        ----------
        format:
            ``"text"`` (default) for human-readable output (rich if available,
            plain otherwise).  ``"json"`` for a machine-readable dict.
        docs_url:
            Base URL for docs links appended to output.  Defaults to the
            published GitHub Pages site.  Set ``ADKFLUENT_DOCS_URL`` env
            var to override globally.
        open_browser:
            If ``True``, open the relevant API docs page in the default
            browser after printing.

        Returns
        -------
        str | dict
            Formatted text when ``format="text"``, a dict when
            ``format="json"``.
        """
        if format == "json":
            result = self._explain_json(docs_url=docs_url)
            if open_browser:
                self._open_docs(docs_url)
            return result

        # --- text mode ---
        try:
            from rich.console import Console  # type: ignore[reportMissingImports]

            tree = self._build_rich_tree()
            console = Console(record=True, width=120)
            console.print(tree)
            text = console.export_text()
        except ImportError:
            text = self._explain_plain()

        # Append docs link
        ref_url = self._docs_url_for(docs_url)
        text += f"\n  Docs: {ref_url}"

        if open_browser:
            self._open_docs(docs_url)

        return text

    def _explain_json(self, *, docs_url: str | None = None) -> dict:
        """Return a structured dict representation of this builder's state."""
        cls_name = self.__class__.__name__
        name = self._config.get("name", "?")
        model = self._config.get("model")
        instruction = self._config.get("instruction", "")

        result: dict[str, Any] = {
            "builder": cls_name,
            "name": name,
            "docs_url": self._docs_url_for(docs_url),
        }

        if model:
            result["model"] = model
        if instruction:
            if callable(instruction):
                result["instruction"] = "<dynamic provider>"
            else:
                result["instruction"] = instruction[:200] + ("..." if len(str(instruction)) > 200 else "")

        # Data flow (five concerns)
        context_spec = self._config.get("_context_spec")
        input_schema = self._config.get("input_schema")
        output_schema = self._config.get("_output_schema") or self._config.get("output_schema")
        output_key = self._config.get("output_key")
        produces = self._config.get("_produces")
        consumes = self._config.get("_consumes")
        data_flow: dict[str, Any] = {}
        if context_spec is not None:
            from adk_fluent.testing.contracts import _context_description

            data_flow["reads"] = _context_description(context_spec)
        if input_schema is not None:
            data_flow["accepts"] = {
                "schema": input_schema.__name__,
                "fields": list(input_schema.model_fields.keys()) if hasattr(input_schema, "model_fields") else [],
            }
        if output_schema is not None:
            data_flow["returns"] = {
                "schema": output_schema.__name__,
                "fields": list(output_schema.model_fields.keys()) if hasattr(output_schema, "model_fields") else [],
            }
        if output_key:
            data_flow["writes"] = output_key
        if consumes:
            data_flow["consumes"] = {"schema": consumes.__name__, "fields": list(consumes.model_fields.keys())}
        if produces:
            data_flow["produces"] = {"schema": produces.__name__, "fields": list(produces.model_fields.keys())}
        if data_flow:
            result["data_flow"] = data_flow

        # Tools
        tools = list(self._config.get("tools", []))
        tools.extend(self._lists.get("tools", []))
        if tools:
            result["tools"] = [
                getattr(t, "name", None) or getattr(t, "__name__", None) or type(t).__name__ for t in tools
            ]

        # Callbacks
        cbs = {}
        for field, fns in self._callbacks.items():
            if fns:
                alias = self._reverse_callback_alias(field)
                cbs[alias] = len(fns)
        if cbs:
            result["callbacks"] = cbs

        # Children
        children_raw = list(self._config.get("sub_agents", []))
        children_raw.extend(self._lists.get("sub_agents", []))
        if children_raw:
            result["children"] = [
                getattr(c, "_config", {}).get("name", "?") if hasattr(c, "_config") else str(c) for c in children_raw
            ]

        # Config (other fields)
        _skip = {
            "name",
            "model",
            "instruction",
            "_produces",
            "_consumes",
            "output_key",
            "input_schema",
            "output_schema",
            "tools",
            "sub_agents",
        }
        other = {k: repr(v) for k, v in self._config.items() if k not in _skip and not k.startswith("_")}
        if other:
            result["config"] = other

        # Contract issues
        try:
            ir = self.to_ir()
            from adk_fluent.testing.contracts import check_contracts

            issues = check_contracts(ir)
            if issues:
                result["contract_issues"] = [
                    {"level": i.get("level", "?"), "agent": i.get("agent", "?"), "message": i.get("message", "?")}
                    if isinstance(i, dict)
                    else {"message": str(i)}
                    for i in issues
                ]
        except (NotImplementedError, Exception):
            pass

        return result

    def _open_docs(self, docs_url: str | None = None) -> None:
        """Open the API reference docs page in the default browser."""
        import webbrowser

        webbrowser.open(self._docs_url_for(docs_url))

    def inspect(self) -> str:
        """Return a detailed view of this builder's full config values."""
        cls_name = self.__class__.__name__
        name = self._config.get("name", "?")
        lines = [f"{cls_name}: {name}"]

        for k, v in self._config.items():
            if k == "name":
                continue
            display_name = self._reverse_alias(k)
            lines.append(f"  {display_name} = {v!r}")

        for field, fns in self._callbacks.items():
            if fns:
                alias = self._reverse_callback_alias(field)
                lines.append(f"  {alias} = {fns!r}")

        for field, items in self._lists.items():
            if items:
                lines.append(f"  {field} = {items!r}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Task 5: Serialization (to_dict, from_dict, to_yaml, from_yaml)
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize_value(v: Any) -> Any:
        """Serialize a single value for dict/yaml output."""
        if callable(v):
            return getattr(v, "__qualname__", repr(v))
        if hasattr(v, "name") and hasattr(v, "model_fields"):
            # Built ADK agent
            return f"<agent:{v.name}>"
        return v

    def to_dict(self) -> dict[str, Any]:
        """Serialize builder state to a plain dict."""
        cls_name = self.__class__.__name__
        # Config: skip internal _ fields
        config = {k: self._serialize_value(v) for k, v in self._config.items() if not k.startswith("_")}
        # Callbacks: store qualname strings
        callbacks: dict[str, list[str]] = {}
        for field, fns in self._callbacks.items():
            if fns:
                callbacks[field] = [self._serialize_value(fn) for fn in fns]
        # Lists
        lists: dict[str, list] = {}
        for field, items in self._lists.items():
            if items:
                lists[field] = [self._serialize_value(item) for item in items]
        return {
            "_type": cls_name,
            "config": config,
            "callbacks": callbacks,
            "lists": lists,
        }

    def to_yaml(self) -> str:
        """Serialize builder state to YAML string.

        Requires the ``pyyaml`` package (``pip install pyyaml``).
        """
        try:
            import yaml
        except ImportError as e:
            raise ImportError("to_yaml() requires the 'pyyaml' package. Install it with: pip install pyyaml") from e
        return yaml.dump(self.to_dict(), default_flow_style=False)

    # ------------------------------------------------------------------
    # Task 6: with_() — Immutable Variants
    # ------------------------------------------------------------------

    def with_(self, **overrides: Any) -> Self:
        """Clone this builder and apply overrides. Original unchanged."""
        from adk_fluent._helpers import deep_clone_builder

        new_name = overrides.pop("name", self._config.get("name", ""))
        new_builder = deep_clone_builder(self, new_name)
        # Resolve aliases in overrides
        aliases = getattr(self.__class__, "_ALIASES", {})
        for key, value in overrides.items():
            field_name = aliases.get(key, key)
            new_builder._config[field_name] = value
        return new_builder

    # ------------------------------------------------------------------
    # _prepare_build_config() — shared build preparation
    # ------------------------------------------------------------------

    def _prepare_build_config(self) -> dict[str, Any]:
        """Prepare config dict for building: strip internal fields, auto-build sub-builders, merge callbacks and lists."""
        # Run IR-first contract checking (appendix_f Q1, Q3)
        self._run_build_contracts()

        # Extract internal directives before stripping
        until_pred = self._config.get("_until_predicate")
        output_schema = self._config.get("_output_schema")
        context_spec = self._config.get("_context_spec")

        config = {k: v for k, v in self._config.items() if not k.startswith("_") and v is not _UNSET}

        # Wire @-operator output schema into ADK's native output_schema field
        if output_schema is not None:
            config["output_schema"] = output_schema

        # Auto-convert PTransform objects to strings
        from adk_fluent._prompt import PTransform

        for key, value in list(config.items()):
            if isinstance(value, PTransform):
                config[key] = str(value)

        # Auto-build any BuilderBase values in config
        for key, value in list(config.items()):
            if isinstance(value, BuilderBase):
                config[key] = value.build()

        # Merge accumulated callbacks
        for field, fns in self._callbacks.items():
            if fns:
                config[field] = _compose_callbacks(list(fns))

        # Merge accumulated lists (auto-building items, skip internal _ keys)
        for field, items in self._lists.items():
            if field.startswith("_"):
                continue
            resolved = []
            for item in items:
                if isinstance(item, BuilderBase) or hasattr(item, "build") and callable(item.build):
                    resolved.append(item.build())
                else:
                    resolved.append(item)
            existing = config.get(field, [])
            if isinstance(existing, list):
                config[field] = existing + resolved
            else:
                config[field] = resolved

        # Context spec: compile C transforms into include_contents + InstructionProvider
        if context_spec is not None:
            from adk_fluent._context import CTransform, CWriteNotes, _compile_context_spec

            # Handle CWriteNotes: register after_agent_callback
            write_notes_specs: list[CWriteNotes] = []
            remaining_spec = context_spec
            if isinstance(context_spec, CWriteNotes):
                write_notes_specs.append(context_spec)
                remaining_spec = None
            elif hasattr(context_spec, "blocks"):
                # CComposite — separate CWriteNotes from other blocks
                non_write = []
                for block in context_spec.blocks:
                    if isinstance(block, CWriteNotes):
                        write_notes_specs.append(block)
                    else:
                        non_write.append(block)
                if non_write:
                    from adk_fluent._context import CComposite

                    remaining_spec = CComposite(blocks=tuple(non_write)) if len(non_write) > 1 else non_write[0]
                else:
                    remaining_spec = None

            # Compile CWriteNotes to after_agent callbacks
            if write_notes_specs:
                from adk_fluent._context import make_write_notes_callback

                cbs = config.setdefault("after_agent_callback", [])
                if not isinstance(cbs, list):
                    cbs = [cbs]
                    config["after_agent_callback"] = cbs
                for wn in write_notes_specs:
                    cbs.append(
                        make_write_notes_callback(
                            wn.key,
                            wn.strategy,
                            wn.source_key,
                        )
                    )

            # Compile remaining context spec normally
            if remaining_spec is not None and isinstance(remaining_spec, CTransform):
                compiled = _compile_context_spec(
                    developer_instruction=config.get("instruction", ""),
                    context_spec=remaining_spec,
                )
                config["include_contents"] = compiled["include_contents"]
                if compiled.get("instruction") is not None:
                    config["instruction"] = compiled["instruction"]

        # Prompt spec: compile P transforms into instruction string or InstructionProvider
        prompt_spec = self._config.get("_prompt_spec")
        if prompt_spec is not None:
            from adk_fluent._prompt import PTransform as _PTransform
            from adk_fluent._prompt import _compile_prompt_spec

            if isinstance(prompt_spec, _PTransform):
                compiled = _compile_prompt_spec(
                    prompt_spec=prompt_spec,
                    existing_instruction=config.get("instruction"),
                )
                config["instruction"] = compiled

        # UI spec: compile A2UI surface into tools + prompt + callbacks
        ui_spec = self._config.get("_ui_spec")
        if ui_spec is not None:
            from adk_fluent._ui_compile import compile_ui_for_agent

            compile_ui_for_agent(ui_spec, config)

        # Inject checkpoint agent for loop_until predicate
        if until_pred:
            from adk_fluent._routing import _make_checkpoint_agent

            checkpoint = _make_checkpoint_agent("_until_check", until_pred)
            config.setdefault("sub_agents", []).append(checkpoint)

        return config

    # ------------------------------------------------------------------
    # clone() — universal deep-copy
    # ------------------------------------------------------------------

    def clone(self, new_name: str) -> Self:
        """Deep-copy this builder with a new name. Independent config/callbacks/lists."""
        from adk_fluent._helpers import deep_clone_builder

        return deep_clone_builder(self, new_name)

    # ------------------------------------------------------------------
    # Task 7: Presets (.use())
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Task 8: Structured Output (.output())
    # ------------------------------------------------------------------

    def output(self, schema: type) -> Self:
        """Constrain LLM responses to a Pydantic model and parse them automatically.

        This does two things:

        1. **At build time**: sets ADK's ``output_schema``, which forces the
           LLM to respond *only* with JSON matching this schema. The agent
           **cannot use tools** when ``output_schema`` is set.
        2. **At .ask() time**: parses the raw JSON response into an instance
           of ``schema``, so ``.ask()`` returns a Pydantic model instead of
           a string.

        The ``@`` operator is shorthand for this method::

            agent @ MyModel   # same as agent.output(MyModel)

        .. note:: **Distinction from similar methods:**

           - ``.output(Model)`` / ``@ Model``: Constrains LLM output format
             AND parses response. Use when you need typed data back.
           - ``.output_schema(Model)``: ADK's raw field. Same LLM constraint
             but no automatic parsing in ``.ask()``.
           - ``.writes(key)`` / ``.save_as(key)``: Stores the agent's *text*
             response in a state key. Does NOT affect output format.
           - ``.produces(Model)``: **Contract-only** annotation for the
             data-flow checker. No runtime effect whatsoever.
        """
        self._config["_output_schema"] = schema
        return self

    # ------------------------------------------------------------------
    # Task 10: Retry and Fallback
    # ------------------------------------------------------------------

    # .retry() and .fallback() removed in v0.10.0.
    # Use .generate_content_config() for model-level retry/fallback settings.

    # ------------------------------------------------------------------
    # Task 11: Debug Trace Mode (.debug())
    # ------------------------------------------------------------------

    def debug(self, enabled: bool = True) -> Self:
        """Enable or disable debug tracing to stderr."""
        self._config["_debug"] = enabled
        return self

    # ------------------------------------------------------------------
    # Control Flow: proceed_if, loop_until, until
    # ------------------------------------------------------------------

    def prepend(self, fn: Callable) -> Self:
        """Prepend dynamic text to the LLM's input each turn via before_model_callback.

        ``fn(callback_context)`` → str is injected as a user content part
        before the LLM processes the request. Use for dynamic context that
        changes per-turn (user metadata, timestamps, etc.).

        Usage:
            agent.prepend(lambda ctx: f"Current user: {ctx.state.get('user')}")
        """

        def _inject_cb(callback_context, llm_request):
            text = fn(callback_context)
            if text:
                from google.genai import types

                part = types.Part.from_text(text=str(text))
                content = types.Content(role="user", parts=[part])
                llm_request.contents.insert(0, content)
            return None

        self._callbacks["before_model_callback"].append(_inject_cb)
        return self

    def proceed_if(self, predicate: Callable) -> Self:
        """Only run this agent if predicate(state) is truthy.

        Uses ADK's before_agent_callback mechanism. If the predicate returns
        False, the agent is skipped and the pipeline continues to the next step.

        Usage:
            enricher.proceed_if(lambda s: s.get("valid") == "yes")
        """

        def _gate_cb(callback_context):
            state = callback_context.state
            try:
                if not predicate(state):
                    from google.genai import types

                    return types.Content(role="model", parts=[])
            except (KeyError, TypeError, ValueError):
                from google.genai import types

                return types.Content(role="model", parts=[])
            return None

        self._callbacks["before_agent_callback"].append(_gate_cb)
        return self

    def loop_until(self, predicate: Callable, *, max_iterations: int = 10) -> BuilderBase:
        """Wrap in a loop that exits when predicate(state) is satisfied.

        Uses ADK's native escalate mechanism via an internal checkpoint agent.

        Usage:
            (writer >> reviewer.outputs("quality")).loop_until(
                lambda s: s.get("quality") == "good", max_iterations=5
            )
        """
        loop = self.__mul__(max_iterations)
        loop._config["_until_predicate"] = predicate
        return loop

    def until(self, predicate: Callable) -> BuilderBase:
        """Set exit predicate on a loop. If not already a Loop, wraps in one.

        Usage:
            Loop("refine").step(writer).step(reviewer).until(lambda s: ...).max_iterations(5)
        """
        from adk_fluent.workflow import Loop

        if isinstance(self, Loop):
            self._config["_until_predicate"] = predicate
            return self
        return self.loop_until(predicate)

    # ------------------------------------------------------------------
    # New Primitives: tap, mock, retry_if, timeout (methods)
    # ------------------------------------------------------------------

    def tap(self, fn: Callable) -> BuilderBase:
        """Append a pure observation step. Reads state, runs side-effect, never mutates.

        .. note:: Returns a new **Pipeline** (self >> tap_step), not self.
           The builder type changes from Agent to Pipeline after this call.

        Usage:
            agent.tap(lambda s: print(s["draft"]))
        """
        return self >> tap(fn)

    def mock(self, responses) -> Self:
        """Replace LLM calls with canned responses for testing.

        Injects a before_model_callback that returns LlmResponse directly,
        bypassing the LLM entirely. Same mechanism as ADK's ReplayPlugin,
        but scoped to this builder instead of globally.

        Args:
            responses: Either a list of response strings (cycles when
                       exhausted), or a callable(llm_request) -> str.

        Usage:
            agent.mock(["Hello!", "World!"])
            agent.mock(lambda req: "Fixed response")
        """
        if callable(responses) and not isinstance(responses, list):
            fn = responses

            def _mock_cb(callback_context, llm_request):
                from google.adk.models.llm_response import LlmResponse
                from google.genai import types

                text = fn(llm_request)
                return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=str(text))]))
        else:
            response_iter = itertools.cycle(responses)

            def _mock_cb(callback_context, llm_request):
                from google.adk.models.llm_response import LlmResponse
                from google.genai import types

                text = next(response_iter)
                return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=str(text))]))

        self._callbacks.setdefault("before_model_callback", []).append(_mock_cb)
        return self

    def loop_while(self, predicate: Callable, *, max_iterations: int = 3) -> BuilderBase:
        """Loop while predicate(state) returns True.

        Wraps in a LoopAgent + checkpoint that exits when the predicate
        becomes False. Natural pair with ``.loop_until()``.

        Args:
            predicate: Receives state dict. Loop continues while True.
            max_iterations: Maximum iterations (default 3).

        Usage:
            agent.loop_while(lambda s: s.get("quality") != "good", max_iterations=3)
        """
        return self.loop_until(lambda s: not predicate(s), max_iterations=max_iterations)

    def timeout(self, seconds: float) -> BuilderBase:
        """Wrap this agent with a time limit. Raises asyncio.TimeoutError if exceeded.

        .. note:: Returns a new **TimedAgent**, not self.
           The builder type changes after this call.

        Usage:
            agent.timeout(30)
        """
        my_name = self._config.get("name", "")
        name = f"{my_name}_timeout_{next(_timeout_counter)}"
        return TimedAgent(name, _agent=self, _seconds=seconds)

    def dispatch(
        self,
        *,
        name: str | None = None,
        on_complete: Callable | None = None,
        on_error: Callable | None = None,
        stream_to: str | None = None,
        progress_key: str | None = None,
    ) -> BuilderBase:
        """Wrap this builder as a background dispatch task.

        Works on ANY builder (Agent, Pipeline, FanOut, Loop).
        Returns a BackgroundTask that fires this builder as a background
        task and continues the pipeline immediately.

        .. note:: Returns a new **BackgroundTask**, not self.

        Args:
            name: Task name for selective join.
            on_complete: Callback ``fn(task_name, result_text)`` on success.
            on_error: Callback ``fn(task_name, exception)`` on failure.
            stream_to: State key for partial result streaming.
            progress_key: Deprecated alias for *stream_to*.

        Usage:
            bg_email = email_agent.dispatch(name="email")
            bg_pipeline = (researcher >> analyzer).dispatch(name="analysis")
            workflow = writer >> bg_email >> bg_pipeline >> join()
        """
        task_name = name or self._config.get("name", f"task_{next(_dispatch_counter)}")
        builder_name = f"dispatch_{task_name}"
        return BackgroundTask(
            builder_name,
            _agents=[self],
            _task_names=(task_name,),
            _on_complete=on_complete,
            _on_error=on_error,
            _stream_to=stream_to or progress_key,
            _max_tasks=None,
        )

    # ------------------------------------------------------------------
    # Task 7: Presets (.use())
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # IR conversion
    # ------------------------------------------------------------------

    def to_ir(self) -> Any:
        """Convert this builder to an IR node.

        Subclasses override to return the appropriate IR node type.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}.to_ir() is not implemented. Use .build() for direct ADK object construction."
        )

    def to_app(self, config=None):
        """Compile this builder through IR to a native ADK App.

        Args:
            config: ExecutionConfig with app_name, resumability, etc.
        Returns:
            A native google.adk App object.
        """
        self._freeze()
        from adk_fluent._ir import ExecutionConfig
        from adk_fluent.backends.adk import ADKBackend

        builder_mw = getattr(self, "_middlewares", [])
        cfg = config or ExecutionConfig()

        # Merge builder middleware + config middleware
        if builder_mw:
            all_mw = tuple(builder_mw) + cfg.middlewares
            cfg = ExecutionConfig(
                app_name=cfg.app_name,
                max_llm_calls=cfg.max_llm_calls,
                timeout_seconds=cfg.timeout_seconds,
                streaming_mode=cfg.streaming_mode,
                resumable=cfg.resumable,
                compaction=cfg.compaction,
                custom_metadata=cfg.custom_metadata,
                middlewares=all_mw,
            )

        try:
            backend = ADKBackend()
            ir = self.to_ir()
            return backend.compile(ir, config=cfg)
        except BuilderError:
            raise
        except Exception as exc:
            name = self._config.get("name", "?")
            raise BuilderError(name, self.__class__.__name__, [str(exc)], exc) from exc

    def middleware(self, mw) -> Self:
        """Attach a middleware to this builder.

        Accepts raw middleware instances or ``MComposite`` chains
        (from ``M.retry(3) | M.log()``).

        Middleware is app-global -- it applies to the entire execution,
        not just this agent. When to_app() is called, all middleware
        from the builder chain is collected and compiled into a plugin.
        """
        from adk_fluent._middleware import MComposite
        from adk_fluent._tools import TComposite

        if isinstance(mw, TComposite):
            raise TypeError(
                "middleware() received a TComposite (tool chain). "
                "Did you mean .tools(...)? Use .middleware() for middleware/MComposite, "
                ".tools() for TComposite."
            )
        if not hasattr(self, "_middlewares"):
            self._middlewares = []
        if isinstance(mw, MComposite):
            self._middlewares.extend(mw.to_stack())
        else:
            self._middlewares.append(mw)
        return self

    def produces(self, schema: type) -> Self:
        """Annotate what state keys this agent writes. Contract-only, no runtime effect.

        Used exclusively by the data-flow contract checker (``.diagnose()``,
        ``.doctor()``, ``check_contracts()``) to verify that downstream
        agents can read what upstream agents produce.

        **This does NOT affect what the LLM outputs.** To constrain the
        LLM's response format, use ``.output(Model)`` or ``@ Model``.

        **When absent:** The contract checker treats this agent's state
        writes as opaque — it cannot verify data-flow correctness for
        downstream consumers. You may see "info" level diagnostics
        suggesting you add type annotations.

        Args:
            schema: A Pydantic BaseModel subclass whose field names correspond
                to the state keys this agent writes via callbacks, tools,
                or output_key.

        Usage::

            class ResearchOutput(BaseModel):
                findings: str
                sources: list[str]

            Agent("researcher").produces(ResearchOutput).writes("findings")
        """
        from pydantic import BaseModel

        if not (isinstance(schema, type) and issubclass(schema, BaseModel)):
            raise TypeError(f"produces() requires a Pydantic BaseModel subclass, got {schema!r}")
        self._config["_produces"] = schema
        return self

    def consumes(self, schema: type) -> Self:
        """Annotate what state keys this agent reads. Contract-only, no runtime effect.

        Used exclusively by the data-flow contract checker to verify that
        required state keys are produced by upstream agents before this
        agent runs.

        **This does NOT affect what context the agent sees.** To control
        what conversation history or state keys are included in the agent's
        prompt, use ``.reads()`` or ``.context()``.

        **When absent:** The contract checker treats this agent's state
        reads as opaque — it cannot verify that required inputs are
        available. Template variables ``{like_this}`` in instructions
        are still checked independently.

        Args:
            schema: A Pydantic BaseModel subclass whose field names correspond
                to the state keys this agent expects to find populated.

        Usage::

            class WriterInput(BaseModel):
                findings: str
                tone: str = "neutral"

            Agent("writer").consumes(WriterInput).reads("findings", "tone")
        """
        from pydantic import BaseModel

        if not (isinstance(schema, type) and issubclass(schema, BaseModel)):
            raise TypeError(f"consumes() requires a Pydantic BaseModel subclass, got {schema!r}")
        self._config["_consumes"] = schema
        return self

    # ------------------------------------------------------------------
    # Interop convenience: .reads(), .writes()
    # ------------------------------------------------------------------

    def reads(self, *keys: str) -> Self:
        """Inject named state keys into this agent's context window.

        At runtime, the values of the specified state keys are prepended to
        the agent's instruction as interpolated text, making them visible
        to the LLM. This is the primary mechanism for data flow in pipelines:
        an upstream agent ``.writes("findings")``, a downstream agent
        ``.reads("findings")``.

        Composes additively: calling ``.reads()`` after ``.context()`` unions
        the specs. Shorthand for ``.context(C.from_state(*keys))``.

        **When NOT set (default):** The agent sees the full conversation
        history (``include_contents="default"``). It does NOT automatically
        see state keys — state values are only visible when explicitly
        requested via ``.reads()``, ``.context(C.from_state(...))``, or
        template variables ``{key}`` in the instruction string.

        Args:
            *keys: State key names to make visible to this agent.

        Usage::

            # These are equivalent:
            Agent("writer").context(C.from_state("topic", "tone"))
            Agent("writer").reads("topic", "tone")

            # Composes with existing context spec:
            Agent("writer").context(C.window(3)).reads("topic")
            # equivalent to: .context(C.window(3) + C.from_state("topic"))

            # Natural pipeline data flow:
            researcher = Agent("researcher").writes("findings")
            writer = Agent("writer").reads("findings").writes("draft")
            pipeline = researcher >> writer
        """
        self = self._maybe_fork_for_mutation()
        from adk_fluent._context import C

        new_spec = C.from_state(*keys)
        existing = self._config.get("_context_spec")
        if existing is not None:
            self._config["_context_spec"] = existing + new_spec
        else:
            self._config["_context_spec"] = new_spec
        return self

    def writes(self, key: str) -> Self:
        """Store this agent's text response in a named state key.

        After the agent runs, its final text response is saved to
        ``session.state[key]``. Downstream agents can then access this
        value via ``.reads(key)`` or template variables ``{key}`` in
        their instructions.

        This is the **primary mechanism for passing data between agents**
        in a pipeline. Without ``.writes()``, the agent's response exists
        only in the conversation history.

        **When NOT set (default):** The agent's response is NOT stored in
        session state. Downstream agents can only see it through
        conversation history (``include_contents="default"``). The
        contract checker will flag this as a potential data-loss issue
        if a downstream agent reads state that no upstream agent writes.

        Equivalent to ``.save_as(key)``.

        Args:
            key: The state key name to store the response text in.

        Usage::

            # Store response in state["findings"]
            Agent("researcher").writes("findings")

            # Downstream agent reads it
            Agent("writer").reads("findings").writes("draft")
        """
        self = self._maybe_fork_for_mutation()
        self._config["output_key"] = key
        return self

    def accepts(self, schema: type) -> Self:
        """Define expected input structure when this agent is used as a tool.

        When another agent invokes this agent via ``AgentTool``, the
        calling agent's arguments are validated against this Pydantic
        model. This is irrelevant for top-level agents — only for
        agents that serve as tools for other agents.

        **When NOT set (default):** No input validation. The agent
        accepts any input when used as a tool.

        Maps to ADK's native ``input_schema`` field.

        Args:
            schema: A Pydantic ``BaseModel`` subclass defining the
                expected input fields.

        Usage::

            class SearchQuery(BaseModel):
                query: str
                max_results: int = 10

            # This agent validates its input when called as a tool
            searcher = Agent("searcher").accepts(SearchQuery).instruct("Search for {query}")
        """
        self = self._maybe_fork_for_mutation()
        self._config["input_schema"] = schema
        return self

    def returns(self, schema: type) -> Self:
        """Constrain the LLM to respond with structured JSON matching a Pydantic model.

        The agent's response MUST conform to this schema. The agent
        **cannot use tools** when this is set (ADK constraint).

        The ``@`` operator is shorthand: ``agent @ MyModel``.

        For ``.ask()`` calls, the response is automatically parsed into
        a ``schema`` instance.

        **Distinction from similar methods:**

        - ``.returns(Model)`` — LLM response SHAPE (this method)
        - ``.writes(key)``    — WHERE response is STORED in state
        - ``.produces(Model)``— ANNOTATION for contract checker (no runtime effect)
        - ``.accepts(Model)`` — INPUT validation for tool-mode agents

        **When NOT set (default):** Agent responds in plain text and
        CAN use tools.

        Args:
            schema: A Pydantic ``BaseModel`` subclass that the LLM
                must conform to.

        Usage::

            class Intent(BaseModel):
                category: str
                confidence: float

            # LLM must respond with Intent JSON
            classifier = Agent("classifier").returns(Intent).writes("intent")
        """
        self = self._maybe_fork_for_mutation()
        self._config["_output_schema"] = schema
        return self

    def inject(self, **resources: Any) -> Self:
        """Inject named resources into tool function parameters (dependency injection).

        At build time, tools whose signatures have parameters matching
        the resource names will have those parameters auto-filled and
        hidden from the LLM tool schema. Use for DB clients, API keys,
        config objects — anything the LLM should never see or control.

        Usage:
            agent.inject(db=my_database, api_key=secret)
        """
        existing = self._config.setdefault("_resources", {})
        existing.update(resources)
        return self

    def to_mermaid(
        self,
        *,
        show_contracts: bool = True,
        show_data_flow: bool = True,
        show_context: bool = False,
    ) -> str:
        """Generate a Mermaid graph visualization of this builder's IR tree.

        Args:
            show_contracts: Include produces/consumes type annotations.
            show_data_flow: Include dotted edges showing state key flow.
            show_context: Include context strategy annotations per agent.
        """
        from adk_fluent.viz import ir_to_mermaid

        return ir_to_mermaid(
            self.to_ir(),
            show_contracts=show_contracts,
            show_data_flow=show_data_flow,
            show_context=show_context,
        )

    def to_sequence_diagram(
        self,
        *,
        show_data_flow: bool = True,
        show_context: bool = True,
    ) -> str:
        """Generate a Mermaid sequence diagram of this builder's execution flow.

        Unlike ``to_mermaid()`` which shows topology (what connects to what),
        this shows *execution order* — what calls what, when, and what data
        moves where.  Parallel branches use ``par`` blocks, loops use ``loop``
        blocks, and routing uses ``alt`` blocks.

        Args:
            show_data_flow: Annotate state key writes as messages.
            show_context: Add notes showing each agent's context strategy.
        """
        from adk_fluent.viz import ir_to_sequence_diagram

        return ir_to_sequence_diagram(
            self.to_ir(),
            show_data_flow=show_data_flow,
            show_context=show_context,
        )

    def diagnose(self):
        """Return a structured Diagnosis of this builder's IR.

        Returns a ``Diagnosis`` dataclass with ``agents``, ``data_flow``,
        ``issues``, and ``topology`` fields.  Use ``.ok`` to check if
        there are no errors.  Use ``.doctor()`` for a formatted report.

        Raises NotImplementedError if this builder doesn't support IR.
        """
        from adk_fluent.testing.diagnosis import diagnose as _diagnose

        return _diagnose(self.to_ir())

    def doctor(self) -> str:
        """Print a formatted diagnostic report and return the report text.

        Combines agent summaries, data flow analysis, contract issues,
        and Mermaid topology into a single readable report.
        """
        from adk_fluent.testing.diagnosis import diagnose as _diagnose
        from adk_fluent.testing.diagnosis import format_diagnosis

        diag = _diagnose(self.to_ir())
        report = format_diagnosis(diag)
        print(report)
        return report

    def data_flow(self):
        """Show all five data-flow concerns at once for this builder.

        Returns a ``DataFlow`` snapshot showing exactly what this agent
        is configured for across all five orthogonal concerns:

        - **Context** (reads): what state/history the agent sees
        - **Input** (accepts): what input schema is validated in tool mode
        - **Output** (returns): plain text or structured JSON
        - **Storage** (writes): where the response is saved in state
        - **Contract** (produces/consumes): annotations for the checker

        This is the definitive way to understand what an agent does with
        data — it surfaces all five concerns in one view, eliminating
        confusion between ``.returns()``, ``.writes()``, ``.produces()``, etc.

        Usage::

            agent = Agent("classifier").reads("query").returns(Intent).writes("intent")
            print(agent.data_flow())
            # Data Flow:
            #   reads:    C.from_state('query') — state keys only
            #   accepts:  (not set — accepts any input as tool)
            #   returns:  structured JSON → Intent (tools disabled)
            #   writes:   state['intent']
            #   contract: (not set)
        """
        from adk_fluent._interop import _extract_data_flow

        return _extract_data_flow(self)

    def llm_anatomy(self) -> str:
        """Show exactly what will be sent to the LLM for this agent.

        Returns a formatted string showing each component in the order
        it is assembled for the LLM call:

        1. **System** — instruction text (with {template} variables)
        2. **History** — whether conversation history is included
        3. **Context** — injected state values from ``.reads()``
        4. **Tools** — registered tools (disabled if output_schema set)
        5. **Constraint** — output schema (forces JSON response)
        6. **After** — what happens after the LLM responds

        This is the definitive reference for "what does the LLM see?"

        Usage::

            agent = Agent("classifier").instruct("Classify: {query}").reads("query").returns(Intent)
            print(agent.llm_anatomy())
            # LLM Call Anatomy: classifier
            #   1. System:     "Classify: {query}"
            #                  → {query} templated from state at runtime
            #   2. History:    SUPPRESSED (set by .reads())
            #   3. Context:    state["query"] injected as <conversation_context>
            #   4. Tools:      DISABLED (output_schema is set)
            #   5. Constraint: must return Intent {category: ..., confidence: ...}
            #   6. After:      response in conversation history only
        """
        from adk_fluent._interop import _build_llm_anatomy

        return _build_llm_anatomy(self)

    def strict(self) -> Self:
        """Enable strict contract checking — build() raises ValueError on contract errors."""
        self._config["_check_mode"] = "strict"
        return self

    def unchecked(self) -> Self:
        """Disable contract checking on build()."""
        self._config["_check_mode"] = False
        return self

    def _run_build_contracts(self) -> None:
        """Run IR-first contract checking if this builder has to_ir().

        Per appendix_f Q1: .build() internally uses IR.
        Per appendix_f Q3: Contract checking is default, not opt-in.

        Also runs output method interop checks to catch common confusion
        patterns (e.g., .produces() without .writes(), conflicting schemas).

        Modes (controlled by _check_mode config):
          True (default) — run contracts, log advisory diagnostics
          "strict"       — raise ValueError on any contract error
          False          — skip contract checking entirely
        """
        check_mode = self._config.get("_check_mode", True)
        if check_mode is False:
            return

        # ── Output interop checks (runs on all builders) ──
        from adk_fluent._interop import check_output_interop

        interop_issues = check_output_interop(self._config)

        # ── IR contract checks (runs on compound builders only) ──
        ir_issues: list = []
        if hasattr(self, "to_ir"):
            try:
                ir = self.to_ir()
                from adk_fluent.testing.contracts import check_contracts

                ir_issues = check_contracts(ir)
            except Exception:
                pass  # IR conversion failed — skip contracts silently

        all_issues = interop_issues + ir_issues
        if not all_issues:
            return

        errors = [i for i in all_issues if isinstance(i, dict) and i.get("level") in ("error", "warning")]

        if check_mode == "strict" and errors:
            msg = "\n".join(f"  {i['agent']}: {i['message']}" for i in errors)
            raise ValueError(f"Contract errors in pipeline:\n{msg}")

        # Advisory mode: log warnings
        if errors:
            import logging

            logger = logging.getLogger("adk_fluent.contracts")
            for issue in errors:
                logger.warning(
                    "Contract issue [%s] %s: %s",
                    issue.get("level", "?"),
                    issue.get("agent", "?"),
                    issue.get("message", "?"),
                )

    def use(self, preset: Any) -> Self:
        """Apply a Preset object that bundles multiple builder settings (model, instruction, tools, callbacks, etc.) onto this builder. Presets are reusable configuration bundles."""
        aliases = getattr(self.__class__, "_ALIASES", {})
        cb_aliases = getattr(self.__class__, "_CALLBACK_ALIASES", {})

        # Apply preset fields
        for key, value in preset._fields.items():
            field_name = aliases.get(key, key)
            self._config[field_name] = value

        # Apply preset callbacks
        for key, fns in preset._callbacks.items():
            # Resolve through callback aliases
            cb_field = cb_aliases.get(key, key)
            for fn in fns:
                self._callbacks[cb_field].append(fn)

        return self

    # ------------------------------------------------------------------
    # Pipeline-level visibility policies
    # ------------------------------------------------------------------

    def transparent(self) -> Self:
        """All agents visible regardless of position. For debugging/demos."""
        self._config["_visibility_policy"] = "transparent"
        return self

    def filtered(self) -> Self:
        """Only terminal agents visible. Topology-inferred (default)."""
        self._config["_visibility_policy"] = "filtered"
        return self

    def annotated(self) -> Self:
        """All events reach client with visibility metadata. Client filters."""
        self._config["_visibility_policy"] = "annotate"
        return self


# ======================================================================
# Re-exports from _primitive_builders (builders, factory functions)
# ======================================================================
from adk_fluent._primitive_builders import (
    PrimitiveBuilderBase as PrimitiveBuilderBase,
    _CaptureBuilder as _CaptureBuilder,
    BackgroundTask as BackgroundTask,
    _FallbackBuilder as _FallbackBuilder,
    _FnStepBuilder as _FnStepBuilder,
    _GateBuilder as _GateBuilder,
    _JoinBuilder as _JoinBuilder,
    _MapOverBuilder as _MapOverBuilder,
    _RaceBuilder as _RaceBuilder,
    _TapBuilder as _TapBuilder,
    TimedAgent as TimedAgent,
    _dispatch_counter as _dispatch_counter,
    _expect_counter as _expect_counter,
    _fn_step as _fn_step,
    _fn_step_counter as _fn_step_counter,
    _gate_counter as _gate_counter,
    _join_counter as _join_counter,
    _map_over_counter as _map_over_counter,
    _tap_counter as _tap_counter,
    _timeout_counter as _timeout_counter,
    dispatch as dispatch,
    expect as expect,
    gate as gate,
    join as join,
    map_over as map_over,
    race as race,
    tap as tap,
)
