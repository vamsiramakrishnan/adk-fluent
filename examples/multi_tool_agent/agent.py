"""
Multi-Tool Task Agent -- Manus / OpenAI Agents SDK Inspired

Demonstrates building a versatile task agent with multiple tools,
safety guardrails, and dependency injection -- inspired by Manus AI's
tool-using agent and the OpenAI Agents SDK patterns.

Uses: .tool(), .guard(), .inject(), .sub_agent(), .context()

Converted from cookbook example: 58_multi_tool_agent.py

Usage:
    cd examples
    adk web multi_tool_agent
"""

from adk_fluent import Agent, C
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)


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
verified_agent = task_agent.writes("task_result") >> verifier

root_agent = verified_agent.build()
