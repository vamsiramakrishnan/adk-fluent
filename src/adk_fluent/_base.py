"""BuilderBase mixin -- shared capabilities for all generated fluent builders."""

from __future__ import annotations

import asyncio as _asyncio
import itertools
import types
from collections.abc import Callable
from typing import Any, Self

from google.adk.agents.base_agent import BaseAgent

__all__ = [
    "BuilderError",
    "until",
    "tap",
    "expect",
    "map_over",
    "gate",
    "race",
    "FnAgent",
    "TapAgent",
    "CaptureAgent",
    "FallbackAgent",
    "MapOverAgent",
    "TimeoutAgent",
    "GateAgent",
    "RaceAgent",
]


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


def _compose_callbacks(fns: list[Callable]) -> Callable:
    """Chain multiple callbacks into a single callable.

    Each runs in order. First non-None return value wins (short-circuit).
    Handles both sync and async callbacks.
    """
    if not fns:
        raise ValueError("_compose_callbacks requires at least one callback")
    if len(fns) == 1:
        return fns[0]

    async def _composed(*args, **kwargs):
        for fn in fns:
            result = fn(*args, **kwargs)
            if _asyncio.iscoroutine(result) or _asyncio.isfuture(result):
                result = await result
            if result is not None:
                return result
        return None

    _composed.__name__ = f"composed_{'_'.join(getattr(f, '__name__', '?') for f in fns)}"
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


class BuilderError(Exception):
    """Raised when a builder fails to construct a valid ADK object.

    Provides a clear, concise error message instead of raw pydantic tracebacks.
    """

    def __init__(self, builder_name: str, builder_type: str, field_errors: list[str], original: Exception):
        self.builder_name = builder_name
        self.builder_type = builder_type
        self.field_errors = field_errors
        self.original = original
        lines = [f"Failed to build {builder_type}('{builder_name}'):"]
        for err in field_errors:
            lines.append(f"  - {err}")
        super().__init__("\n".join(lines))


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

    def _fork_for_operator(self) -> BuilderBase:
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
                    "Left side of >> dict must have .outputs() or .output_key() set "
                    "so the router knows which state key to check."
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
            clone.step(other)
            clone._config["name"] = f"{my_name}_then_{other_name}"
            result = clone
        else:
            name = f"{my_name}_then_{other_name}"
            p = Pipeline(name)
            p.step(self)
            p.step(other)
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
            clone.branch(other)
            clone._config["name"] = f"{my_name}_and_{other_name}"
            result = clone
        else:
            name = f"{my_name}_and_{other_name}"
            f = FanOut(name)
            f.branch(self)
            f.branch(other)
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
            loop.step(self)
        return loop

    def __rmul__(self, iterations: int) -> BuilderBase:
        """Support int * agent syntax."""
        return self.__mul__(iterations)

    def __matmul__(self, schema: type) -> BuilderBase:
        """Bind a Pydantic model as the typed output contract: agent @ Schema.

        Expression-language shorthand for .output_schema(Schema).
        Prefer .output_schema() in explicit builder chains; use @ in
        operator expressions where brevity matters.
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
        children = []
        if isinstance(self, _FallbackBuilder):
            children.extend(self._children)
        else:
            children.append(self)
        if isinstance(other, _FallbackBuilder):
            children.extend(other._children)
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
        """Register a post-build hook to access raw ADK objects."""
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

        # Data flow: reads and writes
        produces_schema = self._config.get("_produces")
        consumes_schema = self._config.get("_consumes")
        output_key = self._config.get("output_key")

        reads_parts = []
        if consumes_schema:
            fields = list(consumes_schema.model_fields.keys())
            reads_parts.append(f"consumes {consumes_schema.__name__}({', '.join(fields)})")
        if reads_parts:
            lines.append(f"  Reads: {'; '.join(reads_parts)}")

        writes_parts = []
        if produces_schema:
            fields = list(produces_schema.model_fields.keys())
            writes_parts.append(f"produces {produces_schema.__name__}({', '.join(fields)})")
        if output_key:
            writes_parts.append(f"output_key='{output_key}'")
        if writes_parts:
            lines.append(f"  Writes: {'; '.join(writes_parts)}")

        if not reads_parts and not writes_parts and not output_key:
            lines.append("  Data flow: no explicit reads/writes declared")

        # Context strategy
        context_spec = self._config.get("_context_spec")
        include_contents = self._config.get("include_contents", "default")
        if context_spec is not None:
            from adk_fluent.testing.contracts import _context_description

            lines.append(f"  Context: {_context_description(context_spec)}")
        elif include_contents != "default":
            lines.append(f"  Context: include_contents='{include_contents}'")

        # Output schema
        output_schema = self._config.get("_output_schema")
        if output_schema:
            lines.append(f"  Structured output: {output_schema.__name__}")

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

        from rich.tree import Tree

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

        # Data flow
        produces_schema = self._config.get("_produces")
        consumes_schema = self._config.get("_consumes")
        output_key = self._config.get("output_key")

        reads_parts = []
        if consumes_schema:
            fields = list(consumes_schema.model_fields.keys())
            reads_parts.append(f"consumes {consumes_schema.__name__}({', '.join(fields)})")
        if reads_parts:
            tree.add(f"[blue]Reads[/blue]: {'; '.join(reads_parts)}")

        writes_parts = []
        if produces_schema:
            fields = list(produces_schema.model_fields.keys())
            writes_parts.append(f"produces {produces_schema.__name__}({', '.join(fields)})")
        if output_key:
            writes_parts.append(f"output_key='{output_key}'")
        if writes_parts:
            tree.add(f"[blue]Writes[/blue]: {'; '.join(writes_parts)}")

        if not reads_parts and not writes_parts and not output_key:
            tree.add("[dim]Data flow: no explicit reads/writes declared[/dim]")

        # Context strategy
        context_spec = self._config.get("_context_spec")
        include_contents = self._config.get("include_contents", "default")
        if context_spec is not None:
            from adk_fluent.testing.contracts import _context_description

            tree.add(f"[magenta]Context[/magenta]: {_context_description(context_spec)}")
        elif include_contents != "default":
            tree.add(f"[magenta]Context[/magenta]: include_contents='{include_contents}'")

        # Structured output
        output_schema = self._config.get("_output_schema")
        if output_schema:
            tree.add(f"[cyan]Structured output[/cyan]: {output_schema.__name__}")

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
        _shown = {"name", "model", "instruction", "_produces", "_consumes", "output_key",
                   "_context_spec", "include_contents", "_output_schema", "tools"}
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

    def explain(self) -> str:
        """Return a multi-line summary of this builder's state.

        Uses rich box-drawing output if ``rich`` is installed, otherwise
        falls back to plain text.
        """
        try:
            from rich.console import Console

            tree = self._build_rich_tree()
            console = Console(record=True, width=120)
            console.print(tree)
            return console.export_text()
        except ImportError:
            return self._explain_plain()

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

        # Auto-convert Prompt objects to strings
        from adk_fluent._prompt import Prompt

        for key, value in list(config.items()):
            if isinstance(value, Prompt):
                config[key] = str(value)

        # Auto-build any BuilderBase values in config
        for key, value in list(config.items()):
            if isinstance(value, BuilderBase):
                config[key] = value.build()

        # Merge accumulated callbacks
        for field, fns in self._callbacks.items():
            if fns:
                config[field] = _compose_callbacks(list(fns))

        # Merge accumulated lists (auto-building items)
        for field, items in self._lists.items():
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
            from adk_fluent._context import CTransform, _compile_context_spec

            if isinstance(context_spec, CTransform):
                compiled = _compile_context_spec(
                    developer_instruction=config.get("instruction", ""),
                    context_spec=context_spec,
                )
                config["include_contents"] = compiled["include_contents"]
                if compiled.get("instruction") is not None:
                    config["instruction"] = compiled["instruction"]

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
        """Set a Pydantic model as the output schema."""
        self._config["_output_schema"] = schema
        return self

    # ------------------------------------------------------------------
    # Task 10: Retry and Fallback
    # ------------------------------------------------------------------

    def retry(self, max_attempts: int = 3, backoff: float = 1.0) -> Self:
        """Configure retry behavior with exponential backoff."""
        self._config["_retry"] = {"max_attempts": max_attempts, "backoff": backoff}
        return self

    def fallback(self, model: str) -> Self:
        """Add a fallback model to try if primary fails."""
        self._config.setdefault("_fallbacks", []).append(model)
        return self

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

    def inject_context(self, fn: Callable) -> Self:
        """Prepend dynamic context to the prompt via before_model_callback.

        The function receives the callback context and returns a string.
        That string is prepended as a system-level content part before
        the LLM processes the request.

        Usage:
            agent.inject_context(lambda ctx: f"User: {ctx.state.get('user')}")
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

    def until(self, predicate: Callable) -> Self:
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

    def retry_if(self, predicate: Callable, *, max_retries: int = 3) -> BuilderBase:
        """Retry agent execution while predicate(state) returns True.

        Wraps in a LoopAgent + checkpoint that exits when the predicate
        becomes False. Thin wrapper over loop_until() with inverted predicate.

        Args:
            predicate: Receives state dict. Retry while this returns True.
            max_retries: Maximum number of retries (default 3).

        Usage:
            agent.retry_if(lambda s: s.get("quality") != "good", max_retries=3)
        """
        return self.loop_until(lambda s: not predicate(s), max_iterations=max_retries)

    def timeout(self, seconds: float) -> BuilderBase:
        """Wrap this agent with a time limit. Raises asyncio.TimeoutError if exceeded.

        .. note:: Returns a new **_TimeoutBuilder**, not self.
           The builder type changes after this call.

        Usage:
            agent.timeout(30)
        """
        my_name = self._config.get("name", "")
        name = f"{my_name}_timeout_{next(_timeout_counter)}"
        return _TimeoutBuilder(name, self, seconds)

    # ------------------------------------------------------------------
    # Task 7: Presets (.use())
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # IR conversion
    # ------------------------------------------------------------------

    def to_ir(self):
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

        Middleware is app-global -- it applies to the entire execution,
        not just this agent. When to_app() is called, all middleware
        from the builder chain is collected and compiled into a plugin.
        """
        if not hasattr(self, "_middlewares"):
            self._middlewares = []
        self._middlewares.append(mw)
        return self

    def produces(self, schema: type) -> Self:
        """Declare the Pydantic schema this agent writes to state."""
        from pydantic import BaseModel

        if not (isinstance(schema, type) and issubclass(schema, BaseModel)):
            raise TypeError(f"produces() requires a Pydantic BaseModel subclass, got {schema!r}")
        self._config["_produces"] = schema
        return self

    def consumes(self, schema: type) -> Self:
        """Declare the Pydantic schema this agent reads from state."""
        from pydantic import BaseModel

        if not (isinstance(schema, type) and issubclass(schema, BaseModel)):
            raise TypeError(f"consumes() requires a Pydantic BaseModel subclass, got {schema!r}")
        self._config["_consumes"] = schema
        return self

    def inject(self, **resources: Any) -> Self:
        """Register resources for dependency injection into tool functions.

        At build time, tools with matching parameter names will have
        those parameters injected and hidden from the LLM schema.
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

        Modes (controlled by _check_mode config):
          True (default) — run contracts, log advisory diagnostics
          "strict"       — raise ValueError on any contract error
          False          — skip contract checking entirely
        """
        check_mode = self._config.get("_check_mode", True)
        if check_mode is False:
            return

        # Only run contracts on compound builders that have to_ir
        if not hasattr(self, "to_ir"):
            return

        try:
            ir = self.to_ir()
        except Exception:
            return  # IR conversion failed — skip contracts silently

        from adk_fluent.testing.contracts import check_contracts

        issues = check_contracts(ir)
        if not issues:
            return

        errors = [i for i in issues if isinstance(i, dict) and i.get("level") == "error"]

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
        """Apply a Preset's fields and callbacks to this builder. Returns self."""
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
# Post-BuilderBase primitives (depend on BuilderBase)
# ======================================================================

_fn_step_counter = itertools.count(1)


def _fn_step(fn: Callable) -> BuilderBase:
    """Wrap a pure function as a zero-cost workflow step.

    The function receives a dict (snapshot of session state) and returns
    a dict of updates to merge back into state:

        def trim(state):
            return {"summary": state["findings"][:500]}

    If the function returns None, it is assumed to have no state updates.
    """
    capture_key = getattr(fn, "_capture_key", None)
    if capture_key is not None:
        name = getattr(fn, "__name__", f"capture_{capture_key}")
        if not name.isidentifier():
            name = f"capture_{capture_key}"
        return _CaptureBuilder(name, capture_key)

    name = getattr(fn, "__name__", "_transform")
    # Sanitize: ADK requires valid Python identifiers for agent names
    if not name.isidentifier():
        name = f"fn_step_{next(_fn_step_counter)}"

    builder = _FnStepBuilder(fn, name)
    return builder


class _FnStepBuilder(BuilderBase):
    """Builder wrapper for a pure function in the expression language."""

    _ALIASES: dict[str, str] = {}
    _CALLBACK_ALIASES: dict[str, str] = {}
    _ADDITIVE_FIELDS: set[str] = set()

    def __init__(self, fn_ref: Callable, step_name: str):
        self._config: dict[str, Any] = {"name": step_name}
        self._callbacks: dict[str, list] = {}
        self._lists: dict[str, list] = {}
        self._fn = fn_ref

    def _fork_for_operator(self) -> BuilderBase:
        clone = super()._fork_for_operator()
        clone._fn = self._fn
        return clone

    def build(self):
        return FnAgent(name=self._config["name"], fn=self._fn)

    def to_ir(self):
        from adk_fluent._ir import TransformNode

        # Extract read/write metadata from annotated S.* callables
        writes = getattr(self._fn, "_writes_keys", None)
        reads = getattr(self._fn, "_reads_keys", None)

        return TransformNode(
            name=self._config.get("name", "fn_step"),
            fn=self._fn,
            semantics="merge",
            affected_keys=writes,
            reads_keys=reads,
        )


class _CaptureBuilder(BuilderBase):
    """Builder wrapper for S.capture() in the expression language."""

    _ALIASES: dict[str, str] = {}
    _CALLBACK_ALIASES: dict[str, str] = {}
    _ADDITIVE_FIELDS: set[str] = set()

    def __init__(self, step_name: str, capture_key: str):
        self._config: dict[str, Any] = {"name": step_name}
        self._callbacks: dict[str, list] = {}
        self._lists: dict[str, list] = {}
        self._capture_key = capture_key

    def _fork_for_operator(self) -> BuilderBase:
        clone = super()._fork_for_operator()
        clone._capture_key = self._capture_key
        return clone

    def build(self):
        return CaptureAgent(name=self._config["name"], key=self._capture_key)

    def to_ir(self):
        from adk_fluent._ir import CaptureNode

        return CaptureNode(
            name=self._config.get("name", "capture"),
            key=self._capture_key,
        )


class _FallbackBuilder(BuilderBase):
    """Builder for a fallback chain: a // b // c.

    Tries each child in order. First success wins.
    """

    _ALIASES: dict[str, str] = {}
    _CALLBACK_ALIASES: dict[str, str] = {}
    _ADDITIVE_FIELDS: set[str] = set()

    def __init__(self, name: str, children: list):
        self._config: dict[str, Any] = {"name": name}
        self._callbacks: dict[str, list] = {}
        self._lists: dict[str, list] = {}
        self._children = children

    def _fork_for_operator(self) -> BuilderBase:
        clone = super()._fork_for_operator()
        clone._children = list(self._children)
        return clone

    def build(self):
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
    return _TapBuilder(fn, name)


class _TapBuilder(BuilderBase):
    """Builder for a pure observation step. No state mutation, no LLM."""

    _ALIASES: dict[str, str] = {}
    _CALLBACK_ALIASES: dict[str, str] = {}
    _ADDITIVE_FIELDS: set[str] = set()

    def __init__(self, fn_ref: Callable, step_name: str):
        self._config: dict[str, Any] = {"name": step_name}
        self._callbacks: dict[str, list] = {}
        self._lists: dict[str, list] = {}
        self._fn = fn_ref

    def _fork_for_operator(self) -> BuilderBase:
        clone = super()._fork_for_operator()
        clone._fn = self._fn
        return clone

    def build(self):
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
    return _FnStepBuilder(_assert_fn, name)


# ======================================================================
# Primitive: map_over (iterate agent over list items)
# ======================================================================

_map_over_counter = itertools.count(1)


def map_over(key: str, agent, *, item_key: str = "_item", output_key: str = "summaries") -> BuilderBase:
    """Iterate over a list in session state, running an agent for each item.

    For each item in state[key], sets state[item_key] = item, runs the agent,
    and collects results into state[output_key].

    Usage:
        map_over("items", summarizer, output_key="summaries")
    """
    name = f"map_over_{key}_{next(_map_over_counter)}"
    return _MapOverBuilder(name, agent, key, item_key, output_key)


class _MapOverBuilder(BuilderBase):
    """Builder for iterating an agent over list items in state."""

    _ALIASES: dict[str, str] = {}
    _CALLBACK_ALIASES: dict[str, str] = {}
    _ADDITIVE_FIELDS: set[str] = set()

    def __init__(self, name: str, agent, list_key: str, item_key: str, output_key: str):
        self._config: dict[str, Any] = {"name": name}
        self._callbacks: dict[str, list] = {}
        self._lists: dict[str, list] = {}
        self._agent = agent
        self._list_key = list_key
        self._item_key = item_key
        self._output_key = output_key

    def _fork_for_operator(self) -> BuilderBase:
        clone = super()._fork_for_operator()
        clone._agent = self._agent
        clone._list_key = self._list_key
        clone._item_key = self._item_key
        clone._output_key = self._output_key
        return clone

    def build(self):
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


class _TimeoutBuilder(BuilderBase):
    """Builder that wraps an agent with a time limit."""

    _ALIASES: dict[str, str] = {}
    _CALLBACK_ALIASES: dict[str, str] = {}
    _ADDITIVE_FIELDS: set[str] = set()

    def __init__(self, name: str, agent, seconds: float):
        self._config: dict[str, Any] = {"name": name}
        self._callbacks: dict[str, list] = {}
        self._lists: dict[str, list] = {}
        self._agent = agent
        self._seconds = seconds

    def _fork_for_operator(self) -> BuilderBase:
        clone = super()._fork_for_operator()
        clone._agent = self._agent
        clone._seconds = self._seconds
        return clone

    def build(self):
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

    When predicate(state) is True, pauses the pipeline by escalating.
    Sets state flags so the outer runner knows approval is pending.
    On re-run with state[gate_key + '_approved'] = True, proceeds.

    Usage:
        gate(lambda s: s.get("risk") == "high", message="Approve high-risk action?")
    """
    name = f"gate_{next(_gate_counter)}"
    if gate_key is None:
        gate_key = f"_{name}"
    return _GateBuilder(name, predicate, message, gate_key)


class _GateBuilder(BuilderBase):
    """Builder for a human-in-the-loop approval gate."""

    _ALIASES: dict[str, str] = {}
    _CALLBACK_ALIASES: dict[str, str] = {}
    _ADDITIVE_FIELDS: set[str] = set()

    def __init__(self, name: str, predicate: Callable, message: str, gate_key: str):
        self._config: dict[str, Any] = {"name": name}
        self._callbacks: dict[str, list] = {}
        self._lists: dict[str, list] = {}
        self._predicate = predicate
        self._message = message
        self._gate_key = gate_key

    def _fork_for_operator(self) -> BuilderBase:
        clone = super()._fork_for_operator()
        clone._predicate = self._predicate
        clone._message = self._message
        clone._gate_key = self._gate_key
        return clone

    def build(self):
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
    return _RaceBuilder(name, list(agents))


class _RaceBuilder(BuilderBase):
    """Builder for a race: first sub-agent to finish wins."""

    _ALIASES: dict[str, str] = {}
    _CALLBACK_ALIASES: dict[str, str] = {}
    _ADDITIVE_FIELDS: set[str] = set()

    def __init__(self, name: str, agents: list):
        self._config: dict[str, Any] = {"name": name}
        self._callbacks: dict[str, list] = {}
        self._lists: dict[str, list] = {}
        self._agents = agents

    def _fork_for_operator(self) -> BuilderBase:
        clone = super()._fork_for_operator()
        clone._agents = list(self._agents)
        return clone

    def build(self):
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
# Module-level agent classes (hoisted from inner build() definitions)
#
# These were previously defined inside each builder's build() method,
# which created a new type object on every call. Hoisting them to
# module level ensures:
#   - type(a1) is type(a2) across builds
#   - isinstance checks work correctly
#   - No closure-based memory leaks in loops
#
# Because BaseAgent is a Pydantic BaseModel, extra constructor params
# are rejected. We use object.__setattr__() after super().__init__()
# to attach behavioral attributes as private instance attrs.
# ======================================================================


class FnAgent(BaseAgent):
    """Zero-cost function agent. No LLM call."""

    def __init__(self, *, fn: Callable, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, "_fn_ref", fn)

    async def _run_async_impl(self, ctx):
        from adk_fluent._transforms import _SCOPE_PREFIXES, StateDelta, StateReplacement

        result = self._fn_ref(dict(ctx.session.state))
        if isinstance(result, StateReplacement):
            # Only affect session-scoped (unprefixed) keys
            current_session_keys = {k for k in ctx.session.state if not k.startswith(_SCOPE_PREFIXES)}
            new_keys = set(result.new_state.keys())
            for k, v in result.new_state.items():
                ctx.session.state[k] = v
            for k in current_session_keys - new_keys:
                ctx.session.state[k] = None
        elif isinstance(result, StateDelta):
            for k, v in result.updates.items():
                ctx.session.state[k] = v
        elif isinstance(result, dict):
            for k, v in result.items():
                ctx.session.state[k] = v
        # yield nothing — pure transform, no events


class FallbackAgent(BaseAgent):
    """Tries each child agent in order. First success wins."""

    async def _run_async_impl(self, ctx):
        last_exc = None
        for child in self.sub_agents:
            try:
                async for event in child.run_async(ctx):
                    yield event
                return  # success — stop trying
            except Exception as exc:
                last_exc = exc
                continue
        if last_exc is not None:
            raise last_exc


class TapAgent(BaseAgent):
    """Zero-cost observation agent. No LLM call, no state mutation."""

    def __init__(self, *, fn: Callable, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, "_fn_ref", fn)

    async def _run_async_impl(self, ctx):
        # Pass read-only view — tap should never mutate state
        self._fn_ref(types.MappingProxyType(dict(ctx.session.state)))
        # Explicitly yield nothing — pure observation


class CaptureAgent(BaseAgent):
    """Capture the most recent user message from session events into state."""

    def __init__(self, *, key: str, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, "_capture_key", key)

    async def _run_async_impl(self, ctx):
        for event in reversed(ctx.session.events):
            if getattr(event, "author", None) == "user":
                parts = getattr(getattr(event, "content", None), "parts", None) or []
                texts = [getattr(p, "text", "") for p in parts if getattr(p, "text", None)]
                if texts:
                    ctx.session.state[self._capture_key] = "\n".join(texts)
                    break
        # yield nothing — pure capture, no events


class MapOverAgent(BaseAgent):
    """Iterates sub-agent over each item in a state list."""

    def __init__(self, *, list_key: str, item_key: str, output_key: str, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, "_list_key", list_key)
        object.__setattr__(self, "_item_key", item_key)
        object.__setattr__(self, "_output_key", output_key)

    async def _run_async_impl(self, ctx):
        items = ctx.session.state.get(self._list_key, [])
        results = []
        for item in items:
            ctx.session.state[self._item_key] = item
            async for event in self.sub_agents[0].run_async(ctx):
                yield event
            # Collect result after sub-agent runs
            result_val = ctx.session.state.get(self._item_key, None)
            results.append(result_val)
        ctx.session.state[self._output_key] = results


class TimeoutAgent(BaseAgent):
    """Wraps a sub-agent with a time limit."""

    def __init__(self, *, seconds: float, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, "_seconds", seconds)

    async def _run_async_impl(self, ctx):
        import asyncio

        queue = asyncio.Queue()
        sentinel = object()

        async def _consume():
            async for event in self.sub_agents[0].run_async(ctx):
                await queue.put(event)
            await queue.put(sentinel)

        task = asyncio.create_task(_consume())
        try:
            deadline = asyncio.get_event_loop().time() + self._seconds
            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    raise TimeoutError(f"Agent '{self.sub_agents[0].name}' exceeded {self._seconds}s timeout")
                item = await asyncio.wait_for(queue.get(), timeout=remaining)
                if item is sentinel:
                    break
                yield item
        except TimeoutError:
            task.cancel()
            raise
        finally:
            if not task.done():
                task.cancel()


class GateAgent(BaseAgent):
    """Human-in-the-loop approval gate."""

    def __init__(self, *, predicate: Callable, message: str, gate_key: str, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, "_predicate", predicate)
        object.__setattr__(self, "_message", message)
        object.__setattr__(self, "_gate_key", gate_key)

    async def _run_async_impl(self, ctx):
        from google.adk.events.event import Event
        from google.adk.events.event_actions import EventActions
        from google.genai import types

        state = ctx.session.state
        approved_key = f"{self._gate_key}_approved"

        try:
            needs_gate = self._predicate(state)
        except (KeyError, TypeError, ValueError):
            needs_gate = False

        if not needs_gate:
            return  # Condition not met, proceed

        if state.get(approved_key):
            # Already approved, clear and proceed
            state[approved_key] = False
            state[self._gate_key] = False
            return

        # Need approval: set flag and escalate
        state[self._gate_key] = True
        state[f"{self._gate_key}_message"] = self._message
        yield Event(
            invocation_id=ctx.invocation_id,
            author=self.name,
            branch=ctx.branch,
            content=types.Content(role="model", parts=[types.Part(text=self._message)]),
            actions=EventActions(escalate=True),
        )


class RaceAgent(BaseAgent):
    """Runs sub-agents concurrently, keeps first to finish."""

    async def _run_async_impl(self, ctx):
        import asyncio

        async def _run_one(agent):
            events = []
            async for event in agent.run_async(ctx):
                events.append(event)
            return events

        tasks = {asyncio.create_task(_run_one(agent)): i for i, agent in enumerate(self.sub_agents)}

        try:
            done, pending = await asyncio.wait(tasks.keys(), return_when=asyncio.FIRST_COMPLETED)
            # Cancel remaining
            for task in pending:
                task.cancel()

            # Yield events from the winner
            winner = done.pop()
            for event in winner.result():
                yield event
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
