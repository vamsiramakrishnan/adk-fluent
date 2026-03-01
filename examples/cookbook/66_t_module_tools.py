"""T Module: Fluent Tool Composition and Dynamic Loading

Demonstrates the T module for composing, wrapping, and dynamically
loading tools using the fluent API.

Key concepts:
  - TComposite: composable tool chain with | operator
  - T.fn(): wrap callable as FunctionTool
  - T.agent(): wrap agent as AgentTool
  - T.toolset(): wrap any ADK toolset
  - T.google_search(): built-in Google Search
  - T.schema(): attach ToolSchema for contract checking
  - T.search(): BM25-indexed dynamic tool loading
  - ToolRegistry: tool catalog with search
  - SearchToolset: two-phase discovery/execution
"""

# --- FLUENT ---
from adk_fluent._tools import T, TComposite

# --- 1. TComposite composition ---
a = TComposite(["tool_a"])
b = TComposite(["tool_b"])
c = a | b
assert len(c) == 2
assert c.to_tools() == ["tool_a", "tool_b"]

# Three-way composition
d = TComposite(["tool_c"])
result = a | b | d
assert len(result) == 3

# Raw value on left
mixed = "raw_tool" | TComposite(["wrapped"])
assert len(mixed) == 2
assert mixed.to_tools()[0] == "raw_tool"

# Repr
assert "TComposite" in repr(c)


# --- 2. T.fn() wrapping ---
def search_web(query: str) -> str:
    """Search the web for information."""
    return f"Results for {query}"


tc = T.fn(search_web)
assert len(tc) == 1

from google.adk.tools.function_tool import FunctionTool

assert isinstance(tc.to_tools()[0], FunctionTool)

# With confirmation
tc_confirm = T.fn(search_web, confirm=True)
assert isinstance(tc_confirm.to_tools()[0], FunctionTool)

# --- 3. T.agent() wrapping ---
from adk_fluent import Agent

helper = Agent("helper").instruct("Help the user.")
tc_agent = T.agent(helper)
assert len(tc_agent) == 1

from google.adk.tools.agent_tool import AgentTool

assert isinstance(tc_agent.to_tools()[0], AgentTool)

# --- 4. T.google_search() ---
tc_gs = T.google_search()
assert len(tc_gs) == 1

# --- 5. Composition: T.fn() | T.google_search() ---
composed = T.fn(search_web) | T.google_search()
assert len(composed) == 2
assert isinstance(composed.to_tools()[0], FunctionTool)

# --- 6. T.schema() ---
from adk_fluent._tools import _SchemaMarker


class FakeToolSchema:
    pass


tc_schema = T.schema(FakeToolSchema)
assert len(tc_schema) == 1
assert isinstance(tc_schema.to_tools()[0], _SchemaMarker)
assert tc_schema.to_tools()[0]._schema_cls is FakeToolSchema

# --- 7. ToolRegistry ---
from adk_fluent._tool_registry import ToolRegistry


def send_email(to: str, body: str) -> str:
    """Send an email message to a recipient."""
    return f"Email sent to {to}"


def calculate(expr: str) -> str:
    """Perform mathematical calculations."""
    return f"Result: {expr}"


def translate(text: str, lang: str) -> str:
    """Translate text to another language."""
    return f"Translated to {lang}: {text}"


registry = ToolRegistry.from_tools(search_web, send_email, calculate, translate)

# Get tool by name
assert registry.get_tool("search_web") is not None
assert registry.get_tool("nonexistent") is None

# Search
results = registry.search("search web", top_k=2)
assert len(results) <= 2
assert any("search_web" in r["name"] for r in results)

# --- 8. SearchToolset two-phase ---
from adk_fluent._tool_registry import SearchToolset

toolset = SearchToolset(registry, always_loaded=["calculate"], max_tools=10)

# Meta-tool functions
search_result = toolset._search_fn("email")
assert "send_email" in search_result

load_result = toolset._load_fn("send_email")
assert "send_email" in toolset._loaded_names

finalize_result = toolset._finalize_fn()
assert toolset._frozen is True
assert "finalized" in finalize_result.lower() or "frozen" in finalize_result.lower()

# --- 9. T.search() factory ---
registry2 = ToolRegistry.from_tools(search_web, send_email)
tc_search = T.search(registry2)
assert len(tc_search) == 1
assert isinstance(tc_search.to_tools()[0], SearchToolset)

# --- 10. compress_large_result ---
from adk_fluent._tool_registry import compress_large_result

small = "hello"
assert compress_large_result(small, threshold=100) == small

large = "x" * 200
compressed = compress_large_result(large, threshold=100)
assert len(compressed) < len(large)

# --- 11. _ResultVariator ---
from adk_fluent._tool_registry import _ResultVariator

variator = _ResultVariator()
r0 = variator.vary("data", 0)
r1 = variator.vary("data", 1)
assert "data" in r0
assert "data" in r1
assert r0 != r1  # Different prefixes


# --- 12. Builder integration ---
def tool_a(x: str) -> str:
    """Tool A."""
    return x


def tool_b(x: str) -> str:
    """Tool B."""
    return x


agent = Agent("composer").tools(T.fn(tool_a) | T.fn(tool_b))
ir = agent.to_ir()
assert len(ir.tools) >= 2

# .tool() and .tools(TComposite) combine
agent2 = Agent("combined").tool(tool_a).tools(T.fn(tool_b))
ir2 = agent2.to_ir()
assert len(ir2.tools) >= 2

# --- 13. T module with delegate pattern ---
specialist = Agent("specialist").instruct("Specialist work.")
coordinator = Agent("coordinator").tools(T.agent(specialist) | T.fn(calculate))
ir3 = coordinator.to_ir()
assert len(ir3.tools) >= 2

print("All T module assertions passed!")
