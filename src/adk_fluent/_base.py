"""BuilderBase mixin -- shared capabilities for all generated fluent builders."""
from __future__ import annotations
from typing import Any, Callable, Self

__all__ = ["until"]


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


class BuilderBase:
    """Mixin base class providing shared builder capabilities.

    All generated builders inherit from this class.
    """
    _ALIASES: dict[str, str]
    _CALLBACK_ALIASES: dict[str, str]
    _ADDITIVE_FIELDS: set[str]

    # ------------------------------------------------------------------
    # Task 2: __repr__
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

    def _clone_shallow(self) -> BuilderBase:
        """Shallow-clone this builder for immutable operator results."""
        import copy
        new = object.__new__(type(self))
        new._config = dict(self._config)
        new._callbacks = {k: list(v) for k, v in self._callbacks.items()}
        new._lists = {k: list(v) for k, v in self._lists.items()}
        return new

    def __rshift__(self, other) -> BuilderBase:
        """Create or extend a Pipeline: a >> b >> c.

        Accepts:
        - BuilderBase (agents, pipelines, etc.)
        - callable (pure function, wrapped as zero-cost step)
        - dict (shorthand for deterministic Route)
        - Route (deterministic branching)
        """
        from adk_fluent.workflow import Pipeline
        from adk_fluent._routing import Route

        # Callable operand: wrap as zero-cost FnStep
        if callable(other) and not isinstance(other, (BuilderBase, Route, type)):
            other = _fn_step(other)

        # Reject unsupported operands (e.g. raw types like int)
        if not isinstance(other, (BuilderBase, Route, dict)) and not hasattr(other, 'build'):
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

        # Route operand: build route agent and create pipeline
        if isinstance(other, Route):
            route_agent = other.build()
            my_name = self._config.get("name", "")
            p = Pipeline(f"{my_name}_routed")
            if isinstance(self, Pipeline):
                for item in self._lists.get("sub_agents", []):
                    p._lists["sub_agents"].append(item)
            else:
                p._lists["sub_agents"].append(self)
            p._lists["sub_agents"].append(route_agent)  # Already built
            return p

        my_name = self._config.get("name", "")
        other_name = other._config.get("name", "") if hasattr(other, '_config') else ""
        if isinstance(self, Pipeline):
            # Clone, then append — original Pipeline unchanged
            clone = self._clone_shallow()
            clone.step(other)
            clone._config["name"] = f"{my_name}_then_{other_name}"
            return clone
        else:
            name = f"{my_name}_then_{other_name}"
            p = Pipeline(name)
            p.step(self)
            p.step(other)
            return p

    def __rrshift__(self, other) -> BuilderBase:
        """Support callable >> agent syntax."""
        if callable(other) and not isinstance(other, (BuilderBase, type)):
            left = _fn_step(other)
            return left >> self
        return NotImplemented

    def __or__(self, other: BuilderBase) -> BuilderBase:
        """Create or extend a FanOut: a | b | c."""
        from adk_fluent.workflow import FanOut
        my_name = self._config.get("name", "")
        other_name = other._config.get("name", "")
        if isinstance(self, FanOut):
            # Clone, then add branch — original FanOut unchanged
            clone = self._clone_shallow()
            clone.branch(other)
            clone._config["name"] = f"{my_name}_and_{other_name}"
            return clone
        else:
            name = f"{my_name}_and_{other_name}"
            f = FanOut(name)
            f.branch(self)
            f.branch(other)
            return f

    def __mul__(self, other) -> BuilderBase:
        """Create a Loop: agent * 3 or agent * until(pred)."""
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
        """Bind a Pydantic model as the typed output contract: agent @ Schema."""
        clone = self._clone_shallow()
        clone._config["_output_schema"] = schema
        return clone

    def __floordiv__(self, other) -> BuilderBase:
        """Create a fallback chain: agent_a // agent_b.

        Tries each agent in order. First success wins.
        """
        from adk_fluent._routing import _make_fallback_builder

        # Callable on right side: wrap it
        if callable(other) and not isinstance(other, (BuilderBase, type)):
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

    def validate(self) -> Self:
        """Try to build; raise ValueError with clear message on failure. Returns self."""
        try:
            self.build()
        except Exception as exc:
            name = self._config.get("name", "?")
            raise ValueError(
                f"Validation failed for {self.__class__.__name__}('{name}'): {exc}"
            ) from exc
        return self

    def explain(self) -> str:
        """Return a multi-line summary of this builder's state."""
        cls_name = self.__class__.__name__
        name = self._config.get("name", "?")
        lines = [f"{cls_name}: {name}"]

        # Config fields
        config_fields = [k for k in self._config if k != "name" and not k.startswith("_")]
        if config_fields:
            lines.append(f"  Config fields: {', '.join(config_fields)}")

        # Callbacks
        for field, fns in self._callbacks.items():
            if fns:
                alias = self._reverse_callback_alias(field)
                lines.append(f"  Callback '{alias}': {len(fns)} registered")

        # Lists
        for field, items in self._lists.items():
            if items:
                lines.append(f"  {field}: {len(items)} items")

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
        config = {
            k: self._serialize_value(v)
            for k, v in self._config.items()
            if not k.startswith("_")
        }
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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BuilderBase:
        """Reconstruct a builder from a dict. Only restores config (not callables)."""
        import inspect
        config = data.get("config", {})
        # Determine constructor args via inspect
        sig = inspect.signature(cls.__init__)
        params = list(sig.parameters.keys())
        # Skip 'self'
        params = [p for p in params if p != "self"]
        # Build constructor kwargs from config
        ctor_kwargs = {}
        remaining = dict(config)
        for p in params:
            if p in remaining:
                ctor_kwargs[p] = remaining.pop(p)
        builder = cls(**ctor_kwargs)
        # Apply remaining config fields
        for k, v in remaining.items():
            builder._config[k] = v
        return builder

    def to_yaml(self) -> str:
        """Serialize builder state to YAML string."""
        import yaml
        return yaml.dump(self.to_dict(), default_flow_style=False)

    @classmethod
    def from_yaml(cls, yaml_str: str) -> BuilderBase:
        """Reconstruct a builder from a YAML string."""
        import yaml
        data = yaml.safe_load(yaml_str)
        return cls.from_dict(data)

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
        # Extract internal directives before stripping
        until_pred = self._config.get("_until_predicate")
        output_schema = self._config.get("_output_schema")

        config = {k: v for k, v in self._config.items() if not k.startswith("_")}

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
                config[field] = fns if len(fns) > 1 else fns[0]

        # Merge accumulated lists (auto-building items)
        for field, items in self._lists.items():
            resolved = []
            for item in items:
                if isinstance(item, BuilderBase):
                    resolved.append(item.build())
                else:
                    resolved.append(item)
            existing = config.get(field, [])
            if isinstance(existing, list):
                config[field] = existing + resolved
            else:
                config[field] = resolved

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
    # Task 7: Presets (.use())
    # ------------------------------------------------------------------

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


# ======================================================================
# Post-BuilderBase primitives (depend on BuilderBase)
# ======================================================================

_fn_step_counter = 0


def _fn_step(fn: Callable) -> BuilderBase:
    """Wrap a pure function as a zero-cost workflow step.

    The function receives a dict (snapshot of session state) and returns
    a dict of updates to merge back into state:

        def trim(state):
            return {"summary": state["findings"][:500]}

    If the function returns None, it is assumed to have no state updates.
    """
    global _fn_step_counter
    name = getattr(fn, "__name__", "_transform")
    # Sanitize: ADK requires valid Python identifiers for agent names
    if not name.isidentifier():
        _fn_step_counter += 1
        name = f"fn_step_{_fn_step_counter}"

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

    def _clone_shallow(self) -> BuilderBase:
        clone = super()._clone_shallow()
        clone._fn = self._fn
        return clone

    def build(self):
        from google.adk.agents.base_agent import BaseAgent

        fn_ref = self._fn

        class _FnAgent(BaseAgent):
            """Zero-cost function agent. No LLM call."""
            async def _run_async_impl(self, ctx):
                result = fn_ref(dict(ctx.session.state))
                if isinstance(result, dict):
                    for k, v in result.items():
                        ctx.session.state[k] = v
                # yield nothing — pure transform, no events

        return _FnAgent(name=self._config["name"])


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

    def _clone_shallow(self) -> BuilderBase:
        clone = super()._clone_shallow()
        clone._children = list(self._children)
        return clone

    def build(self):
        from google.adk.agents.base_agent import BaseAgent

        built_children = []
        for child in self._children:
            if isinstance(child, BuilderBase):
                built_children.append(child.build())
            else:
                built_children.append(child)

        class _FallbackAgent(BaseAgent):
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

        return _FallbackAgent(
            name=self._config["name"],
            sub_agents=built_children,
        )
