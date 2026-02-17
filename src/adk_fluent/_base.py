"""BuilderBase mixin -- shared capabilities for all generated fluent builders."""
from __future__ import annotations
from typing import Any, Callable, Self


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

    def __rshift__(self, other) -> BuilderBase:
        """Create or extend a Pipeline: a >> b >> c.

        Special case: a >> {"key": agent, ...} creates conditional routing.
        The left side should have .outputs() set. A coordinator agent is created
        that routes to the appropriate sub-agent based on the state value.
        """
        from adk_fluent.workflow import Pipeline

        # Dict operand: conditional routing via coordinator
        if isinstance(other, dict):
            return self._build_conditional_route(other)

        my_name = self._config.get("name", "")
        other_name = other._config.get("name", "") if hasattr(other, '_config') else ""
        if isinstance(self, Pipeline):
            # Append to existing Pipeline
            self.step(other)
            self._config["name"] = f"{my_name}_then_{other_name}"
            return self
        else:
            name = f"{my_name}_then_{other_name}"
            p = Pipeline(name)
            p.step(self)
            p.step(other)
            return p

    def _build_conditional_route(self, routes: dict) -> BuilderBase:
        """Build conditional routing from dict operand.

        Creates a Pipeline where:
        1. Self runs first (should have .outputs() set)
        2. A coordinator Agent reads the state key and routes to the matching sub-agent

        Uses native ADK LLM-driven routing (transfer_to_agent via sub_agents).
        """
        from adk_fluent.workflow import Pipeline
        from adk_fluent.agent import Agent

        output_key = self._config.get("output_key")
        if not output_key:
            raise ValueError(
                "Left side of >> dict must have .outputs() or .output_key() set "
                "so the router knows which state key to check."
            )

        # Build route descriptions for the coordinator instruction
        route_descriptions = []
        sub_agents = []
        for value, agent_builder in routes.items():
            if hasattr(agent_builder, '_config'):
                agent_name = agent_builder._config.get("name", value)
                agent_desc = agent_builder._config.get("description", "")
                if not agent_desc:
                    # Auto-set description for routing
                    agent_builder._config["description"] = f"Handles the '{value}' case."
            else:
                agent_name = getattr(agent_builder, 'name', value)
            route_descriptions.append(f"- If {{{output_key}}} is '{value}', transfer to '{agent_name}'")
            sub_agents.append(agent_builder)

        routes_text = "\n".join(route_descriptions)
        coordinator = Agent(f"route_{output_key}")
        coordinator._config["model"] = self._config.get("model", "gemini-2.5-flash")
        coordinator._config["instruction"] = (
            f"You are a router. Based on the value of {{{output_key}}}, "
            f"transfer to the appropriate agent:\n{routes_text}\n\n"
            f"Do not generate any other response. Just transfer immediately."
        )
        for agent_builder in sub_agents:
            coordinator._lists.setdefault("sub_agents", []).append(agent_builder)

        # Create pipeline: self >> coordinator
        # Append as builders (not eagerly built) so tests can inspect structure
        my_name = self._config.get("name", "")
        p = Pipeline(f"{my_name}_routed")
        p._lists["sub_agents"].append(self)
        p._lists["sub_agents"].append(coordinator)
        return p

    def __or__(self, other: BuilderBase) -> BuilderBase:
        """Create or extend a FanOut: a | b | c."""
        from adk_fluent.workflow import FanOut
        my_name = self._config.get("name", "")
        other_name = other._config.get("name", "")
        if isinstance(self, FanOut):
            self.branch(other)
            self._config["name"] = f"{my_name}_and_{other_name}"
            return self
        else:
            name = f"{my_name}_and_{other_name}"
            f = FanOut(name)
            f.branch(self)
            f.branch(other)
            return f

    def __mul__(self, iterations: int) -> BuilderBase:
        """Create a Loop: agent * 3."""
        from adk_fluent.workflow import Loop, Pipeline
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
        config = {k: v for k, v in self._config.items() if not k.startswith("_")}

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
