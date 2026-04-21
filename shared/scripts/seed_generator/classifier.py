"""Classification engine — categorize ADK classes into semantic tags.

Tags determine which classes get fluent builders and how they're grouped
into output modules.
"""

from __future__ import annotations


def classify_class(name: str, module: str, mro_chain: list[str]) -> str:
    """Classify an ADK class into a semantic tag.

    Rules are checked in priority order; first match wins.

    Returns one of: agent, runtime, eval, auth, service, config, tool,
    plugin, planner, executor, data.
    """
    # 1. Agent hierarchy
    if "BaseAgent" in mro_chain or name == "BaseAgent":
        return "agent"
    # 2. Runtime singletons
    if name in ("App", "Runner", "InMemoryRunner"):
        return "runtime"
    # 3. Evaluation subsystem
    if "evaluation" in module:
        return "eval"
    # 4. Auth subsystem
    if ".auth" in module:
        return "auth"
    # 5-10. Suffix-based classification
    if name.endswith("Service"):
        return "service"
    if name.endswith("Config"):
        return "config"
    if name.endswith("Tool") or name.endswith("Toolset"):
        return "tool"
    if name.endswith("Plugin"):
        return "plugin"
    if name.endswith("Planner"):
        return "planner"
    if name.endswith("Executor"):
        return "executor"
    # 11. Default
    return "data"


_BUILDER_WORTHY_TAGS = frozenset(
    {
        "agent",
        "config",
        "runtime",
        "executor",
        "planner",
        "service",
        "plugin",
        "tool",
    }
)


# ADK mirror-deprecated classes that exist only as legacy-name shims for a
# canonical class. We never emit a builder for these — users go through the
# canonical builder (McpTool, McpToolset, ...).
_DEPRECATED_CLASS_SKIPLIST = frozenset(
    {
        "MCPTool",
        "MCPToolset",
    }
)


def is_builder_worthy(tag: str, *, name: str | None = None) -> bool:
    """Return True if classes with this tag should get a fluent builder."""
    if name is not None and name in _DEPRECATED_CLASS_SKIPLIST:
        return False
    return tag in _BUILDER_WORTHY_TAGS
