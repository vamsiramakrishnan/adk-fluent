# Verb Harmonization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate all verb aliases, rename misleading methods, add Fallback builder, and enforce operator/builder equivalence — producing a zero-ambiguity API surface.

**Architecture:** 10 tasks executed in dependency order. Tasks 1-3 are infrastructure (seed/generator/helpers). Tasks 4-6 are core renames in hand-written files. Task 7 adds the Fallback builder. Task 8 regenerates. Task 9 migrates all tests/examples. Task 10 is full verification.

**Tech Stack:** Python 3.11+, `seeds/seed.manual.toml` code generation pipeline, `just seed && just generate`, ruff, pyright, pytest.

---

### Task 1: Update `seed.manual.toml` — Remove Aliases, Rename Extras

**Files:**

- Modify: `seeds/seed.manual.toml`

**Step 1: Remove `save_as` from manual aliases**

In `seeds/seed.manual.toml`, find and remove this line:

```toml
[builders.Agent.manual_aliases]
save_as = "output_key"
```

Replace with:

```toml
[builders.Agent.manual_aliases]
```

(empty section — no manual aliases remain)

**Step 2: Update deprecated aliases — add removals, remove old ones**

Find:

```toml
[builders.Agent.deprecated_aliases]
outputs = { field = "output_key", use = "save_as" }
history = { field = "include_contents", use = "context" }
include_history = { field = "include_contents", use = "context" }
static_instruct = { field = "static_instruction", use = "static" }
```

Replace with:

```toml
[builders.Agent.deprecated_aliases]
save_as = { field = "output_key", use = "writes" }
outputs = { field = "output_key", use = "writes" }
output_key = { field = "output_key", use = "writes" }
output_schema = { field = "output_schema", use = "returns" }
input_schema = { field = "input_schema", use = "accepts" }
history = { field = "include_contents", use = "context" }
include_history = { field = "include_contents", use = "context" }
static_instruct = { field = "static_instruction", use = "static" }
retry_if = { field = "_retry_if", use = "loop_while" }
inject_context = { field = "_inject_context", use = "prepend" }
```

**Step 3: Rename `guardrail` extra to `guard`**

Find:

```toml
[[builders.Agent.extras]]
name = "guardrail"
signature = "(self, fn: Callable[..., Any]) -> Self"
doc = "Attach a guardrail function as both before_model and after_model callback."
behavior = "dual_callback"
target_fields = ["before_model_callback", "after_model_callback"]
```

Replace `name = "guardrail"` with `name = "guard"`. Update the doc:

```toml
[[builders.Agent.extras]]
name = "guard"
signature = "(self, fn: Callable[..., Any]) -> Self"
doc = "Attach a guard function as both before_model and after_model callback. Runs before the LLM call and after the LLM response."
behavior = "dual_callback"
target_fields = ["before_model_callback", "after_model_callback"]
```

Update `see_also` to remove old name references.

**Step 4: Rename `delegate` extra to `agent_tool`**

Find:

```toml
[[builders.Agent.extras]]
name = "delegate"
signature = "(self, agent: Any) -> Self"
doc = "Add an agent as a delegatable tool (wraps in AgentTool). The coordinator LLM can route to this agent."
behavior = "runtime_helper"
helper_func = "delegate_agent"
```

Replace with:

```toml
[[builders.Agent.extras]]
name = "agent_tool"
signature = "(self, agent: Any) -> Self"
doc = "Wrap an agent as a callable tool (AgentTool) and add it to this agent's tools. The LLM can invoke the wrapped agent by name."
behavior = "runtime_helper"
helper_func = "delegate_agent"
```

Update the example to use `.agent_tool(specialist)` instead of `.delegate(specialist)`.

**Step 5: Update `output_key` field docstring**

In the `[builders.Agent.field_docs]` section, find:

```toml
output_key = "Session state key where the agent's response text is stored. Downstream agents and state transforms can read this key. Alias: ``.save_as(key)`` / ``.writes(key)``."
```

Replace with:

```toml
output_key = "Deprecated: use ``.writes(key)`` instead. Session state key where the agent's response text is stored."
```

Remove the `save_as` field doc entirely.

**Step 6: Run seed merge**

```bash
just seed
```

Expected: `seeds/seed.toml` regenerated with merged changes.

**Step 7: Commit**

```bash
git add seeds/seed.manual.toml seeds/seed.toml
git commit -m "refactor: update seed — rename guardrail→guard, delegate→agent_tool, remove save_as alias"
```

---

### Task 2: Rename helper functions in `_helpers.py`

**Files:**

- Modify: `src/adk_fluent/_helpers.py`

**Step 1: Rename `delegate_agent` to `add_agent_tool`**

Find the function at line ~207:

```python
def delegate_agent(builder, agent):
    """Wrap an agent (or builder) as an AgentTool and add it to the builder's tools list.

    This enables the coordinator pattern: the parent agent's LLM can decide
    to delegate tasks to the wrapped agent via transfer_to_agent.
    """
```

Rename to:

```python
def add_agent_tool(builder, agent):
    """Wrap an agent (or builder) as an AgentTool and add it to this agent's tools.

    The LLM can invoke the wrapped agent by name. This enables the
    coordinator pattern where a parent agent delegates to specialists.
    """
```

**Step 2: Update `_add_tools` to always append (no replace)**

Find in `_add_tools()`:

```python
        elif isinstance(tools_arg, list):
            builder._config["tools"] = tools_arg
```

Replace with:

```python
        elif isinstance(tools_arg, list):
            builder._lists.setdefault("tools", []).extend(tools_arg)
```

**Step 3: Update `__all__` export**

Find `"delegate_agent"` in `__all__` and replace with `"add_agent_tool"`.

**Step 4: Update seed.manual.toml helper_func reference**

In `seeds/seed.manual.toml`, update the `agent_tool` extra's `helper_func`:

```toml
helper_func = "add_agent_tool"
```

**Step 5: Commit**

```bash
git add src/adk_fluent/_helpers.py seeds/seed.manual.toml
git commit -m "refactor: rename delegate_agent→add_agent_tool, make .tools() always append"
```

---

### Task 3: Core renames in `_base.py`

**Files:**

- Modify: `src/adk_fluent/_base.py`

**Step 1: Remove `.retry()` and `.fallback()` methods**

Delete the entire `retry` method (lines ~1392-1395):

```python
    def retry(self, max_attempts: int = 3, backoff: float = 1.0) -> Self:
        """Configure retry behavior with exponential backoff."""
        self._config["_retry"] = {"max_attempts": max_attempts, "backoff": backoff}
        return self
```

Delete the entire `fallback` method (lines ~1397-1400):

```python
    def fallback(self, model: str) -> Self:
        """Add a fallback model to try if primary fails."""
        self._config.setdefault("_fallbacks", []).append(model)
        return self
```

**Step 2: Rename `.retry_if()` to `.loop_while()`**

Find:

```python
    def retry_if(self, predicate: Callable, *, max_retries: int = 3) -> BuilderBase:
        """Retry agent execution while predicate(state) returns True.

        Wraps in a LoopAgent + checkpoint that exits when the predicate
        becomes False. Thin wrapper over loop_until() with inverted predicate.

        Args:
            predicate: Receives state dict. Retry while this returns True.
            max_retries: Maximum number of retries (default 3).

        Usage:
            agent.retry_if(lambda s: s.get("quality") != "good", max_retries=3)
        """
        return self.loop_until(lambda s: not predicate(s), max_iterations=max_retries)
```

Replace with:

```python
    def loop_while(self, predicate: Callable, *, max_iterations: int = 3) -> BuilderBase:
        """Loop while predicate(state) returns True.

        Wraps in a LoopAgent + checkpoint that exits when the predicate
        becomes False. Natural pair with ``.loop_until()``.

        Args:
            predicate: Receives state dict. Loop continues while True.
            max_iterations: Maximum iterations (default 3).

        Usage:
            agent.loop_while(lambda s: s.get("quality") != "good", max_iterations=3)
        """
        return self.loop_until(lambda s: not predicate(s), max_iterations=max_iterations)
```

**Step 3: Rename `.inject_context()` to `.prepend()`**

Find the `inject_context` method and rename:

```python
    def prepend(self, fn: Callable) -> Self:
        """Prepend dynamic text to the LLM prompt via before_model_callback.

        The function receives the callback context and returns a string.
        That string is prepended as a content part before the LLM
        processes the request.

        Usage:
            agent.prepend(lambda ctx: f"User: {ctx.state.get('user')}")
        """

        def _inject_cb(callback_context, llm_request):
            text = fn(callback_context)
            if text:
                from google.genai import types

                part = types.Part.from_text(text=str(text))
                content = types.Content(role="user", parts=[part])
                llm_request.contents.insert(0, content)
            return None

        self._callbacks["before_model_callback"].append(_inject_cb)
        return self
```

**Step 4: Update `.timeout()` return type annotation**

Find `.timeout()` method, update its return type hint from `BuilderBase` to be more specific in the docstring (the actual return remains `BuilderBase` for compatibility, but document it):

```python
    def timeout(self, seconds: float) -> BuilderBase:
        """Wrap this agent with a time limit. Returns a ``TimedAgent`` builder.

        .. note:: Returns a new builder (not self). The builder type changes.
```

**Step 5: Update `__rshift__` error message**

Find in `__rshift__`:

```python
                    "Left side of >> dict must have .outputs() or .output_key() set "
```

Replace with:

```python
                    "Left side of >> dict must have .writes() set "
```

**Step 6: Also remove retry/fallback usage in helpers**

Search `_helpers.py` for `_retry` and `_fallbacks` config keys used in `run_one_shot_async` and update the execution path. Find where `_retry` and `_fallbacks` are read and remove the retry/fallback logic from the one-shot execution helpers. These should become no-ops or be removed.

Check `run_one_shot_async()` in `_helpers.py` — it reads `_retry` and `_fallbacks` from config. Remove those code paths.

**Step 7: Commit**

```bash
git add src/adk_fluent/_base.py src/adk_fluent/_helpers.py
git commit -m "refactor: remove .retry()/.fallback(), rename retry_if→loop_while, inject_context→prepend"
```

---

### Task 4: Rename internal builder types in `_primitive_builders.py`

**Files:**

- Modify: `src/adk_fluent/_primitive_builders.py`

**Step 1: Rename `_TimeoutBuilder` to `TimedAgent`**

Find `class _TimeoutBuilder(PrimitiveBuilderBase):` and rename to `class TimedAgent(PrimitiveBuilderBase):`.

**Step 2: Rename `_DispatchBuilder` to `BackgroundTask`**

Find `class _DispatchBuilder(PrimitiveBuilderBase):` and rename to `class BackgroundTask(PrimitiveBuilderBase):`.

**Step 3: Update all references**

Search `_base.py` for `_TimeoutBuilder` and replace with `TimedAgent`.
Search `_base.py` for `_DispatchBuilder` and replace with `BackgroundTask`.
Search `_primitive_builders.py` itself for any self-references.

**Step 4: Update `__all__` in `_primitive_builders.py`**

Add `"TimedAgent"` and `"BackgroundTask"` to `__all__`.

**Step 5: Commit**

```bash
git add src/adk_fluent/_primitive_builders.py src/adk_fluent/_base.py
git commit -m "refactor: rename _TimeoutBuilder→TimedAgent, _DispatchBuilder→BackgroundTask"
```

---

### Task 5: Cross-module cleanup — `_context.py` and `_routing.py`

**Files:**

- Modify: `src/adk_fluent/_context.py`
- Modify: `src/adk_fluent/_routing.py`

**Step 1: Remove `C.capture()` from `_context.py`**

Find the `capture` static method on the `C` class (around line 2175):

```python
    @staticmethod
    def capture(key: str) -> Callable:
        """Capture the most recent user message into state[key].

        Delegates to S.capture(key) from adk_fluent._transforms.
        """
        from adk_fluent._transforms import S

        return S.capture(key)
```

Delete this entire method.

**Step 2: Rename `template_str` parameter to `text` in `C.template()`**

Find:

```python
    @staticmethod
    def template(template_str: str) -> CTemplate:
        """Render a template string with {key} and {key?} state placeholders."""
        return CTemplate(template=template_str)
```

Replace with:

```python
    @staticmethod
    def template(text: str) -> CTemplate:
        """Render a template string with {key} and {key?} state placeholders."""
        return CTemplate(template=text)
```

**Step 3: Add `Route.gte()`, `Route.lte()`, `Route.ne()` to `_routing.py`**

After the existing `lt()` method in the `Route` class, add:

```python
    def gte(self, threshold: float | int, agent) -> Route:
        """Branch if ``float(state[key]) >= threshold``."""
        self._rules.append((lambda s, t=threshold: float(s) >= t, agent))
        return self

    def lte(self, threshold: float | int, agent) -> Route:
        """Branch if ``float(state[key]) <= threshold``."""
        self._rules.append((lambda s, t=threshold: float(s) <= t, agent))
        return self

    def ne(self, value: Any, agent) -> Route:
        """Branch if ``state[key] != value``."""
        self._rules.append((lambda s, v=value: s != v, agent))
        return self
```

**Step 4: Commit**

```bash
git add src/adk_fluent/_context.py src/adk_fluent/_routing.py
git commit -m "refactor: remove C.capture(), align C.template() param, add Route.gte/lte/ne"
```

---

### Task 6: Add `Fallback` builder to `_routing.py`

**Files:**

- Modify: `src/adk_fluent/_routing.py`

**Step 1: Add `Fallback` class**

After the `Route` class, add:

```python
class Fallback:
    """Fluent builder for fallback chains. Builder equivalent of the ``//`` operator.

    Tries each agent in order. First success wins.

    Usage::

        from adk_fluent import Fallback

        # These are equivalent:
        pipeline_a = agent_a // agent_b // agent_c
        pipeline_b = Fallback("recovery").attempt(agent_a).attempt(agent_b).attempt(agent_c)
    """

    def __init__(self, name: str = "fallback"):
        self._name = name
        self._children: list[Any] = []

    def attempt(self, agent: Any) -> Fallback:
        """Add an agent to try. Agents are tried in order; first success wins."""
        self._children.append(agent)
        return self

    def build(self) -> Any:
        """Build the fallback chain."""
        return _make_fallback_builder(self._children).build()

    def to_ir(self) -> Any:
        """Convert to IR."""
        fb = _make_fallback_builder(self._children)
        fb._config["name"] = self._name
        return fb.to_ir()

    def __floordiv__(self, other: Any) -> Fallback:
        """Support ``Fallback("f").attempt(a) // b`` syntax."""
        self._children.append(other)
        return self
```

**Step 2: Update `__all__` in `_routing.py`**

Add `"Fallback"` to `__all__`.

**Step 3: Commit**

```bash
git add src/adk_fluent/_routing.py
git commit -m "feat: add Fallback builder — .attempt() method, // operator equivalence"
```

---

### Task 7: Update exports — `prelude.py`

**Files:**

- Modify: `src/adk_fluent/prelude.py`

**Step 1: Add `Fallback` to prelude imports and `__all__`**

Add to the imports (in the appropriate tier — Tier 1 with core builders):

```python
from adk_fluent._routing import Fallback
```

Add `"Fallback"` to `__all__` in Tier 1 alongside `Agent`, `Pipeline`, `FanOut`, `Loop`.

**Step 2: Commit**

```bash
git add src/adk_fluent/prelude.py
git commit -m "feat: export Fallback from prelude"
```

---

### Task 8: Regenerate code, update `__init__.py`

**Files:**

- Regenerate: `src/adk_fluent/agent.py`, `src/adk_fluent/__init__.py`, stubs

**Step 1: Regenerate all code**

```bash
just seed && just generate
```

Expected: `agent.py` regenerated with `guard()` instead of `guardrail()`, `agent_tool()` instead of `delegate()`, deprecated aliases for `save_as`/`outputs`/`output_key`/`output_schema`/`input_schema`/`retry_if`/`inject_context`.

**Step 2: Run check-gen**

```bash
just check-gen
```

Expected: There will be diffs since we changed the seed. This is expected.

**Step 3: Lint and format**

```bash
ruff check --fix . && ruff format .
```

**Step 4: Run typecheck**

```bash
just typecheck-core
```

Expected: 0 errors. Fix any issues.

**Step 5: Commit**

```bash
git add src/adk_fluent/agent.py src/adk_fluent/agent.pyi src/adk_fluent/__init__.py seeds/
git commit -m "chore: regenerate code with verb harmonization changes"
```

---

### Task 9: Migrate all tests and examples

This is the largest task — 142+ usages across tests and examples need updating.

**Files:**

- Modify: All files in `tests/` and `examples/` that use old method names.

**Step 1: Automated find-and-replace**

Run these replacements across `tests/` and `examples/`:

```bash
# .save_as() → .writes()
find tests/ examples/ -name '*.py' -exec sed -i 's/\.save_as(/\.writes(/g' {} +

# .output_key( → .writes(  (method calls only, not field references)
find tests/ examples/ -name '*.py' -exec sed -i 's/\.output_key(/\.writes(/g' {} +

# .outputs( → .writes(
find tests/ examples/ -name '*.py' -exec sed -i 's/\.outputs(/\.writes(/g' {} +

# .output_schema( → .returns(
find tests/ examples/ -name '*.py' -exec sed -i 's/\.output_schema(/\.returns(/g' {} +

# .input_schema( → .accepts(
find tests/ examples/ -name '*.py' -exec sed -i 's/\.input_schema(/\.accepts(/g' {} +

# .retry_if( → .loop_while(
find tests/ examples/ -name '*.py' -exec sed -i 's/\.retry_if(/\.loop_while(/g' {} +

# .inject_context( → .prepend(
find tests/ examples/ -name '*.py' -exec sed -i 's/\.inject_context(/\.prepend(/g' {} +

# .guardrail( → .guard(
find tests/ examples/ -name '*.py' -exec sed -i 's/\.guardrail(/\.guard(/g' {} +

# .delegate( → .agent_tool(
find tests/ examples/ -name '*.py' -exec sed -i 's/\.delegate(/\.agent_tool(/g' {} +

# C.capture( → S.capture(
find tests/ examples/ -name '*.py' -exec sed -i 's/C\.capture(/S\.capture(/g' {} +

# max_retries= → max_iterations= (in loop_while context)
find tests/ examples/ -name '*.py' -exec sed -i 's/max_retries=/max_iterations=/g' {} +
```

**Step 2: Handle `.retry()` removals manually**

Find all `.retry(` usages in tests and examples. The test file `tests/manual/test_retry.py` needs manual rewriting:

- Tests for `.retry()` and `.fallback()` model-level behavior should be **removed** (these methods no longer exist)
- Tests for `M.retry()` middleware should remain

**Step 3: Handle cookbook renames**

- Rename `examples/cookbook/38_retry_if.py` to `examples/cookbook/38_loop_while.py`
- Rename `examples/cookbook/12_guardrails.py` to `examples/cookbook/12_guards.py`
- Rename `examples/cookbook/27_delegate_pattern.py` to `examples/cookbook/27_agent_tool_pattern.py`
- Rename `examples/retry_if/` to `examples/loop_while/`
- Rename `examples/guardrails/` to `examples/guards/`
- Rename `examples/delegate_pattern/` to `examples/agent_tool_pattern/`

**Step 4: Update string references in test assertions and docstrings**

Search for string mentions of old names in test assertions, comments, and docstrings:

```bash
grep -rn "save_as\|output_key\|retry_if\|inject_context\|guardrail\|delegate" tests/ examples/ --include='*.py'
```

Fix any remaining references (assertion strings, docstrings, comments).

**Step 5: Lint and format**

```bash
ruff check --fix . && ruff format .
```

**Step 6: Run tests**

```bash
uv run pytest tests/ -x --tb=short -q
```

Expected: All tests pass. Fix any failures.

**Step 7: Run cookbooks**

```bash
uv run pytest examples/cookbook/ -q
```

Expected: All 66+ cookbooks pass.

**Step 8: Commit**

```bash
git add tests/ examples/
git commit -m "refactor: migrate all tests and examples to harmonized verb names"
```

---

### Task 10: Write tests for new features and full verification

**Files:**

- Create: `tests/manual/test_verb_harmonization.py`
- Modify: `tests/manual/test_api_surface_v2.py`

**Step 1: Write tests for Fallback builder**

```python
"""Tests for verb harmonization — new features and removed methods."""

from __future__ import annotations

import pytest


class TestFallbackBuilder:
    def test_fallback_attempt_builds(self):
        from adk_fluent import Agent, Fallback

        a = Agent("a", "gemini-2.5-flash").instruct("Try A.")
        b = Agent("b", "gemini-2.5-flash").instruct("Try B.")
        fb = Fallback("recovery").attempt(a).attempt(b)
        built = fb.build()
        assert built.name == "recovery"
        assert len(built.sub_agents) == 2

    def test_fallback_attempt_to_ir(self):
        from adk_fluent import Agent, Fallback

        a = Agent("a", "gemini-2.5-flash").instruct("A.")
        b = Agent("b", "gemini-2.5-flash").instruct("B.")
        ir = Fallback("fb").attempt(a).attempt(b).to_ir()
        assert ir.name == "fb"

    def test_fallback_equivalence_with_operator(self):
        from adk_fluent import Agent, Fallback

        a = Agent("a", "gemini-2.5-flash").instruct("A.")
        b = Agent("b", "gemini-2.5-flash").instruct("B.")
        op_built = (a // b).build()
        builder_built = Fallback("fb").attempt(a).attempt(b).build()
        assert len(op_built.sub_agents) == len(builder_built.sub_agents)


class TestRouteNewOperators:
    def test_route_gte(self):
        from adk_fluent import Agent, Route

        a = Agent("a", "gemini-2.5-flash").instruct("A.")
        r = Route("score").gte(0.8, a)
        assert len(r._rules) == 1

    def test_route_lte(self):
        from adk_fluent import Agent, Route

        a = Agent("a", "gemini-2.5-flash").instruct("A.")
        r = Route("score").lte(0.2, a)
        assert len(r._rules) == 1

    def test_route_ne(self):
        from adk_fluent import Agent, Route

        a = Agent("a", "gemini-2.5-flash").instruct("A.")
        r = Route("status").ne("failed", a)
        assert len(r._rules) == 1


class TestRemovedMethods:
    def test_save_as_raises(self):
        from adk_fluent import Agent

        agent = Agent("test", "gemini-2.5-flash")
        with pytest.raises((AttributeError, DeprecationWarning)):
            agent.save_as("key")

    def test_writes_works(self):
        from adk_fluent import Agent

        agent = Agent("test", "gemini-2.5-flash").writes("key")
        assert agent._config["output_key"] == "key"


class TestRenamedMethods:
    def test_loop_while(self):
        from adk_fluent import Agent

        result = Agent("test", "gemini-2.5-flash").instruct("Test.").loop_while(
            lambda s: s.get("done") != "yes", max_iterations=3
        )
        assert result._config.get("max_iterations") == 3

    def test_guard(self):
        from adk_fluent import Agent

        def my_guard(ctx, req):
            return None

        agent = Agent("test", "gemini-2.5-flash").guard(my_guard)
        assert my_guard in agent._callbacks["before_model_callback"]
        assert my_guard in agent._callbacks["after_model_callback"]

    def test_agent_tool(self):
        from adk_fluent import Agent

        specialist = Agent("spec", "gemini-2.5-flash").instruct("Specialize.")
        coordinator = Agent("coord", "gemini-2.5-flash").agent_tool(specialist)
        assert len(coordinator._lists["tools"]) == 1

    def test_prepend(self):
        from adk_fluent import Agent

        agent = Agent("test", "gemini-2.5-flash").prepend(lambda ctx: "extra")
        assert len(agent._callbacks["before_model_callback"]) == 1


class TestToolsAlwaysAppend:
    def test_tools_list_appends(self):
        from adk_fluent import Agent

        def fn_a(x: str) -> str:
            return x

        def fn_b(x: str) -> str:
            return x

        agent = Agent("test", "gemini-2.5-flash").tool(fn_a).tools([fn_b])
        # Both should be present (tools appends, not replaces)
        assert len(agent._lists["tools"]) == 2


class TestFallbackExport:
    def test_fallback_in_prelude(self):
        from adk_fluent.prelude import Fallback

        assert Fallback is not None

    def test_fallback_in_init(self):
        from adk_fluent import Fallback

        assert Fallback is not None
```

**Step 2: Update API surface test**

In `tests/manual/test_api_surface_v2.py`, update the expected prelude exports count and add `Fallback` to the expected set.

**Step 3: Run all tests**

```bash
uv run pytest tests/ -x --tb=short -q
```

**Step 4: Run full verification suite**

```bash
just preflight
just typecheck-core
just check-gen
uv run pytest examples/cookbook/ -q
```

**Step 5: Verify no old names remain in src/**

```bash
grep -rn "save_as\|\.output_key(\|\.outputs(\|\.output_schema(\|\.input_schema(\|\.retry_if(\|\.inject_context(\|\.guardrail(\|\.delegate(" src/adk_fluent/ --include='*.py' | grep -v deprecated | grep -v "removed\|# old"
```

Expected: Only hits in deprecated alias stubs (which emit warnings).

**Step 6: Commit**

```bash
git add tests/ src/
git commit -m "test: add verb harmonization tests, verify clean API surface"
```

---

### Task Summary

| Task | What | Files | Risk |
|---|---|---|---|
| 1 | Update seed.manual.toml | seeds/ | Low |
| 2 | Rename helpers | _helpers.py, seeds/ | Low |
| 3 | Core renames in _base.py | _base.py, _helpers.py | Medium |
| 4 | Rename internal types | _primitive_builders.py, _base.py | Low |
| 5 | Cross-module cleanup | _context.py, _routing.py | Low |
| 6 | Add Fallback builder | _routing.py | Low |
| 7 | Update prelude exports | prelude.py | Low |
| 8 | Regenerate code | agent.py, __init__.py | Medium |
| 9 | Migrate tests/examples | tests/, examples/ | High (volume) |
| 10 | New tests + verification | tests/, full suite | Medium |
