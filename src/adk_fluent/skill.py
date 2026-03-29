"""Skill builder — load, configure, and compose skills from SKILL.md files.

A Skill is a composable runtime unit parsed from a SKILL.md file.  It extends
:class:`BuilderBase` and inherits all operators (``>>``, ``|``, ``*``,
``//``, ``@``), execution helpers (``.ask()``, ``.stream()``), and
introspection (``.explain()``, ``.validate()``).

Usage::

    from adk_fluent import Skill

    # Load and execute
    result = Skill("skills/deep-research/").ask("Research quantum computing")

    # Compose with other builders
    pipeline = Skill("skills/research/") >> Skill("skills/writing/")

    # Override model for all agents in the skill
    fast = Skill("skills/research/").model("gemini-2.5-flash")

    # Inject tool implementations
    custom = Skill("skills/research/").inject(web_search=my_search_fn)
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

from adk_fluent._base import BuilderBase

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from google.adk.agents.base_agent import BaseAgent as _ADK_BaseAgent

__all__ = ["Skill"]


# ======================================================================
# Built-in tool name → factory mapping
# ======================================================================

_BUILTIN_TOOLS: dict[str, Callable[[], Any]] = {}


def _get_builtin_tool(name: str) -> Any | None:
    """Resolve a well-known tool name to an ADK tool instance."""
    # Lazy populate on first call
    if not _BUILTIN_TOOLS:
        _BUILTIN_TOOLS["google_search"] = lambda: __import__(
            "google.adk.tools.google_search_tool", fromlist=["google_search"]
        ).google_search
    factory = _BUILTIN_TOOLS.get(name)
    return factory() if factory else None


def _resolve_tools(tool_names: list[str], injections: dict[str, Any]) -> list[Any]:
    """Resolve tool name strings to actual tool objects.

    Resolution order:
    1. ``injections`` dict (from ``.inject()``)
    2. Built-in ADK tools (``google_search`` etc.)
    3. Skip with warning (tool will be missing at runtime)
    """
    resolved = []
    for name in tool_names:
        if name in injections:
            resolved.append(injections[name])
        else:
            builtin = _get_builtin_tool(name)
            if builtin is not None:
                resolved.append(builtin)
            # else: silently skip — user must .inject() or it fails at runtime
    return resolved


class Skill(BuilderBase):
    """Load, configure, and compose a skill from a SKILL.md file.

    Extends :class:`BuilderBase` — inherits all operators (``>>``, ``|``,
    ``*``, ``//``, ``@``) and shared methods (``.mock()``, ``.clone()``,
    ``.validate()``, ``.use()``).
    """

    _ALIASES: dict[str, str] = {"describe": "description"}
    _CALLBACK_ALIASES: dict[str, str] = {
        "after_agent": "after_agent_callback",
        "before_agent": "before_agent_callback",
    }
    _ADDITIVE_FIELDS: set[str] = {
        "after_agent_callback",
        "before_agent_callback",
    }

    def __init__(self, path: str | Path) -> None:
        """Parse a SKILL.md file and store its definition.

        Does NOT build agents yet — lazy until ``.build()``.
        """
        from adk_fluent._skill_parser import parse_skill_file

        self._config: dict[str, Any] = {}
        self._callbacks: dict[str, list[Callable]] = defaultdict(list)
        self._lists: dict[str, list] = defaultdict(list)
        self._frozen = False

        skill_def = parse_skill_file(path)
        self._config["name"] = skill_def.name
        self._config["_skill_def"] = skill_def
        self._config["_skill_path"] = Path(path)
        self._config["_overrides"] = {}
        self._config["_injections"] = {}
        self._config["_model_override"] = None

    # ------------------------------------------------------------------
    # Configuration methods
    # ------------------------------------------------------------------

    def model(self, model: str) -> Self:
        """Override model for ALL agents in the skill."""
        self = self._maybe_fork_for_mutation()
        self._config["_model_override"] = model
        return self

    def inject(self, **resources: Any) -> Self:
        """Inject tool implementations by name.

        Keys match tool names referenced in ``agents.tools`` in the skill
        file.  Values are callables or ADK tool instances.
        """
        self = self._maybe_fork_for_mutation()
        self._config["_injections"].update(resources)
        return self

    def configure(self, agent_name: str, **overrides: Any) -> Self:
        """Override settings for a specific agent within the skill.

        Valid override keys: ``model``, ``instruct``, ``tools``, ``writes``,
        ``reads``.  Raises :class:`ValueError` if *agent_name* doesn't exist.
        """
        self = self._maybe_fork_for_mutation()
        skill_def = self._config["_skill_def"]
        valid_names = {a.name for a in skill_def.agents}
        if agent_name not in valid_names:
            raise ValueError(
                f"Agent '{agent_name}' not found in skill '{skill_def.name}'. "
                f"Available: {', '.join(sorted(valid_names))}"
            )
        self._config["_overrides"][agent_name] = overrides
        return self

    def describe(self, value: str) -> Self:
        """Set/override skill description."""
        self = self._maybe_fork_for_mutation()
        self._config["description"] = value
        return self

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def topology_expr(self) -> str:
        """Return the topology expression string from the skill file."""
        return self._config["_skill_def"].topology or ""

    def contract(self) -> dict[str, Any]:
        """Return the input/output contract from the skill file."""
        sd = self._config["_skill_def"]
        return {"input": dict(sd.input_schema), "output": dict(sd.output_schema)}

    def explain(self) -> None:
        """Print a summary of the skill's configuration."""
        import sys

        sd = self._config["_skill_def"]
        lines = [
            f"Skill: {sd.name}",
            f"  Description: {sd.description}" if sd.description else None,
            f"  Version: {sd.version}" if sd.version else None,
            f"  Tags: {', '.join(sd.tags)}" if sd.tags else None,
            f"  Agents: {', '.join(a.name for a in sd.agents)}" if sd.agents else "  Agents: (none — documentation only)",
            f"  Topology: {sd.topology}" if sd.topology else None,
        ]
        model_override = self._config.get("_model_override")
        if model_override:
            lines.append(f"  Model override: {model_override}")
        injections = self._config.get("_injections", {})
        if injections:
            lines.append(f"  Injected tools: {', '.join(injections.keys())}")
        for line in lines:
            if line is not None:
                print(line, file=sys.stderr)

    # ------------------------------------------------------------------
    # Execution helpers (same delegation pattern as Pipeline/Loop)
    # ------------------------------------------------------------------

    def ask(self, prompt: str) -> str:
        """One-shot SYNC execution (blocking)."""
        from adk_fluent._helpers import run_one_shot

        return run_one_shot(self, prompt)

    async def ask_async(self, prompt: str) -> str:
        """One-shot ASYNC execution (non-blocking)."""
        from adk_fluent._helpers import run_one_shot_async

        return await run_one_shot_async(self, prompt)

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        """ASYNC streaming execution."""
        from adk_fluent._helpers import run_stream

        async for chunk in run_stream(self, prompt):
            yield chunk

    async def events(self, prompt: str) -> AsyncIterator[Any]:
        """Stream raw ADK Event objects."""
        from adk_fluent._helpers import run_events

        async for chunk in run_events(self, prompt):
            yield chunk

    def session(self) -> Any:
        """Create an interactive multi-turn chat session."""
        from adk_fluent._helpers import create_session

        return create_session(self)

    def map(self, prompts: list[str], *, concurrency: int = 5) -> list[str]:
        """Batch SYNC execution (blocking)."""
        from adk_fluent._helpers import run_map

        return run_map(self, prompts, concurrency=concurrency)

    async def map_async(self, prompts: list[str], *, concurrency: int = 5) -> list[str]:
        """Batch ASYNC execution."""
        from adk_fluent._helpers import run_map_async

        return await run_map_async(self, prompts, concurrency=concurrency)

    def test(
        self,
        prompt: str,
        *,
        contains: str | None = None,
        matches: str | None = None,
        equals: str | None = None,
    ) -> Self:
        """Run a smoke test."""
        from adk_fluent._helpers import run_inline_test

        return run_inline_test(self, prompt, contains=contains, matches=matches, equals=equals)

    def eval(self, prompt: str, *, expect: str | None = None, criteria: Any | None = None) -> Any:
        """Inline evaluation."""
        from adk_fluent._helpers import _eval_inline

        return _eval_inline(self, prompt, expect=expect, criteria=criteria)

    def eval_suite(self) -> Any:
        """Create an evaluation suite builder."""
        from adk_fluent._helpers import _eval_suite

        return _eval_suite(self)

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _create_agent_builders(self) -> dict[str, BuilderBase]:
        """Create Agent builders from the skill definition.

        Returns a dict mapping agent names to configured builders.
        Also stores them in ``_lists["sub_agents"]`` for mock propagation.
        """
        from adk_fluent.agent import Agent

        skill_def = self._config["_skill_def"]
        model_override = self._config.get("_model_override")
        injections = self._config.get("_injections", {})
        overrides = self._config.get("_overrides", {})

        builders: dict[str, BuilderBase] = {}
        for agent_def in skill_def.agents:
            model = model_override or agent_def.model or "gemini-2.5-flash"
            builder: BuilderBase = Agent(agent_def.name, model)

            if agent_def.instruct:
                builder = builder.instruct(agent_def.instruct)
            if agent_def.describe:
                builder = builder.describe(agent_def.describe)
            if agent_def.writes:
                builder = builder.writes(agent_def.writes)
            if agent_def.reads:
                builder = builder.reads(*agent_def.reads)

            # Resolve tools
            if agent_def.tools:
                resolved = _resolve_tools(agent_def.tools, injections)
                if resolved:
                    for tool in resolved:
                        builder = builder.tool(tool)

            # Apply per-agent overrides from .configure()
            if agent_def.name in overrides:
                for key, val in overrides[agent_def.name].items():
                    setter = getattr(builder, key, None)
                    if setter and callable(setter):
                        builder = setter(val)

            builders[agent_def.name] = builder

        # Store in _lists for mock propagation
        self._lists["sub_agents"] = list(builders.values())

        return builders

    def build(self) -> _ADK_BaseAgent:
        """Build the skill into a native ADK agent graph.

        1. Create Agent builders from each agent definition
        2. Wire them via the topology expression (or default pipeline)
        3. Apply skill-level callbacks
        4. Return the native ADK agent
        """
        from adk_fluent._skill_parser import parse_topology
        from adk_fluent.workflow import Pipeline

        skill_def = self._config["_skill_def"]

        if not skill_def.agents:
            raise ValueError(
                f"Skill '{skill_def.name}' has no agents: block. "
                f"Cannot build a documentation-only skill. "
                f"Add an agents: section to the SKILL.md frontmatter."
            )

        builders = self._create_agent_builders()

        # Wire topology
        if len(builders) == 1:
            root = next(iter(builders.values()))
        elif skill_def.topology:
            topo_fn = parse_topology(skill_def.topology, list(builders.keys()))
            root = topo_fn(builders)
        else:
            # Default: pipeline in definition order
            root = Pipeline(skill_def.name)
            for b in builders.values():
                root = root.step(b)

        # Propagate skill-level callbacks to root
        for field_name, fns in self._callbacks.items():
            for fn in fns:
                cb_method_name = None
                for alias, target in self._CALLBACK_ALIASES.items():
                    if target == field_name:
                        cb_method_name = alias
                        break
                if cb_method_name and hasattr(root, cb_method_name):
                    getattr(root, cb_method_name)(fn)

        result = root.build()
        return self._apply_native_hooks(result)
