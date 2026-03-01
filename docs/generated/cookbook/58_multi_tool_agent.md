# Multi-Tool Task Agent -- Manus / OpenAI Agents SDK Inspired

Demonstrates building a versatile task agent with multiple tools,
safety guardrails, and dependency injection -- inspired by Manus AI's
tool-using agent and the OpenAI Agents SDK patterns.

Uses: .tool(), .guard(), .inject(), .sub_agent(), .context()

*How to attach tools to an agent using the fluent API.*

_Source: `58_multi_tool_agent.py`_

::::\{tab-set}
:::\{tab-item} Native ADK

```python
import functools

from google.adk.agents.llm_agent import LlmAgent


def search_web_native(query: str) -> str:
    """Search the web for information."""
    return f"Results for: {query}"


def calculate_native(expression: str) -> str:
    """Evaluate a mathematical expression."""
    return f"Result: {expression}"


def read_file_native(path: str, api_key: str = "") -> str:
    """Read a file from storage."""
    return f"Contents of {path}"


# Native: tools with infra params leak into LLM schema
agent_native = LlmAgent(
    name="task_agent",
    model="gemini-2.5-flash",
    instruction=(
        "You are a versatile task agent. Use your tools to research, "
        "calculate, and read files to complete the user's request."
    ),
    tools=[
        search_web_native,
        calculate_native,
        functools.partial(read_file_native, api_key="prod_key"),
    ],
)
```

:::
:::\{tab-item} adk-fluent

```python
from adk_fluent import Agent, C


def search_web(query: str) -> str:
    """Search the web for information."""
    return f"Results for: {query}"


def calculate(expression: str) -> str:
    """Evaluate a mathematical expression."""
    return f"Result: {expression}"


def read_file(path: str, api_key: str) -> str:
    """Read a file from cloud storage."""
    return f"Contents of {path} (via {api_key})"


def safety_guardrail(callback_context, llm_request):
    """Screen requests for unsafe operations.

    Blocks attempts to access system files, execute arbitrary code,
    or exfiltrate data through tool calls.
    """
    return None


# The fluent builder provides:
#   .tool()      -- add tools one at a time (appends, not replaces)
#   .guard() -- registers both before_model and after_model
#   .inject()    -- hides infra params from LLM schema
task_agent = (
    Agent("task_agent")
    .model("gemini-2.5-flash")
    .instruct(
        "You are a versatile task agent. Use your tools to research, "
        "calculate, and read files to complete the user's request. "
        "Always explain your reasoning before using a tool."
    )
    .tool(search_web)
    .tool(calculate)
    .tool(read_file)
    .inject(api_key="prod_key")  # Hidden from LLM -- only visible to read_file
    .guard(safety_guardrail)
)

# Verifier agent checks the task agent's work
verifier = (
    Agent("verifier")
    .model("gemini-2.5-flash")
    .instruct("Verify the task agent's output for accuracy and completeness.")
    .context(C.from_state("task_result"))
)

# Compose: task agent -> verifier pipeline
verified_agent = (
    task_agent.writes("task_result")
    >> verifier
)
```

:::
::::

## Equivalence

```python
# Task agent has 3 tools (stored in _lists, not _config)
assert len(task_agent._lists["tools"]) == 3

# Guardrail registered on both before and after model callbacks
assert safety_guardrail in task_agent._callbacks["before_model_callback"]
assert safety_guardrail in task_agent._callbacks["after_model_callback"]

# DI resources stored
assert task_agent._config["_resources"] == {"api_key": "prod_key"}

# inject_resources hides infra params from LLM
import inspect
from adk_fluent.di import inject_resources

wrapped = inject_resources(read_file, {"api_key": "test"})
sig = inspect.signature(wrapped)
assert "path" in sig.parameters
assert "api_key" not in sig.parameters

# Pipeline builds correctly
from adk_fluent import Pipeline

assert isinstance(verified_agent, Pipeline)
built = verified_agent.build()
assert len(built.sub_agents) == 2
assert built.sub_agents[0].name == "task_agent"
assert built.sub_agents[1].name == "verifier"
```

:::\{seealso}
API reference: [FunctionTool](../api/tool.md#builder-FunctionTool)
:::
