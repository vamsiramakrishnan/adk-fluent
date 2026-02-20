# v4 Phase 3: Middleware Protocol Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a composable middleware system that compiles a stack of cross-cutting behaviors (retry, logging, cost tracking, etc.) into a single ADK `BasePlugin`, giving adk-fluent users plugin-level control with a simpler, unified API.

**Architecture:** A `Middleware` Protocol defines ~12 optional async lifecycle hooks (runner, agent, model, tool). A `_MiddlewarePlugin(BasePlugin)` adapter compiles a list of middleware into one ADK plugin. Middleware is attached via `ExecutionConfig.middlewares` and wired into `App.plugins` by `ADKBackend.compile()`. Builder gains a `.middleware()` method for ergonomic attachment.

**Tech Stack:** Python 3.11+, google-adk ≥1.25.0, typing.Protocol, dataclasses

**Reference Specs:**

- `docs/other_specs/adk_fluent_v4_spec.md` — §5 (Middleware Protocol)
- ADK `BasePlugin` — `.venv/lib/python3.11/site-packages/google/adk/plugins/base_plugin.py`

**Key Design Decisions:**

- Middleware is **app-global** (attached to ExecutionConfig, compiled to App.plugins). Agent callbacks are **agent-specific** (stored in IR nodes, compiled per-agent). These are separate systems.
- The `Middleware` Protocol uses **simplified signatures** — hides ADK internals like `InvocationContext`, `BaseTool`, `BaseAgent`. The adapter translates.
- All methods are **optional** — a middleware only implements the hooks it needs.
- Stack execution: **in-order, first-non-None short-circuits** (matches ADK plugin semantics).
- Built-in middleware starts small: **retry + structured_log**. More added later.

______________________________________________________________________

## Context: Key Files

| File                                          | Role                                        |
| --------------------------------------------- | ------------------------------------------- |
| `src/adk_fluent/_ir.py`                       | ExecutionConfig (needs `middlewares` field) |
| `src/adk_fluent/backends/adk.py`              | ADKBackend.compile() (needs plugin wiring)  |
| `src/adk_fluent/_base.py`                     | BuilderBase (needs `.middleware()` method)  |
| `src/adk_fluent/__init__.py`                  | Package exports                             |
| `.venv/.../google/adk/plugins/base_plugin.py` | ADK BasePlugin (13 callbacks)               |

## ADK BasePlugin Callback Signatures (Reference)

```
RUNNER LIFECYCLE:
  on_user_message_callback(invocation_context, user_message) -> Content | None
  before_run_callback(invocation_context) -> Content | None
  on_event_callback(invocation_context, event) -> Event | None
  after_run_callback(invocation_context) -> None

AGENT LIFECYCLE:
  before_agent_callback(agent, callback_context) -> Content | None
  after_agent_callback(agent, callback_context) -> Content | None

MODEL LIFECYCLE:
  before_model_callback(callback_context, llm_request) -> LlmResponse | None
  after_model_callback(callback_context, llm_response) -> LlmResponse | None
  on_model_error_callback(callback_context, llm_request, error) -> LlmResponse | None

TOOL LIFECYCLE:
  before_tool_callback(tool, tool_args, tool_context) -> dict | None
  after_tool_callback(tool, tool_args, tool_context, result) -> dict | None
  on_tool_error_callback(tool, tool_args, tool_context, error) -> dict | None

CLEANUP:
  close() -> None
```

All BasePlugin parameters are keyword-only (`*`).

______________________________________________________________________

### Task 1: Middleware Protocol

**Problem:** Need a composable middleware abstraction with simpler signatures than ADK's BasePlugin.

**Files:**

- Create: `src/adk_fluent/middleware.py`
- Create: `tests/manual/test_middleware.py`

**Step 1: Write tests for Middleware protocol**

Create `tests/manual/test_middleware.py`:

```python
"""Tests for the Middleware protocol and _MiddlewarePlugin adapter."""
import pytest
from adk_fluent.middleware import Middleware


# --- Protocol tests ---

def test_middleware_is_runtime_checkable():
    """Middleware should be a runtime-checkable Protocol."""
    class Conforming:
        pass  # All methods optional — empty class conforms

    class HasBeforeModel:
        async def before_model(self, ctx, request):
            return None

    assert isinstance(Conforming(), Middleware)
    assert isinstance(HasBeforeModel(), Middleware)


def test_middleware_protocol_has_expected_methods():
    """Protocol should define all lifecycle hooks."""
    import inspect
    members = [m for m in dir(Middleware) if not m.startswith("_")]
    expected = {
        "on_user_message", "before_run", "after_run", "on_event",
        "before_agent", "after_agent",
        "before_model", "after_model", "on_model_error",
        "before_tool", "after_tool", "on_tool_error",
        "close",
    }
    assert expected.issubset(set(members)), f"Missing: {expected - set(members)}"
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/manual/test_middleware.py -v
```

Expected: FAIL — `middleware` module doesn't exist

**Step 3: Implement Middleware protocol**

Create `src/adk_fluent/middleware.py`:

```python
"""Middleware protocol and adapter for adk-fluent.

Middleware provides composable cross-cutting behavior (logging, retry,
cost tracking, etc.) that compiles to ADK BasePlugin instances.

Middleware is app-global (attached via ExecutionConfig). This is separate
from agent-level callbacks (stored per-agent in IR nodes).
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

__all__ = [
    "Middleware",
    "_MiddlewarePlugin",
]


@runtime_checkable
class Middleware(Protocol):
    """A composable unit of cross-cutting behavior.

    All methods are optional — implement only the hooks you need.
    Stack execution: in-order, first non-None return short-circuits.

    Lifecycle groups:
        Runner:  on_user_message, before_run, after_run, on_event
        Agent:   before_agent, after_agent
        Model:   before_model, after_model, on_model_error
        Tool:    before_tool, after_tool, on_tool_error
        Cleanup: close
    """

    # --- Runner lifecycle ---

    async def on_user_message(self, ctx: Any, message: Any) -> Any:
        """Called when a user message is received."""
        return None

    async def before_run(self, ctx: Any) -> Any:
        """Called before execution starts."""
        return None

    async def after_run(self, ctx: Any) -> None:
        """Called after execution completes."""
        return None

    async def on_event(self, ctx: Any, event: Any) -> Any:
        """Called for each event during execution."""
        return None

    # --- Agent lifecycle ---

    async def before_agent(self, ctx: Any, agent_name: str) -> Any:
        """Called before an agent executes."""
        return None

    async def after_agent(self, ctx: Any, agent_name: str) -> Any:
        """Called after an agent executes."""
        return None

    # --- Model lifecycle ---

    async def before_model(self, ctx: Any, request: Any) -> Any:
        """Called before an LLM request."""
        return None

    async def after_model(self, ctx: Any, response: Any) -> Any:
        """Called after an LLM response."""
        return None

    async def on_model_error(self, ctx: Any, request: Any, error: Exception) -> Any:
        """Called when an LLM request fails."""
        return None

    # --- Tool lifecycle ---

    async def before_tool(self, ctx: Any, tool_name: str, args: dict) -> dict | None:
        """Called before a tool executes."""
        return None

    async def after_tool(self, ctx: Any, tool_name: str, args: dict, result: dict) -> dict | None:
        """Called after a tool executes."""
        return None

    async def on_tool_error(self, ctx: Any, tool_name: str, args: dict, error: Exception) -> dict | None:
        """Called when a tool execution fails."""
        return None

    # --- Cleanup ---

    async def close(self) -> None:
        """Called when the app shuts down."""
        pass
```

**Step 4: Run tests**

```bash
pytest tests/manual/test_middleware.py -v
```

Expected: All PASS

**Step 5: Run full test suite**

```bash
pytest tests/ --tb=short -q
```

Expected: All PASS, no regressions

**Step 6: Commit**

```bash
git add src/adk_fluent/middleware.py tests/manual/test_middleware.py
git commit -m "feat: add Middleware protocol with 13 lifecycle hooks"
```

______________________________________________________________________

### Task 2: \_MiddlewarePlugin Adapter

**Problem:** Need to compile a stack of `Middleware` objects into a single ADK `BasePlugin` that can be passed to `App.plugins`.

**Files:**

- Modify: `src/adk_fluent/middleware.py` (add `_MiddlewarePlugin`)
- Add tests to: `tests/manual/test_middleware.py`

**Step 1: Write tests for \_MiddlewarePlugin**

Append to `tests/manual/test_middleware.py`:

```python
# --- _MiddlewarePlugin adapter tests ---

import asyncio
from adk_fluent.middleware import _MiddlewarePlugin


def test_middleware_plugin_is_base_plugin():
    from google.adk.plugins.base_plugin import BasePlugin
    plugin = _MiddlewarePlugin(name="test", stack=[])
    assert isinstance(plugin, BasePlugin)


def test_middleware_plugin_runs_stack_in_order():
    """Middleware should execute in registration order."""
    call_log = []

    class MW1:
        async def before_model(self, ctx, request):
            call_log.append("mw1")
            return None

    class MW2:
        async def before_model(self, ctx, request):
            call_log.append("mw2")
            return None

    plugin = _MiddlewarePlugin(name="test", stack=[MW1(), MW2()])

    async def run():
        result = await plugin.before_model_callback(
            callback_context=None, llm_request=None
        )
        return result

    result = asyncio.run(run())
    assert call_log == ["mw1", "mw2"]
    assert result is None  # No short-circuit


def test_middleware_plugin_short_circuits_on_non_none():
    """First non-None return should stop the chain."""
    call_log = []

    class MW1:
        async def before_model(self, ctx, request):
            call_log.append("mw1")
            return "intercepted"

    class MW2:
        async def before_model(self, ctx, request):
            call_log.append("mw2")  # Should NOT be reached
            return None

    plugin = _MiddlewarePlugin(name="test", stack=[MW1(), MW2()])

    async def run():
        return await plugin.before_model_callback(
            callback_context=None, llm_request=None
        )

    result = asyncio.run(run())
    assert call_log == ["mw1"]
    assert result == "intercepted"


def test_middleware_plugin_skips_unimplemented_hooks():
    """Middleware without a hook should be silently skipped."""
    class OnlyBeforeModel:
        async def before_model(self, ctx, request):
            return "result"

    plugin = _MiddlewarePlugin(name="test", stack=[OnlyBeforeModel()])

    async def run():
        # after_model not implemented — should return None
        result = await plugin.after_model_callback(
            callback_context=None, llm_response=None
        )
        return result

    result = asyncio.run(run())
    assert result is None


def test_middleware_plugin_before_agent_passes_agent_name():
    """before_agent should extract agent name from ADK agent object."""
    captured = {}

    class NameCapture:
        async def before_agent(self, ctx, agent_name):
            captured["name"] = agent_name
            return None

    plugin = _MiddlewarePlugin(name="test", stack=[NameCapture()])

    class FakeAgent:
        name = "my_agent"

    async def run():
        return await plugin.before_agent_callback(
            agent=FakeAgent(), callback_context=None
        )

    asyncio.run(run())
    assert captured["name"] == "my_agent"


def test_middleware_plugin_before_tool_passes_tool_name():
    """before_tool should extract tool name from ADK tool object."""
    captured = {}

    class ToolCapture:
        async def before_tool(self, ctx, tool_name, args):
            captured["name"] = tool_name
            captured["args"] = args
            return None

    plugin = _MiddlewarePlugin(name="test", stack=[ToolCapture()])

    class FakeTool:
        name = "search"

    async def run():
        return await plugin.before_tool_callback(
            tool=FakeTool(), tool_args={"q": "hello"}, tool_context=None
        )

    asyncio.run(run())
    assert captured["name"] == "search"
    assert captured["args"] == {"q": "hello"}


def test_middleware_plugin_on_model_error_passes_error():
    """on_model_error should pass the exception object."""
    captured = {}

    class ErrorCapture:
        async def on_model_error(self, ctx, request, error):
            captured["error"] = error
            return None

    plugin = _MiddlewarePlugin(name="test", stack=[ErrorCapture()])

    err = ValueError("test error")

    async def run():
        return await plugin.on_model_error_callback(
            callback_context=None, llm_request=None, error=err
        )

    asyncio.run(run())
    assert captured["error"] is err


def test_middleware_plugin_close_calls_all():
    """close() should call close() on all middleware, not short-circuit."""
    closed = []

    class MW1:
        async def close(self):
            closed.append("mw1")

    class MW2:
        async def close(self):
            closed.append("mw2")

    plugin = _MiddlewarePlugin(name="test", stack=[MW1(), MW2()])

    asyncio.run(plugin.close())
    assert closed == ["mw1", "mw2"]
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/manual/test_middleware.py -v
```

Expected: New tests FAIL — `_MiddlewarePlugin` not implemented yet

**Step 3: Implement `_MiddlewarePlugin`**

Add to `src/adk_fluent/middleware.py`:

```python
from google.adk.plugins.base_plugin import BasePlugin


class _MiddlewarePlugin(BasePlugin):
    """Compiles a middleware stack into a single ADK-compatible plugin.

    ADK execution order: plugins first → agent callbacks second.
    This ensures middleware has priority over user-defined callbacks.

    Each callback iterates the stack in order. First non-None return
    short-circuits the remaining middleware (matching ADK semantics).
    """

    def __init__(self, name: str, stack: list):
        super().__init__(name=name)
        self._stack = list(stack)

    # --- Helper: iterate stack for a given method ---

    async def _run_stack(self, method_name: str, *args, **kwargs):
        """Call method_name on each middleware in order. Short-circuit on non-None."""
        for mw in self._stack:
            fn = getattr(mw, method_name, None)
            if fn is not None:
                result = await fn(*args, **kwargs)
                if result is not None:
                    return result
        return None

    async def _run_stack_void(self, method_name: str, *args, **kwargs):
        """Call method_name on ALL middleware (no short-circuit). For void hooks."""
        for mw in self._stack:
            fn = getattr(mw, method_name, None)
            if fn is not None:
                await fn(*args, **kwargs)

    # --- Runner lifecycle ---

    async def on_user_message_callback(self, *, invocation_context, user_message):
        return await self._run_stack(
            "on_user_message", invocation_context, user_message
        )

    async def before_run_callback(self, *, invocation_context):
        return await self._run_stack("before_run", invocation_context)

    async def after_run_callback(self, *, invocation_context):
        await self._run_stack_void("after_run", invocation_context)

    async def on_event_callback(self, *, invocation_context, event):
        return await self._run_stack("on_event", invocation_context, event)

    # --- Agent lifecycle ---

    async def before_agent_callback(self, *, agent, callback_context):
        return await self._run_stack(
            "before_agent", callback_context, getattr(agent, "name", str(agent))
        )

    async def after_agent_callback(self, *, agent, callback_context):
        return await self._run_stack(
            "after_agent", callback_context, getattr(agent, "name", str(agent))
        )

    # --- Model lifecycle ---

    async def before_model_callback(self, *, callback_context, llm_request):
        return await self._run_stack(
            "before_model", callback_context, llm_request
        )

    async def after_model_callback(self, *, callback_context, llm_response):
        return await self._run_stack(
            "after_model", callback_context, llm_response
        )

    async def on_model_error_callback(self, *, callback_context, llm_request, error):
        return await self._run_stack(
            "on_model_error", callback_context, llm_request, error
        )

    # --- Tool lifecycle ---

    async def before_tool_callback(self, *, tool, tool_args, tool_context):
        return await self._run_stack(
            "before_tool", tool_context,
            getattr(tool, "name", str(tool)), tool_args
        )

    async def after_tool_callback(self, *, tool, tool_args, tool_context, result):
        return await self._run_stack(
            "after_tool", tool_context,
            getattr(tool, "name", str(tool)), tool_args, result
        )

    async def on_tool_error_callback(self, *, tool, tool_args, tool_context, error):
        return await self._run_stack(
            "on_tool_error", tool_context,
            getattr(tool, "name", str(tool)), tool_args, error
        )

    # --- Cleanup ---

    async def close(self):
        await self._run_stack_void("close")
```

**Step 4: Run tests**

```bash
pytest tests/manual/test_middleware.py -v
```

Expected: All PASS

**Step 5: Run full test suite**

```bash
pytest tests/ --tb=short -q
```

**Step 6: Commit**

```bash
git add src/adk_fluent/middleware.py tests/manual/test_middleware.py
git commit -m "feat: add _MiddlewarePlugin adapter that compiles middleware stack to ADK plugin"
```

______________________________________________________________________

### Task 3: Wire Middleware into ExecutionConfig + ADKBackend

**Problem:** `ExecutionConfig` needs a `middlewares` field, and `ADKBackend.compile()` needs to compile middleware into `App.plugins`.

**Files:**

- Modify: `src/adk_fluent/_ir.py` (add `middlewares` field to `ExecutionConfig`)
- Modify: `src/adk_fluent/backends/adk.py` (compile middleware to plugins)
- Create: `tests/manual/test_middleware_wiring.py`

**Step 1: Write tests**

Create `tests/manual/test_middleware_wiring.py`:

```python
"""Tests for middleware wiring through ExecutionConfig → ADKBackend → App."""
import asyncio
import pytest
from adk_fluent._ir import ExecutionConfig
from adk_fluent._ir_generated import AgentNode
from adk_fluent.backends.adk import ADKBackend
from adk_fluent.middleware import Middleware


def test_execution_config_has_middlewares_field():
    cfg = ExecutionConfig()
    assert cfg.middlewares == ()


def test_execution_config_accepts_middleware_tuple():
    class LogMW:
        pass

    cfg = ExecutionConfig(middlewares=(LogMW(),))
    assert len(cfg.middlewares) == 1


def test_backend_compile_without_middleware():
    """Compile without middleware should produce App with no plugins."""
    backend = ADKBackend()
    node = AgentNode(name="test")
    app = backend.compile(node)
    # App should have no plugins (or empty list)
    plugins = getattr(app, "plugins", []) or []
    assert len(plugins) == 0


def test_backend_compile_with_middleware():
    """Compile with middleware should produce App with a _MiddlewarePlugin."""
    from adk_fluent.middleware import _MiddlewarePlugin

    class LogMW:
        async def before_model(self, ctx, request):
            return None

    backend = ADKBackend()
    node = AgentNode(name="test")
    cfg = ExecutionConfig(middlewares=(LogMW(),))
    app = backend.compile(node, config=cfg)

    plugins = getattr(app, "plugins", []) or []
    assert len(plugins) == 1
    assert isinstance(plugins[0], _MiddlewarePlugin)


def test_backend_compile_middleware_preserves_stack_order():
    """Middleware stack order should be preserved in the plugin."""
    call_log = []

    class MW1:
        async def before_model(self, ctx, request):
            call_log.append("mw1")
            return None

    class MW2:
        async def before_model(self, ctx, request):
            call_log.append("mw2")
            return None

    backend = ADKBackend()
    node = AgentNode(name="test")
    cfg = ExecutionConfig(middlewares=(MW1(), MW2()))
    app = backend.compile(node, config=cfg)

    plugin = app.plugins[0]

    async def run():
        await plugin.before_model_callback(
            callback_context=None, llm_request=None
        )

    asyncio.run(run())
    assert call_log == ["mw1", "mw2"]


def test_to_app_with_middleware():
    """to_app() should wire middleware through to App.plugins."""
    from adk_fluent import Agent
    from adk_fluent.middleware import _MiddlewarePlugin

    class LogMW:
        async def before_model(self, ctx, request):
            return None

    cfg = ExecutionConfig(middlewares=(LogMW(),))
    app = Agent("test").to_app(config=cfg)

    plugins = getattr(app, "plugins", []) or []
    assert len(plugins) == 1
    assert isinstance(plugins[0], _MiddlewarePlugin)
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/manual/test_middleware_wiring.py -v
```

Expected: FAIL — `ExecutionConfig` has no `middlewares` field

**Step 3: Add `middlewares` to ExecutionConfig**

In `src/adk_fluent/_ir.py`, add the `middlewares` field to `ExecutionConfig`:

```python
@dataclass(frozen=True)
class ExecutionConfig:
    """Top-level execution configuration."""
    app_name: str = "adk_fluent_app"
    max_llm_calls: int = 500
    timeout_seconds: float | None = None
    streaming_mode: Literal["none", "sse", "bidi"] = "none"
    resumable: bool = False
    compaction: CompactionConfig | None = None
    custom_metadata: dict[str, Any] | None = None
    middlewares: tuple = ()
```

**Step 4: Update ADKBackend.compile() to wire middleware**

In `src/adk_fluent/backends/adk.py`, update the `compile()` method to create a `_MiddlewarePlugin` when middlewares are present:

After the resumability block and before `return App(**app_kwargs)`, add:

```python
        # Middleware → plugin
        if cfg.middlewares:
            from adk_fluent.middleware import _MiddlewarePlugin
            plugin = _MiddlewarePlugin(
                name=f"{cfg.app_name}_middleware",
                stack=list(cfg.middlewares),
            )
            app_kwargs["plugins"] = [plugin]
```

**Step 5: Run tests**

```bash
pytest tests/manual/test_middleware_wiring.py -v
```

Expected: All PASS

**Step 6: Run full test suite**

```bash
pytest tests/ --tb=short -q
```

**Step 7: Commit**

```bash
git add src/adk_fluent/_ir.py src/adk_fluent/backends/adk.py tests/manual/test_middleware_wiring.py
git commit -m "feat: wire middleware through ExecutionConfig into ADK App plugins"
```

______________________________________________________________________

### Task 4: Builder `.middleware()` Method

**Problem:** Users need an ergonomic way to attach middleware to a builder chain without manually constructing `ExecutionConfig`.

**Files:**

- Modify: `src/adk_fluent/_base.py` (add `.middleware()` to BuilderBase, update `to_app()`)
- Create: `tests/manual/test_builder_middleware.py`

**Step 1: Write tests**

Create `tests/manual/test_builder_middleware.py`:

```python
"""Tests for builder .middleware() method."""
import asyncio
import pytest
from adk_fluent import Agent


def test_middleware_method_returns_self():
    class LogMW:
        pass

    a = Agent("test")
    result = a.middleware(LogMW())
    assert result is a


def test_middleware_method_chainable():
    class MW1:
        pass
    class MW2:
        pass

    a = Agent("test").middleware(MW1()).middleware(MW2())
    assert len(a._middlewares) == 2


def test_middleware_flows_through_to_app():
    from adk_fluent.middleware import _MiddlewarePlugin

    class LogMW:
        async def before_model(self, ctx, request):
            return None

    app = Agent("test").middleware(LogMW()).to_app()
    plugins = getattr(app, "plugins", []) or []
    assert len(plugins) == 1
    assert isinstance(plugins[0], _MiddlewarePlugin)


def test_middleware_with_explicit_config_merges():
    """Middleware from builder + config should both be included."""
    from adk_fluent._ir import ExecutionConfig
    from adk_fluent.middleware import _MiddlewarePlugin

    class MW1:
        async def before_model(self, ctx, request):
            return None

    class MW2:
        async def after_model(self, ctx, response):
            return None

    cfg = ExecutionConfig(middlewares=(MW2(),))
    app = Agent("test").middleware(MW1()).to_app(config=cfg)
    plugins = getattr(app, "plugins", []) or []
    assert len(plugins) == 1
    plugin = plugins[0]
    # Stack should have both MW1 (from builder) and MW2 (from config)
    assert len(plugin._stack) == 2


def test_middleware_preserved_through_operators():
    """Middleware should survive >> and | operators."""
    class LogMW:
        pass

    pipeline = Agent("a").middleware(LogMW()) >> Agent("b")
    # The pipeline should carry the middleware from its children
    assert hasattr(pipeline, "_middlewares")


def test_pipeline_to_app_with_middleware():
    from adk_fluent.middleware import _MiddlewarePlugin

    class LogMW:
        async def before_model(self, ctx, request):
            return None

    app = (Agent("a").middleware(LogMW()) >> Agent("b")).to_app()
    plugins = getattr(app, "plugins", []) or []
    assert len(plugins) == 1
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/manual/test_builder_middleware.py -v
```

Expected: FAIL — `.middleware()` doesn't exist

**Step 3: Implement `.middleware()` on BuilderBase**

In `src/adk_fluent/_base.py`:

1. Add `_middlewares` initialization in `BuilderBase.__init_subclass__` or wherever `_config`, `_lists`, `_callbacks` are initialized. Actually, since BuilderBase uses `__init_subclass__` and mixin patterns, the simplest approach is to add `_middlewares` as a lazy attribute:

```python
def middleware(self, mw) -> Self:
    """Attach a middleware to this builder.

    Middleware is app-global — it applies to the entire execution,
    not just this agent. When to_app() is called, all middleware
    from the builder chain is collected and compiled into a plugin.
    """
    if not hasattr(self, "_middlewares"):
        self._middlewares = []
    self._middlewares.append(mw)
    return self
```

Add this method right after the `to_app()` method on BuilderBase.

2. Update `to_app()` to collect middleware from the builder and merge with config:

```python
def to_app(self, config=None):
    """Compile this builder through IR to a native ADK App."""
    from adk_fluent._ir import ExecutionConfig
    from adk_fluent.backends.adk import ADKBackend

    builder_mw = getattr(self, "_middlewares", [])
    cfg = config or ExecutionConfig()

    # Merge builder middleware + config middleware
    if builder_mw:
        all_mw = tuple(builder_mw) + cfg.middlewares
        cfg = ExecutionConfig(
            app_name=cfg.app_name,
            max_llm_calls=cfg.max_llm_calls,
            timeout_seconds=cfg.timeout_seconds,
            streaming_mode=cfg.streaming_mode,
            resumable=cfg.resumable,
            compaction=cfg.compaction,
            custom_metadata=cfg.custom_metadata,
            middlewares=all_mw,
        )

    backend = ADKBackend()
    ir = self.to_ir()
    return backend.compile(ir, config=cfg)
```

3. Ensure `_fork_for_operator()` copies `_middlewares`:

Read `_fork_for_operator()` in `_base.py` and add copying of `_middlewares` if present. The method should include:

```python
if hasattr(self, "_middlewares"):
    clone._middlewares = list(self._middlewares)
```

**Step 4: Run tests**

```bash
pytest tests/manual/test_builder_middleware.py -v
```

Expected: All PASS

**Step 5: Run full test suite**

```bash
pytest tests/ --tb=short -q
```

**Step 6: Commit**

```bash
git add src/adk_fluent/_base.py tests/manual/test_builder_middleware.py
git commit -m "feat: add .middleware() method to BuilderBase for ergonomic middleware attachment"
```

______________________________________________________________________

### Task 5: Built-in Middleware + Exports

**Problem:** Provide 2 useful built-in middleware implementations and export all middleware types from `adk_fluent`.

**Files:**

- Modify: `src/adk_fluent/middleware.py` (add RetryMiddleware, StructuredLogMiddleware)
- Modify: `src/adk_fluent/__init__.py` (export middleware types)
- Create: `tests/manual/test_builtin_middleware.py`

**Step 1: Write tests**

Create `tests/manual/test_builtin_middleware.py`:

```python
"""Tests for built-in middleware implementations."""
import asyncio
import pytest
from adk_fluent.middleware import RetryMiddleware, StructuredLogMiddleware


# --- RetryMiddleware ---

def test_retry_middleware_is_middleware():
    from adk_fluent.middleware import Middleware
    mw = RetryMiddleware()
    assert isinstance(mw, Middleware)


def test_retry_middleware_defaults():
    mw = RetryMiddleware()
    assert mw.max_attempts == 3
    assert mw.backoff_base == 1.0


def test_retry_middleware_custom_config():
    mw = RetryMiddleware(max_attempts=5, backoff_base=0.5)
    assert mw.max_attempts == 5
    assert mw.backoff_base == 0.5


def test_retry_middleware_on_model_error_returns_none():
    """Retry middleware returns None to let ADK retry."""
    mw = RetryMiddleware(max_attempts=3, backoff_base=0.0)

    async def run():
        result = await mw.on_model_error(
            ctx=None, request=None, error=ValueError("test")
        )
        return result

    result = asyncio.run(run())
    assert result is None  # Let ADK handle the retry


def test_retry_middleware_on_tool_error_returns_none():
    mw = RetryMiddleware(max_attempts=3, backoff_base=0.0)

    async def run():
        result = await mw.on_tool_error(
            ctx=None, tool_name="search", args={}, error=ValueError("test")
        )
        return result

    result = asyncio.run(run())
    assert result is None


# --- StructuredLogMiddleware ---

def test_structured_log_is_middleware():
    from adk_fluent.middleware import Middleware
    mw = StructuredLogMiddleware()
    assert isinstance(mw, Middleware)


def test_structured_log_captures_events():
    mw = StructuredLogMiddleware()

    async def run():
        await mw.before_model(ctx=None, request="test_request")
        await mw.after_model(ctx=None, response="test_response")
        await mw.before_agent(ctx=None, agent_name="agent1")
        await mw.after_agent(ctx=None, agent_name="agent1")

    asyncio.run(run())
    assert len(mw.log) == 4
    assert mw.log[0]["event"] == "before_model"
    assert mw.log[1]["event"] == "after_model"
    assert mw.log[2]["event"] == "before_agent"
    assert mw.log[2]["agent_name"] == "agent1"


def test_structured_log_never_short_circuits():
    """Log middleware should never return non-None (observation only)."""
    mw = StructuredLogMiddleware()

    async def run():
        r1 = await mw.before_model(ctx=None, request="req")
        r2 = await mw.after_model(ctx=None, response="resp")
        r3 = await mw.before_tool(ctx=None, tool_name="t", args={})
        r4 = await mw.after_tool(ctx=None, tool_name="t", args={}, result={})
        return [r1, r2, r3, r4]

    results = asyncio.run(run())
    assert all(r is None for r in results)


# --- Exports ---

def test_middleware_importable_from_top_level():
    from adk_fluent import Middleware, RetryMiddleware, StructuredLogMiddleware
    assert Middleware is not None
    assert RetryMiddleware is not None
    assert StructuredLogMiddleware is not None
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/manual/test_builtin_middleware.py -v
```

Expected: FAIL — `RetryMiddleware` doesn't exist

**Step 3: Implement built-in middleware**

Add to `src/adk_fluent/middleware.py`:

```python
import asyncio as _asyncio
import time as _time


class RetryMiddleware:
    """Retry middleware for model and tool errors.

    Returns None on error to signal ADK should retry.
    After max_attempts, lets the error propagate.
    Uses exponential backoff between retries.
    """

    def __init__(self, max_attempts: int = 3, backoff_base: float = 1.0):
        self.max_attempts = max_attempts
        self.backoff_base = backoff_base
        self._attempts: dict[str, int] = {}

    async def on_model_error(self, ctx: Any, request: Any, error: Exception) -> Any:
        key = f"model_{id(request)}"
        self._attempts[key] = self._attempts.get(key, 0) + 1
        if self._attempts[key] < self.max_attempts:
            delay = self.backoff_base * (2 ** (self._attempts[key] - 1))
            if delay > 0:
                await _asyncio.sleep(delay)
            return None  # Let ADK retry
        return None  # Exhausted — let error propagate

    async def on_tool_error(self, ctx: Any, tool_name: str, args: dict, error: Exception) -> dict | None:
        key = f"tool_{tool_name}"
        self._attempts[key] = self._attempts.get(key, 0) + 1
        if self._attempts[key] < self.max_attempts:
            delay = self.backoff_base * (2 ** (self._attempts[key] - 1))
            if delay > 0:
                await _asyncio.sleep(delay)
            return None  # Let ADK retry
        return None  # Exhausted — let error propagate


class StructuredLogMiddleware:
    """Observability middleware that captures structured event logs.

    Never short-circuits — all methods return None (observation only).
    Access captured events via the `log` attribute.
    """

    def __init__(self):
        self.log: list[dict[str, Any]] = []

    def _record(self, event: str, **kwargs):
        entry = {"event": event, "timestamp": _time.time()}
        entry.update(kwargs)
        self.log.append(entry)

    async def before_model(self, ctx: Any, request: Any) -> Any:
        self._record("before_model", request=str(request)[:200])
        return None

    async def after_model(self, ctx: Any, response: Any) -> Any:
        self._record("after_model", response=str(response)[:200])
        return None

    async def on_model_error(self, ctx: Any, request: Any, error: Exception) -> Any:
        self._record("on_model_error", error=str(error))
        return None

    async def before_agent(self, ctx: Any, agent_name: str) -> Any:
        self._record("before_agent", agent_name=agent_name)
        return None

    async def after_agent(self, ctx: Any, agent_name: str) -> Any:
        self._record("after_agent", agent_name=agent_name)
        return None

    async def before_tool(self, ctx: Any, tool_name: str, args: dict) -> dict | None:
        self._record("before_tool", tool_name=tool_name)
        return None

    async def after_tool(self, ctx: Any, tool_name: str, args: dict, result: dict) -> dict | None:
        self._record("after_tool", tool_name=tool_name)
        return None

    async def on_tool_error(self, ctx: Any, tool_name: str, args: dict, error: Exception) -> dict | None:
        self._record("on_tool_error", tool_name=tool_name, error=str(error))
        return None
```

Update `__all__` in `middleware.py`:

```python
__all__ = [
    "Middleware",
    "_MiddlewarePlugin",
    "RetryMiddleware",
    "StructuredLogMiddleware",
]
```

**Step 4: Update `src/adk_fluent/__init__.py`**

Add exports:

```python
from .middleware import Middleware, RetryMiddleware, StructuredLogMiddleware
```

And add to `__all__`:

```python
"Middleware",
"RetryMiddleware",
"StructuredLogMiddleware",
```

**Step 5: Run tests**

```bash
pytest tests/manual/test_builtin_middleware.py -v
```

Expected: All PASS

**Step 6: Run full test suite**

```bash
pytest tests/ --tb=short -q
```

**Step 7: Commit**

```bash
git add src/adk_fluent/middleware.py src/adk_fluent/__init__.py tests/manual/test_builtin_middleware.py
git commit -m "feat: add RetryMiddleware and StructuredLogMiddleware built-ins with exports"
```

______________________________________________________________________

## Post-Implementation Verification

After all 5 tasks are complete:

1. **Full test suite:**

   ```bash
   pytest tests/ -v --tb=short
   ```

   Expected: All 983+ tests PASS (plus ~30 new middleware tests)

1. **Round-trip verification:**

   ```python
   python -c "
   from adk_fluent import Agent, StructuredLogMiddleware
   from adk_fluent._ir import ExecutionConfig

   log_mw = StructuredLogMiddleware()
   app = Agent('test').middleware(log_mw).to_app()

   print('App:', app.name)
   print('Plugins:', len(app.plugins))
   print('Plugin type:', type(app.plugins[0]).__name__)
   "
   ```

   Expected: No errors, 1 plugin of type `_MiddlewarePlugin`

1. **Imports:**

   ```bash
   python -c "from adk_fluent import Middleware, RetryMiddleware, StructuredLogMiddleware, Agent"
   ```

   Expected: No import errors

1. **Middleware chaining:**

   ```python
   python -c "
   from adk_fluent import Agent, RetryMiddleware, StructuredLogMiddleware
   app = (
       Agent('a').middleware(RetryMiddleware()).middleware(StructuredLogMiddleware())
       >> Agent('b')
   ).to_app()
   print('Plugins:', len(app.plugins))
   print('Stack size:', len(app.plugins[0]._stack))
   "
   ```

   Expected: 1 plugin, stack size 2

______________________________________________________________________

## Summary

| Task | What                                   | Impact                                                      |
| ---- | -------------------------------------- | ----------------------------------------------------------- |
| 1    | Middleware Protocol                    | 13-method Protocol with simplified signatures               |
| 2    | \_MiddlewarePlugin adapter             | Compiles middleware stack → single ADK BasePlugin           |
| 3    | Wire into ExecutionConfig + ADKBackend | `middlewares` field + App.plugins integration               |
| 4    | Builder `.middleware()` method         | Ergonomic attachment + operator propagation                 |
| 5    | Built-in middleware + exports          | RetryMiddleware, StructuredLogMiddleware, top-level exports |
