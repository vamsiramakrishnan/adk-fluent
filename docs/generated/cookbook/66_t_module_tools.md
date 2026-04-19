# T Module: Fluent Tool Composition and Dynamic Loading

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

:::{tip} What you'll learn
How to attach tools to an agent using the fluent API.
:::

_Source: `66_t_module_tools.py`_

```python
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

# .tools() replaces, .tool() appends — use .tools() first, then .tool() to add
agent2 = Agent("combined").tools(T.fn(tool_a)).tool(tool_b)
ir2 = agent2.to_ir()
assert len(ir2.tools) >= 2

# --- 13. T module with delegate pattern ---
specialist = Agent("specialist").instruct("Specialist work.")
coordinator = Agent("coordinator").tools(T.agent(specialist) | T.fn(calculate))
ir3 = coordinator.to_ir()
assert len(ir3.tools) >= 2

# --- 14. T.mock() ---
from adk_fluent._tools import _MockWrapper

# Create mock with fixed return value
tc_mock = T.mock("search_api", returns="mock result")
assert len(tc_mock) == 1
assert tc_mock._kind == "mock"
mock_tool = tc_mock.to_tools()[0]
assert isinstance(mock_tool, _MockWrapper)
assert mock_tool.name == "search_api"

# Mock with side-effect callable
call_count = 0


def side_effect_fn(query: str) -> str:
    global call_count
    call_count += 1
    return f"Called {call_count} times with {query}"


tc_mock_se = T.mock("counter", side_effect=side_effect_fn)
se_tool = tc_mock_se.to_tools()[0]
assert isinstance(se_tool, _MockWrapper)

# Verify async execution
import asyncio


async def _run_mock_async():
    result = await se_tool.run_async(args={"query": "test"}, tool_context=None)
    return result


result = asyncio.run(_run_mock_async())
assert "Called 1 times" in result

# --- 15. T.confirm() ---
from adk_fluent._tools import _ConfirmWrapper


def risky_operation(target: str) -> str:
    """Perform a risky operation."""
    return f"Executed on {target}"


# Wrap single tool
tc_confirm_single = T.confirm(T.fn(risky_operation))
assert len(tc_confirm_single) == 1
confirm_tool = tc_confirm_single.to_tools()[0]
assert isinstance(confirm_tool, _ConfirmWrapper)
assert confirm_tool.require_confirmation is True

# Wrap with custom message
tc_confirm_msg = T.confirm(T.fn(risky_operation), message="Are you sure?")
msg_tool = tc_confirm_msg.to_tools()[0]
assert isinstance(msg_tool, _ConfirmWrapper)
assert msg_tool._message == "Are you sure?"

# Confirm a composite (wraps each item)
tc_multi = T.fn(search_web) | T.fn(send_email)
tc_confirm_multi = T.confirm(tc_multi)
assert len(tc_confirm_multi) == 2
assert all(isinstance(t, _ConfirmWrapper) for t in tc_confirm_multi.to_tools())

# --- 16. T.timeout() ---
from adk_fluent._tools import _TimeoutWrapper


def slow_operation(data: str) -> str:
    """Potentially slow operation."""
    return f"Processed {data}"


# Wrap with default 30s timeout
tc_timeout = T.timeout(T.fn(slow_operation))
assert len(tc_timeout) == 1
timeout_tool = tc_timeout.to_tools()[0]
assert isinstance(timeout_tool, _TimeoutWrapper)
assert timeout_tool._seconds == 30

# Custom timeout
tc_timeout_5s = T.timeout(T.fn(slow_operation), seconds=5)
timeout_5s_tool = tc_timeout_5s.to_tools()[0]
assert timeout_5s_tool._seconds == 5

# Timeout a composite
tc_timeout_multi = T.timeout(T.fn(search_web) | T.fn(send_email), seconds=10)
assert len(tc_timeout_multi) == 2
assert all(isinstance(t, _TimeoutWrapper) for t in tc_timeout_multi.to_tools())
assert all(t._seconds == 10 for t in tc_timeout_multi.to_tools())

# --- 17. T.cache() ---
from adk_fluent._tools import _CachedWrapper


def expensive_query(query: str) -> str:
    """Expensive API call."""
    return f"Result for {query}"


# Wrap with default 300s TTL
tc_cache = T.cache(T.fn(expensive_query))
assert len(tc_cache) == 1
cache_tool = tc_cache.to_tools()[0]
assert isinstance(cache_tool, _CachedWrapper)
assert cache_tool._ttl == 300
assert cache_tool._cache == {}

# Custom TTL
tc_cache_60s = T.cache(T.fn(expensive_query), ttl=60)
cache_60s_tool = tc_cache_60s.to_tools()[0]
assert cache_60s_tool._ttl == 60


# Custom key function
def custom_key(args: dict) -> str:
    return args.get("query", "default")


tc_cache_custom = T.cache(T.fn(expensive_query), ttl=120, key_fn=custom_key)
cache_custom_tool = tc_cache_custom.to_tools()[0]
assert cache_custom_tool._key_fn is custom_key

# Cache a composite
tc_cache_multi = T.cache(T.fn(search_web) | T.fn(translate), ttl=180)
assert len(tc_cache_multi) == 2
assert all(isinstance(t, _CachedWrapper) for t in tc_cache_multi.to_tools())
assert all(t._ttl == 180 for t in tc_cache_multi.to_tools())

# --- 18. T.transform() ---
from adk_fluent._tools import _TransformWrapper


def process_data(text: str) -> str:
    """Process some text."""
    return f"Processed: {text}"


# Pre-transform (modify arguments)
def pre_fn(args: dict) -> dict:
    args["text"] = args["text"].upper()
    return args


tc_transform_pre = T.transform(T.fn(process_data), pre=pre_fn)
assert len(tc_transform_pre) == 1
transform_tool = tc_transform_pre.to_tools()[0]
assert isinstance(transform_tool, _TransformWrapper)
assert transform_tool._pre is pre_fn
assert transform_tool._post is None


# Post-transform (modify result)
def post_fn(result: str) -> str:
    return result + " [verified]"


tc_transform_post = T.transform(T.fn(process_data), post=post_fn)
post_tool = tc_transform_post.to_tools()[0]
assert post_tool._post is post_fn

# Both pre and post
tc_transform_both = T.transform(T.fn(process_data), pre=pre_fn, post=post_fn)
both_tool = tc_transform_both.to_tools()[0]
assert both_tool._pre is pre_fn
assert both_tool._post is post_fn

# Transform a composite
tc_transform_multi = T.transform(T.fn(search_web) | T.fn(translate), pre=pre_fn)
assert len(tc_transform_multi) == 2
assert all(isinstance(t, _TransformWrapper) for t in tc_transform_multi.to_tools())

# --- 19. Wrapper composition (nesting) ---

# Cache → Timeout → Tool
nested_tool = T.fn(expensive_query)
nested_with_timeout = T.timeout(nested_tool, seconds=5)
nested_with_cache = T.cache(nested_with_timeout, ttl=60)

assert len(nested_with_cache) == 1
outer = nested_with_cache.to_tools()[0]
assert isinstance(outer, _CachedWrapper)
assert outer._ttl == 60

# The inner is a TimeoutWrapper
assert isinstance(outer._inner, _TimeoutWrapper)
assert outer._inner._seconds == 5

# Innermost is FunctionTool
assert isinstance(outer._inner._inner, FunctionTool)

# Multi-layer: Transform → Confirm → Cache → Tool
base = T.fn(process_data)
cached = T.cache(base, ttl=100)
confirmed = T.confirm(cached, message="Proceed?")
transformed = T.transform(confirmed, post=post_fn)

assert len(transformed) == 1
t_outer = transformed.to_tools()[0]
assert isinstance(t_outer, _TransformWrapper)
assert isinstance(t_outer._inner, _ConfirmWrapper)
assert isinstance(t_outer._inner._inner, _CachedWrapper)

# --- 20. Integration with Agent.tools() ---

# Single mock
agent_mock = Agent("tester").tools(T.mock("fake_search", returns="fake data"))
ir_mock = agent_mock.to_ir()
assert len(ir_mock.tools) >= 1

# Composite: mock | real function
agent_mixed = Agent("mixed").tools(T.mock("search", returns="ok") | T.fn(tool_a))
ir_mixed = agent_mixed.to_ir()
assert len(ir_mixed.tools) >= 2

# Cached timeout tool
cached_timeout = T.cache(T.timeout(T.fn(expensive_query), 10), ttl=120)
agent_wrapped = Agent("wrapped").tools(cached_timeout)
ir_wrapped = agent_wrapped.to_ir()
assert len(ir_wrapped.tools) >= 1


# Combine schema + wrapped tools
class ExampleToolSchema:
    pass


agent_schema = Agent("schema_agent").tools(T.schema(ExampleToolSchema) | T.confirm(T.fn(risky_operation)))
ir_schema = agent_schema.to_ir()
assert len(ir_schema.tools) >= 1  # schema marker is extracted, confirm wrapper remains


# Multi-tool integration
def fetch_data(url: str) -> str:
    """Fetch data from URL."""
    return f"Data from {url}"


agent_full = Agent("full_demo").tools(
    T.mock("db_query", returns="cached")
    | T.cache(T.fn(fetch_data), ttl=60)
    | T.timeout(T.fn(slow_operation), seconds=15)
    | T.confirm(T.fn(risky_operation), message="Confirm risky action")
)
ir_full = agent_full.to_ir()
assert len(ir_full.tools) >= 4

print("All T module assertions passed!")
```

:::{seealso}
API reference: [FunctionTool](../api/tool.md#builder-FunctionTool)
:::
