"""adk_fluent._subagents — dynamic subagent spawner + task tool.

Claude Agent SDK and Deep Agents SDK both expose a ``Task`` tool that lets
a parent agent spin up a fresh subagent with a specific role and prompt,
run it in a constrained context, and fold its result back into the parent's
state. adk-fluent already has static delegation (`.sub_agent()`,
`.agent_tool()`), but none of those let the agent *decide at runtime* which
specialist to invoke.

This package provides that missing affordance:

- :class:`SubagentSpec` — a frozen dataclass describing one specialist
  (role name, instruction, model, tool names, permission mode, budget).
- :class:`SubagentRegistry` — a dict-like registry of specs keyed by
  role. Parent agents see the list of available roles as part of the
  task tool's docstring.
- :class:`SubagentResult` — structured output from a subagent invocation
  (text, usage tokens, artifacts, metadata).
- :class:`SubagentRunner` — the runtime contract. The default
  implementation dispatches to a user-provided callable; tests use
  :class:`FakeSubagentRunner` to avoid touching a live model.
- :func:`make_task_tool` — factory that produces the ``task(role,
  prompt, context=None)`` tool for the parent agent. The tool's
  docstring is rewritten at build time to enumerate the registered
  roles so the parent LLM knows what specialists exist.

The subagent runtime is intentionally **not** coupled to ADK's own
agent_tool machinery — the abstraction is a plain callable
``(spec, prompt, context) -> SubagentResult``. That keeps the package
testable in isolation and lets callers wire in whatever execution engine
they like (local ADK agent, remote A2A endpoint, canned responses).
"""

from adk_fluent._subagents._registry import SubagentRegistry
from adk_fluent._subagents._result import SubagentResult
from adk_fluent._subagents._runner import (
    FakeSubagentRunner,
    SubagentRunner,
    SubagentRunnerError,
)
from adk_fluent._subagents._spec import SubagentSpec
from adk_fluent._subagents._task_tool import make_task_tool

__all__ = [
    "FakeSubagentRunner",
    "SubagentRegistry",
    "SubagentResult",
    "SubagentRunner",
    "SubagentRunnerError",
    "SubagentSpec",
    "make_task_tool",
]
