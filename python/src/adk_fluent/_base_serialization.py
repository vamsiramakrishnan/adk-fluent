"""Serialization mixin for :class:`~adk_fluent._base.BuilderBase`.

Holds the dict/YAML round-trip surface (``to_dict`` / ``from_dict`` /
``to_yaml`` / ``from_yaml`` / ``from_native``) plus the value (de)serialization
helpers. Split out of ``_base.py`` to keep the core builder class focused on
the fluent chain machinery.

The methods reference ``BuilderBase`` and the module-level
``_resolve_builder_class`` helper via call-time local imports — by the time any
of these run, ``adk_fluent._base`` is fully imported, so there is no import
cycle even though ``_base`` composes this mixin into ``BuilderBase``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from adk_fluent._base import BuilderBase


class SerializationMixin:
    """dict/YAML/native (de)serialization for builders."""

    @staticmethod
    def _serialize_value(v: Any) -> Any:
        """Serialize a single value for dict/yaml output."""
        from adk_fluent._base import BuilderBase

        if isinstance(v, BuilderBase):
            # Nested builder (e.g. a Pipeline's sub-agents) — recurse so the
            # topology round-trips structurally via from_dict().
            return v.to_dict()
        if isinstance(v, (list, tuple)):
            return [SerializationMixin._serialize_value(x) for x in v]
        if isinstance(v, dict):
            return {k: SerializationMixin._serialize_value(x) for k, x in v.items()}
        if callable(v):
            return getattr(v, "__qualname__", repr(v))
        if hasattr(v, "name") and hasattr(v, "model_fields"):
            # Built ADK agent
            return f"<agent:{v.name}>"
        return v

    @staticmethod
    def _revive_value(v: Any) -> Any:
        """Deserialization dual of :meth:`_serialize_value`.

        Reconstructs nested builder-dicts (``{"_type": ...}``) into builders,
        recursing through lists and dicts. Plain scalars and callable-name
        strings pass through unchanged (callables are not restored).
        """
        if isinstance(v, dict) and "_type" in v:
            return SerializationMixin.from_dict(v)
        if isinstance(v, list):
            return [SerializationMixin._revive_value(x) for x in v]
        if isinstance(v, dict):
            return {k: SerializationMixin._revive_value(x) for k, x in v.items()}
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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BuilderBase:
        """Reconstruct a builder from a :meth:`to_dict` payload.

        This is a **structural** round-trip: it restores the builder *type*,
        its config scalars (name, model, instruction, description, …), and
        nested builder topology (e.g. a Pipeline's sub-agents, recursively).

        It does **NOT** restore callables — callbacks, guards, and tool
        functions are serialized by :meth:`to_dict` as name strings only and
        cannot be turned back into live functions. The reconstructed builder
        is therefore a faithful structural skeleton suitable for inspection,
        diagramming, topology diffing, and config-as-code workflows — not a
        behavior-complete clone. Re-attach callables explicitly after loading.

        Example::

            data = (Agent("a") >> Agent("b")).to_dict()
            skeleton = Pipeline.from_dict(data)   # type + names + topology
        """
        from adk_fluent._base import _resolve_builder_class

        builder_cls = _resolve_builder_class(data.get("_type", "Agent"))
        config = dict(data.get("config", {}))
        name = config.get("name", "")
        obj = builder_cls(name)
        for key, value in config.items():
            if key == "name":
                continue
            # Revive nested builder-dicts stored in config (e.g. sub_agents
            # held in config rather than _lists), recursing through lists/dicts.
            # Plain scalars (instruction text, model, schemas) pass through.
            obj._config[key] = SerializationMixin._revive_value(value)
        # Restore nested builder children (topology). Non-builder list items
        # (tools/functions serialized as name strings) are intentionally not
        # restored — they are not runnable callables. See the docstring.
        for field, items in data.get("lists", {}).items():
            for item in items:
                if isinstance(item, dict) and "_type" in item:
                    obj._lists[field].append(SerializationMixin.from_dict(item))
        return obj

    @classmethod
    def from_yaml(cls, source: str) -> BuilderBase:
        """Reconstruct a builder from YAML produced by :meth:`to_yaml`.

        ``source`` may be a YAML string or a path to a ``.yaml`` file. Shares
        the structural-round-trip semantics (and limitations) of
        :meth:`from_dict` — callables are not restored.
        """
        import os

        try:
            import yaml
        except ImportError as e:
            raise ImportError("from_yaml() requires the 'pyyaml' package. Install it with: pip install pyyaml") from e

        if "\n" not in source and source.endswith((".yaml", ".yml")) and os.path.exists(source):
            with open(source) as f:
                data = yaml.safe_load(f)
        else:
            data = yaml.safe_load(source)
        return cls.from_dict(data)

    @classmethod
    def from_native(cls, native: Any) -> BuilderBase:
        """Adopt a native ADK agent object as a fluent builder — the inverse of ``build()``.

        Recovers the common, round-trippable surface (name, model, instruction,
        description, tools, and sub-agent topology) for the core agent types:

        * ``LlmAgent``       → :class:`Agent`
        * ``SequentialAgent`` → :class:`Pipeline`
        * ``ParallelAgent``   → :class:`FanOut`
        * ``LoopAgent``       → :class:`Loop`

        This is the missing import path: it lets an existing ADK app be wrapped
        in the fluent API for inspection (``.to_mermaid()``, ``.diagnose()``) or
        incremental adoption. Exotic ADK fields and callbacks are not
        reconstructed — layer fluent calls on top of the returned builder.
        Raises ``TypeError`` for unsupported native types.
        """
        from adk_fluent.agent import Agent
        from adk_fluent.workflow import FanOut, Loop, Pipeline

        tname = type(native).__name__
        name = getattr(native, "name", "") or ""

        def _carry_description(builder: BuilderBase) -> None:
            desc = getattr(native, "description", None)
            if desc:
                builder._config["description"] = desc

        if tname in ("SequentialAgent", "ParallelAgent", "LoopAgent"):
            children = [cls.from_native(c) for c in (getattr(native, "sub_agents", None) or [])]
            if tname == "SequentialAgent":
                builder: BuilderBase = Pipeline(name)
            elif tname == "ParallelAgent":
                builder = FanOut(name)
            else:
                builder = Loop(name)
                max_iter = getattr(native, "max_iterations", None)
                if max_iter:
                    builder._config["max_iterations"] = max_iter
            builder._lists["sub_agents"].extend(children)
            _carry_description(builder)
            return builder

        # LlmAgent (and subclasses with an instruction) → Agent
        if tname == "LlmAgent" or hasattr(native, "instruction"):
            model = getattr(native, "model", None)
            model_str = model if isinstance(model, str) else getattr(model, "model", None)
            builder = Agent(name, model_str) if model_str else Agent(name)
            instr = getattr(native, "instruction", None)
            if instr:
                builder._config["instruction"] = instr
            _carry_description(builder)
            tools = list(getattr(native, "tools", None) or [])
            if tools:
                builder._lists["tools"] = tools
            for sub in getattr(native, "sub_agents", None) or []:
                builder._lists["sub_agents"].append(cls.from_native(sub))
            return builder

        raise TypeError(
            f"from_native: unsupported native agent type {tname!r}. "
            "Supported: LlmAgent, SequentialAgent, ParallelAgent, LoopAgent."
        )
