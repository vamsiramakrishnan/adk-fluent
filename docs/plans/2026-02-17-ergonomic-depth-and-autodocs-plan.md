# Ergonomic Depth Features + Auto-Generated Documentation — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add runtime shortcut features (`.ask()`, `.stream()`, `.clone()`, `.test()`, `.guardrail()`, `.session()`, variadic/conditional callbacks) to adk-fluent builders, plus an auto-generated documentation system (API reference, cookbook, migration guide) integrated into the justfile pipeline.

**Architecture:** Hand-written `_helpers.py` module provides runtime implementations. The generator is extended with new `behavior` types that import and delegate to helpers. A new `scripts/doc_generator.py` reads manifest + seed + annotated cookbook examples to emit Markdown docs. Everything is wired into `just docs`.

**Tech Stack:** Python 3.11+, google-adk >= 1.20.0, pytest, TOML (seed), JSON (manifest), Markdown (docs output).

______________________________________________________________________

## Group 1: Runtime Helpers — Clone & Callback Combinators (TDD)

These are pure-logic features with no external dependencies. Full TDD.

### Task 1: Test and implement `.clone()` helper

**Files:**

- Create: `tests/manual/test_clone.py`
- Create: `src/adk_fluent/_helpers.py`

**Step 1: Write the failing test**

```python
# tests/manual/test_clone.py
"""Tests for builder .clone() functionality."""
import pytest
from adk_fluent.agent import Agent


class TestClone:
    def test_clone_returns_new_builder(self):
        """Clone returns a different builder instance."""
        original = Agent("orig").instruct("Be helpful.")
        cloned = original.clone("copy")
        assert cloned is not original

    def test_clone_has_new_name(self):
        """Cloned builder has the new name."""
        original = Agent("orig").instruct("Be helpful.")
        cloned = original.clone("copy")
        assert cloned._config["name"] == "copy"

    def test_clone_preserves_config(self):
        """Cloned builder copies config from original."""
        original = Agent("orig").instruct("Be helpful.").model("gemini-2.5-flash")
        cloned = original.clone("copy")
        assert cloned._config["instruction"] == "Be helpful."
        assert cloned._config["model"] == "gemini-2.5-flash"

    def test_clone_is_deep_copy(self):
        """Modifying clone does not affect original."""
        original = Agent("orig").instruct("Be helpful.")
        cloned = original.clone("copy").instruct("Be different.")
        assert original._config["instruction"] == "Be helpful."
        assert cloned._config["instruction"] == "Be different."

    def test_clone_copies_callbacks(self):
        """Cloned builder has copies of accumulated callbacks."""
        fn1 = lambda ctx: None
        original = Agent("orig").before_model(fn1)
        cloned = original.clone("copy")
        assert fn1 in cloned._callbacks["before_model_callback"]
        # Modifying clone's callbacks doesn't affect original
        fn2 = lambda ctx: None
        cloned.before_model(fn2)
        assert fn2 not in original._callbacks["before_model_callback"]

    def test_clone_copies_lists(self):
        """Cloned builder has copies of accumulated lists."""
        def my_tool(x: str) -> str:
            return x
        original = Agent("orig").tool(my_tool)
        cloned = original.clone("copy")
        assert my_tool in cloned._lists["tools"]

    def test_clone_returns_self_type(self):
        """Clone returns the same builder class for chaining."""
        original = Agent("orig").instruct("test")
        cloned = original.clone("copy")
        assert type(cloned) == type(original)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/manual/test_clone.py -v`
Expected: FAIL — `Agent` has no `.clone()` method.

**Step 3: Write minimal implementation**

```python
# src/adk_fluent/_helpers.py
"""
Runtime helpers for adk-fluent ergonomic features.

These are hand-written (not generated) and imported by generated builders.
"""
from __future__ import annotations

import copy
from typing import Any, Callable


def deep_clone_builder(builder: Any, new_name: str) -> Any:
    """Deep-copy a builder's internal state and set a new name.

    Returns a new builder of the same type with independent config,
    callbacks, and lists.
    """
    new_builder = object.__new__(type(builder))
    new_builder._config = copy.deepcopy(builder._config)
    new_builder._callbacks = copy.deepcopy(builder._callbacks)
    new_builder._lists = copy.deepcopy(builder._lists)
    new_builder._config["name"] = new_name
    return new_builder
```

Then add the `.clone()` method directly to the Agent class in `src/adk_fluent/agent.py`. Insert after the `# --- Extra methods ---` section, before `# --- Dynamic field forwarding ---`:

```python
    def clone(self, new_name: str) -> Self:
        """Deep-copy this builder with a new name. Independent config/callbacks/lists."""
        from adk_fluent._helpers import deep_clone_builder
        return deep_clone_builder(self, new_name)
```

**Important:** Since `agent.py` is auto-generated, we need to add `.clone()` via the generator (Task 7). For now, manually add it to verify tests pass, then we'll make the generator emit it.

**Step 4: Run test to verify it passes**

Run: `pytest tests/manual/test_clone.py -v`
Expected: All 7 tests PASS.

**Step 5: Commit**

```bash
git add tests/manual/test_clone.py src/adk_fluent/_helpers.py
git commit -m "feat: add clone() helper with deep-copy semantics"
```

______________________________________________________________________

### Task 2: Test and implement variadic callback methods

**Files:**

- Create: `tests/manual/test_variadic_callbacks.py`
- Modify: `src/adk_fluent/agent.py` (temporarily, until generator handles it)

**Step 1: Write the failing test**

```python
# tests/manual/test_variadic_callbacks.py
"""Tests for variadic callback methods."""
from adk_fluent.agent import Agent


class TestVariadicCallbacks:
    def test_single_callback_still_works(self):
        """Single callback argument still works as before."""
        fn = lambda ctx: None
        builder = Agent("a").before_model(fn)
        assert builder._callbacks["before_model_callback"] == [fn]

    def test_multiple_callbacks_in_one_call(self):
        """Multiple callbacks can be passed in a single call."""
        fn1 = lambda ctx: None
        fn2 = lambda ctx: None
        fn3 = lambda ctx: None
        builder = Agent("a").before_model(fn1, fn2, fn3)
        assert builder._callbacks["before_model_callback"] == [fn1, fn2, fn3]

    def test_variadic_chaining(self):
        """Variadic callbacks chain with subsequent calls."""
        fn1 = lambda ctx: None
        fn2 = lambda ctx: None
        fn3 = lambda ctx: None
        builder = Agent("a").before_model(fn1, fn2).before_model(fn3)
        assert builder._callbacks["before_model_callback"] == [fn1, fn2, fn3]

    def test_variadic_returns_self(self):
        """Variadic callback still returns self for chaining."""
        fn1 = lambda ctx: None
        fn2 = lambda ctx: None
        builder = Agent("a")
        result = builder.before_model(fn1, fn2)
        assert result is builder

    def test_all_callback_aliases_support_variadic(self):
        """Every callback alias method accepts multiple args."""
        fn1 = lambda ctx: None
        fn2 = lambda ctx: None
        builder = Agent("a")
        builder.after_model(fn1, fn2)
        builder.before_tool(fn1, fn2)
        builder.after_tool(fn1, fn2)
        assert len(builder._callbacks["after_model_callback"]) == 2
        assert len(builder._callbacks["before_tool_callback"]) == 2
        assert len(builder._callbacks["after_tool_callback"]) == 2
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/manual/test_variadic_callbacks.py -v`
Expected: FAIL — `.before_model()` only accepts 1 positional arg.

**Step 3: Modify generator to emit variadic callbacks**

In `scripts/generator.py`, change `gen_callback_methods`:

```python
def gen_callback_methods(spec: BuilderSpec) -> str:
    """Generate additive callback methods with variadic support."""
    methods = []

    for short_name, full_name in spec.callback_aliases.items():
        methods.append(f'''
    def {short_name}(self, *fns: Callable) -> Self:
        """Append callback(s) to `{full_name}`. Multiple calls accumulate."""
        for fn in fns:
            self._callbacks["{full_name}"].append(fn)
        return self
''')

    return "\n".join(methods)
```

**Step 4: Regenerate code and run tests**

Run: `python scripts/generator.py seeds/seed.toml manifest.json --output-dir src/adk_fluent --test-dir tests/generated`
Run: `pytest tests/manual/test_variadic_callbacks.py -v`
Expected: All 5 tests PASS.

**Step 5: Run full test suite to ensure no regressions**

Run: `pytest tests/ -v --tb=short`
Expected: All existing tests still pass.

**Step 6: Commit**

```bash
git add scripts/generator.py tests/manual/test_variadic_callbacks.py
git commit -m "feat: variadic callback methods — .before_model(fn1, fn2, fn3)"
```

______________________________________________________________________

### Task 3: Test and implement `.guardrail()` method

**Files:**

- Create: `tests/manual/test_guardrail.py`
- Modify: `scripts/generator.py` (add dual_callback behavior)
- Modify: `seeds/seed.toml` (add guardrail extra to Agent)

**Step 1: Write the failing test**

```python
# tests/manual/test_guardrail.py
"""Tests for .guardrail() dual-callback method."""
from adk_fluent.agent import Agent


class TestGuardrail:
    def test_guardrail_registers_before_and_after(self):
        """guardrail() registers fn as both before_model and after_model callback."""
        fn = lambda ctx: None
        builder = Agent("a").guardrail(fn)
        assert fn in builder._callbacks["before_model_callback"]
        assert fn in builder._callbacks["after_model_callback"]

    def test_guardrail_chaining(self):
        """guardrail() returns self for chaining."""
        fn = lambda ctx: None
        builder = Agent("a")
        result = builder.guardrail(fn)
        assert result is builder

    def test_multiple_guardrails(self):
        """Multiple guardrails accumulate."""
        fn1 = lambda ctx: None
        fn2 = lambda ctx: None
        builder = Agent("a").guardrail(fn1).guardrail(fn2)
        assert builder._callbacks["before_model_callback"] == [fn1, fn2]
        assert builder._callbacks["after_model_callback"] == [fn1, fn2]

    def test_guardrail_with_other_callbacks(self):
        """guardrail() works alongside explicit before/after callbacks."""
        guard = lambda ctx: None
        before = lambda ctx: None
        builder = Agent("a").before_model(before).guardrail(guard)
        assert builder._callbacks["before_model_callback"] == [before, guard]
        assert builder._callbacks["after_model_callback"] == [guard]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/manual/test_guardrail.py -v`
Expected: FAIL — Agent has no `.guardrail()` method.

**Step 3: Add guardrail extra to seed.toml**

Add to `seeds/seed.toml` under `[builders.Agent]`, after the existing `extras`:

```toml
[[builders.Agent.extras]]
name = "guardrail"
signature = "(self, fn: Callable) -> Self"
doc = "Attach a guardrail function as both before_model and after_model callback."
behavior = "dual_callback"
target_fields = ["before_model_callback", "after_model_callback"]
```

**Step 4: Extend generator to handle `dual_callback` behavior**

In `scripts/generator.py`, in `gen_extra_methods`, add a new behavior branch:

```python
        elif behavior == "dual_callback":
            target_fields = extra.get("target_fields", [])
            param_name = sig.split("self, ")[1].split(":")[0].strip() if "self, " in sig else "fn"
            append_lines = "\n".join(
                f'        self._callbacks["{tf}"].append({param_name})'
                for tf in target_fields
            )
            body = f'''
        {append_lines}
        return self'''
```

**Step 5: Regenerate code**

Run: `python scripts/generator.py seeds/seed.toml manifest.json --output-dir src/adk_fluent --test-dir tests/generated`

**Step 6: Run tests**

Run: `pytest tests/manual/test_guardrail.py -v`
Expected: All 4 tests PASS.

Run: `pytest tests/ -v --tb=short`
Expected: No regressions.

**Step 7: Commit**

```bash
git add scripts/generator.py seeds/seed.toml tests/manual/test_guardrail.py
git commit -m "feat: add .guardrail() dual-callback method for Agent builder"
```

______________________________________________________________________

### Task 4: Test and implement conditional callbacks (`.before_model_if()`)

**Files:**

- Create: `tests/manual/test_conditional_callbacks.py`
- Modify: `scripts/generator.py` (emit `_if` variants)

**Step 1: Write the failing test**

```python
# tests/manual/test_conditional_callbacks.py
"""Tests for conditional callback methods (_if variants)."""
from adk_fluent.agent import Agent


class TestConditionalCallbacks:
    def test_if_true_registers_callback(self):
        """When condition is True, callback is registered."""
        fn = lambda ctx: None
        builder = Agent("a").before_model_if(True, fn)
        assert fn in builder._callbacks["before_model_callback"]

    def test_if_false_skips_callback(self):
        """When condition is False, callback is NOT registered."""
        fn = lambda ctx: None
        builder = Agent("a").before_model_if(False, fn)
        assert fn not in builder._callbacks.get("before_model_callback", [])

    def test_if_returns_self(self):
        """Conditional callback returns self for chaining regardless of condition."""
        fn = lambda ctx: None
        builder = Agent("a")
        result = builder.before_model_if(True, fn)
        assert result is builder
        result2 = builder.before_model_if(False, fn)
        assert result2 is builder

    def test_if_works_for_all_callback_aliases(self):
        """Every callback alias has an _if variant."""
        fn = lambda ctx: None
        builder = Agent("a")
        builder.after_model_if(True, fn)
        builder.before_tool_if(True, fn)
        builder.after_tool_if(True, fn)
        assert len(builder._callbacks["after_model_callback"]) == 1
        assert len(builder._callbacks["before_tool_callback"]) == 1
        assert len(builder._callbacks["after_tool_callback"]) == 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/manual/test_conditional_callbacks.py -v`
Expected: FAIL — Agent has no `.before_model_if()` method.

**Step 3: Extend generator to emit `_if` variants**

In `scripts/generator.py`, extend `gen_callback_methods` to also emit conditional variants:

```python
def gen_callback_methods(spec: BuilderSpec) -> str:
    """Generate additive callback methods with variadic and conditional support."""
    methods = []

    for short_name, full_name in spec.callback_aliases.items():
        # Variadic version
        methods.append(f'''
    def {short_name}(self, *fns: Callable) -> Self:
        """Append callback(s) to `{full_name}`. Multiple calls accumulate."""
        for fn in fns:
            self._callbacks["{full_name}"].append(fn)
        return self
''')
        # Conditional version
        methods.append(f'''
    def {short_name}_if(self, condition: bool, fn: Callable) -> Self:
        """Append callback to `{full_name}` only if condition is True."""
        if condition:
            self._callbacks["{full_name}"].append(fn)
        return self
''')

    return "\n".join(methods)
```

**Step 4: Regenerate code and run tests**

Run: `python scripts/generator.py seeds/seed.toml manifest.json --output-dir src/adk_fluent --test-dir tests/generated`
Run: `pytest tests/manual/test_conditional_callbacks.py -v`
Expected: All 4 tests PASS.

**Step 5: Commit**

```bash
git add scripts/generator.py tests/manual/test_conditional_callbacks.py
git commit -m "feat: conditional callback methods — .before_model_if(cond, fn)"
```

______________________________________________________________________

### Task 5: Wire `.clone()` into the generator

Now that `.clone()` works via manual insertion (Task 1), make the generator emit it automatically.

**Files:**

- Modify: `scripts/generator.py` (add `deep_copy` behavior)
- Modify: `seeds/seed.toml` (add clone extra to Agent, Pipeline, FanOut, Loop)

**Step 1: Add clone extras to seed.toml**

Add to each of `[builders.Agent]`, `[builders.Pipeline]`, `[builders.FanOut]`, and `[builders.Loop]`:

```toml
[[builders.Agent.extras]]
name = "clone"
signature = "(self, new_name: str) -> Self"
doc = "Deep-copy this builder with a new name. Independent config/callbacks/lists."
behavior = "deep_copy"

[[builders.Pipeline.extras]]
name = "clone"
signature = "(self, new_name: str) -> Self"
doc = "Deep-copy this builder with a new name."
behavior = "deep_copy"

[[builders.FanOut.extras]]
name = "clone"
signature = "(self, new_name: str) -> Self"
doc = "Deep-copy this builder with a new name."
behavior = "deep_copy"

[[builders.Loop.extras]]
name = "clone"
signature = "(self, new_name: str) -> Self"
doc = "Deep-copy this builder with a new name."
behavior = "deep_copy"
```

**Step 2: Add deep_copy behavior to generator**

In `scripts/generator.py`, in `gen_extra_methods`, add:

```python
        elif behavior == "deep_copy":
            param_name = sig.split("self, ")[1].split(":")[0].strip() if "self, " in sig else "new_name"
            body = f'''
        from adk_fluent._helpers import deep_clone_builder
        return deep_clone_builder(self, {param_name})'''
```

**Step 3: Regenerate code and verify**

Run: `python scripts/generator.py seeds/seed.toml manifest.json --output-dir src/adk_fluent --test-dir tests/generated`
Run: `pytest tests/manual/test_clone.py -v`
Expected: All 7 tests still PASS.

**Step 4: Verify Pipeline/FanOut/Loop also got `.clone()`**

```bash
grep -n "def clone" src/adk_fluent/agent.py src/adk_fluent/workflow.py
```

Expected: `.clone()` appears in both files.

**Step 5: Commit**

```bash
git add scripts/generator.py seeds/seed.toml
git commit -m "feat: generate .clone() for Agent, Pipeline, FanOut, Loop builders"
```

______________________________________________________________________

## Group 2: Runtime Helpers — Ask, Stream, Test, Session

These features require ADK runtime (InMemoryRunner, sessions). Tests need mocking or real ADK.

### Task 6: Implement `.ask()` and `.ask_async()` helpers

**Files:**

- Modify: `src/adk_fluent/_helpers.py`
- Create: `tests/manual/test_ask.py`
- Modify: `seeds/seed.toml` (add ask/ask_async terminals to Agent)
- Modify: `scripts/generator.py` (handle runtime_terminal behavior)

**Step 1: Write the test**

```python
# tests/manual/test_ask.py
"""Tests for .ask() one-shot execution."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from adk_fluent.agent import Agent


class TestAskBuilderMechanics:
    def test_ask_exists_on_agent(self):
        """Agent builder has .ask() method."""
        builder = Agent("test").instruct("test")
        assert hasattr(builder, "ask")
        assert callable(builder.ask)

    def test_ask_async_exists_on_agent(self):
        """Agent builder has .ask_async() method."""
        builder = Agent("test").instruct("test")
        assert hasattr(builder, "ask_async")
        assert callable(builder.ask_async)
```

**Step 2: Add implementation to `_helpers.py`**

```python
import asyncio

async def run_one_shot_async(builder: Any, prompt: str) -> str:
    """Execute a builder as a one-shot agent and return the text response.

    Internally: build() → InMemoryRunner → create session → send message → collect response.
    """
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    agent = builder.build()
    app_name = f"_ask_{agent.name}"
    runner = InMemoryRunner(agent=agent, app_name=app_name)
    session = await runner.session_service.create_session(
        app_name=app_name, user_id="_ask_user"
    )
    content = types.Content(
        role="user", parts=[types.Part(text=prompt)]
    )

    last_text = ""
    async for event in runner.run_async(
        user_id="_ask_user", session_id=session.id, new_message=content
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    last_text = part.text

    return last_text


def run_one_shot(builder: Any, prompt: str) -> str:
    """Synchronous wrapper around run_one_shot_async."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, run_one_shot_async(builder, prompt)).result()
    else:
        return asyncio.run(run_one_shot_async(builder, prompt))
```

**Step 3: Add ask/ask_async to seed.toml for Agent**

```toml
[[builders.Agent.extras]]
name = "ask"
signature = "(self, prompt: str) -> str"
doc = "One-shot execution. Build agent, send prompt, return response text."
behavior = "runtime_helper"
helper_func = "run_one_shot"

[[builders.Agent.extras]]
name = "ask_async"
signature = "(self, prompt: str) -> str"
doc = "Async one-shot execution. Build agent, send prompt, return response text."
behavior = "runtime_helper_async"
helper_func = "run_one_shot_async"
```

**Step 4: Add runtime_helper behavior to generator**

In `scripts/generator.py`, in `gen_extra_methods`:

```python
        elif behavior == "runtime_helper":
            helper_func = extra.get("helper_func", name)
            param_name = "prompt"  # Extract from signature
            body = f'''
        from adk_fluent._helpers import {helper_func}
        return {helper_func}(self, {param_name})'''
        elif behavior == "runtime_helper_async":
            helper_func = extra.get("helper_func", name)
            param_name = "prompt"
            body = f'''
        from adk_fluent._helpers import {helper_func}
        return await {helper_func}(self, {param_name})'''
```

Note: The `ask_async` method needs `async def`. Adjust generator to detect `_async` suffix or `runtime_helper_async` behavior and emit `async def` instead of `def`.

**Step 5: Regenerate and run tests**

Run: `python scripts/generator.py seeds/seed.toml manifest.json --output-dir src/adk_fluent --test-dir tests/generated`
Run: `pytest tests/manual/test_ask.py -v`
Expected: PASS for builder mechanics tests.

**Step 6: Commit**

```bash
git add src/adk_fluent/_helpers.py tests/manual/test_ask.py seeds/seed.toml scripts/generator.py
git commit -m "feat: add .ask() and .ask_async() one-shot execution"
```

______________________________________________________________________

### Task 7: Implement `.stream()` helper

**Files:**

- Modify: `src/adk_fluent/_helpers.py`
- Create: `tests/manual/test_stream.py`
- Modify: `seeds/seed.toml`

**Step 1: Write the test**

```python
# tests/manual/test_stream.py
"""Tests for .stream() streaming execution."""
from adk_fluent.agent import Agent


class TestStreamBuilderMechanics:
    def test_stream_exists_on_agent(self):
        """Agent builder has .stream() method."""
        builder = Agent("test").instruct("test")
        assert hasattr(builder, "stream")
        assert callable(builder.stream)
```

**Step 2: Add implementation to `_helpers.py`**

```python
from typing import AsyncIterator

async def run_stream(builder: Any, prompt: str) -> AsyncIterator[str]:
    """Stream text chunks from a one-shot agent execution.

    Yields text parts as they arrive from the runner event stream.
    """
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    agent = builder.build()
    app_name = f"_stream_{agent.name}"
    runner = InMemoryRunner(agent=agent, app_name=app_name)
    session = await runner.session_service.create_session(
        app_name=app_name, user_id="_stream_user"
    )
    content = types.Content(
        role="user", parts=[types.Part(text=prompt)]
    )

    async for event in runner.run_async(
        user_id="_stream_user", session_id=session.id, new_message=content
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    yield part.text
```

**Step 3: Add stream extra to seed.toml**

```toml
[[builders.Agent.extras]]
name = "stream"
signature = "(self, prompt: str) -> AsyncIterator[str]"
doc = "Streaming execution. Yields response text chunks as they arrive."
behavior = "runtime_helper_async_gen"
helper_func = "run_stream"
```

**Step 4: Add `runtime_helper_async_gen` behavior to generator**

This needs to emit `async def` that returns an async generator:

```python
        elif behavior == "runtime_helper_async_gen":
            helper_func = extra.get("helper_func", name)
            param_name = "prompt"
            body = f'''
        from adk_fluent._helpers import {helper_func}
        async for chunk in {helper_func}(self, {param_name}):
            yield chunk'''
```

**Step 5: Regenerate, test, commit**

Run: `python scripts/generator.py seeds/seed.toml manifest.json --output-dir src/adk_fluent --test-dir tests/generated`
Run: `pytest tests/manual/test_stream.py -v`

```bash
git add src/adk_fluent/_helpers.py tests/manual/test_stream.py seeds/seed.toml scripts/generator.py
git commit -m "feat: add .stream() async generator for streaming responses"
```

______________________________________________________________________

### Task 8: Implement `.test()` method

**Files:**

- Modify: `src/adk_fluent/_helpers.py`
- Create: `tests/manual/test_inline_test.py`
- Modify: `seeds/seed.toml`

**Step 1: Write the test**

```python
# tests/manual/test_inline_test.py
"""Tests for .test() inline testing method — builder mechanics only."""
from adk_fluent.agent import Agent


class TestInlineTestMechanics:
    def test_method_exists(self):
        """Agent builder has .test() method."""
        builder = Agent("test").instruct("test")
        assert hasattr(builder, "test")
        assert callable(builder.test)

    def test_returns_self(self):
        """test() returns self for chaining (when mocked)."""
        # Full test() requires LLM, so we just verify the method signature
        builder = Agent("test").instruct("test")
        # Can't call .test() without LLM, but verify it's there
        import inspect
        sig = inspect.signature(builder.test)
        assert "prompt" in sig.parameters
```

**Step 2: Add implementation to `_helpers.py`**

```python
import re

def run_inline_test(builder: Any, prompt: str, *,
                    contains: str | None = None,
                    matches: str | None = None,
                    equals: str | None = None) -> Any:
    """Run a smoke test against this agent configuration.

    Calls .ask() internally, asserts the output matches the condition.
    Returns the builder for chaining.
    """
    response = run_one_shot(builder, prompt)

    if contains is not None and contains not in response:
        raise AssertionError(
            f"Agent '{builder._config.get('name', '?')}' test failed:\n"
            f"  prompt:   {prompt!r}\n"
            f"  expected: contains {contains!r}\n"
            f"  got:      {response!r}"
        )
    if matches is not None and not re.search(matches, response):
        raise AssertionError(
            f"Agent '{builder._config.get('name', '?')}' test failed:\n"
            f"  prompt:   {prompt!r}\n"
            f"  expected: matches {matches!r}\n"
            f"  got:      {response!r}"
        )
    if equals is not None and response.strip() != equals.strip():
        raise AssertionError(
            f"Agent '{builder._config.get('name', '?')}' test failed:\n"
            f"  prompt:   {prompt!r}\n"
            f"  expected: {equals!r}\n"
            f"  got:      {response!r}"
        )

    return builder
```

**Step 3: Add test extra to seed.toml**

```toml
[[builders.Agent.extras]]
name = "test"
signature = "(self, prompt: str, *, contains: str | None = None, matches: str | None = None, equals: str | None = None) -> Self"
doc = "Run a smoke test. Calls .ask() internally, asserts output matches condition."
behavior = "runtime_helper"
helper_func = "run_inline_test"
```

**Step 4: Adjust generator for complex signatures**

The `runtime_helper` behavior needs to forward all params, not just `prompt`. Update generator to parse the signature and forward correctly:

```python
        elif behavior == "runtime_helper":
            helper_func = extra.get("helper_func", name)
            # Extract param names from signature (everything between parens minus self)
            sig_inner = sig.split("(self, ")[1].rstrip(")")  if "self, " in sig else ""
            param_names = []
            for part in sig_inner.split(","):
                part = part.strip()
                if not part:
                    continue
                pname = part.split(":")[0].strip().lstrip("*")
                if pname:
                    param_names.append(pname)
            fwd = ", ".join(f"{p}={p}" if "=" in sig_inner.split(p)[1].split(",")[0] if p in sig_inner else "" else p for p in param_names)
            # Simplified: just forward all named params
            body = f'''
        from adk_fluent._helpers import {helper_func}
        return {helper_func}(self, {", ".join(param_names)})'''
```

Actually, this is getting complex. Simpler approach: just forward `**kwargs` from the signature:

```python
        elif behavior == "runtime_helper":
            helper_func = extra.get("helper_func", name)
            # Parse params from signature
            if "self, " in sig:
                params_str = sig.split("(self, ", 1)[1].rsplit(")", 1)[0]
            else:
                params_str = ""
            # Extract positional and keyword params
            params = []
            for p in params_str.split(","):
                p = p.strip()
                if not p:
                    continue
                if p == "*":
                    continue
                pname = p.split(":")[0].strip().lstrip("*")
                params.append(pname)
            args_fwd = ", ".join(params)
            body = f'''
        from adk_fluent._helpers import {helper_func}
        return {helper_func}(self, {args_fwd})'''
```

**Step 5: Regenerate, test, commit**

Run: `python scripts/generator.py seeds/seed.toml manifest.json --output-dir src/adk_fluent --test-dir tests/generated`
Run: `pytest tests/manual/test_inline_test.py -v`

```bash
git add src/adk_fluent/_helpers.py tests/manual/test_inline_test.py seeds/seed.toml scripts/generator.py
git commit -m "feat: add .test() inline agent testing method"
```

______________________________________________________________________

### Task 9: Implement `.session()` context manager

**Files:**

- Modify: `src/adk_fluent/_helpers.py`
- Create: `tests/manual/test_session.py`
- Modify: `seeds/seed.toml`

**Step 1: Write the test**

```python
# tests/manual/test_session.py
"""Tests for .session() context manager — builder mechanics only."""
from adk_fluent.agent import Agent


class TestSessionMechanics:
    def test_session_exists_on_agent(self):
        """Agent builder has .session() method."""
        builder = Agent("test").instruct("test")
        assert hasattr(builder, "session")
        assert callable(builder.session)
```

**Step 2: Add implementation to `_helpers.py`**

```python
from contextlib import asynccontextmanager


class ChatSession:
    """Interactive chat session wrapping ADK Runner + Session."""

    def __init__(self, runner, session, user_id: str):
        self._runner = runner
        self._session = session
        self._user_id = user_id

    async def send(self, text: str) -> str:
        """Send a message and return the response text."""
        from google.genai import types

        content = types.Content(
            role="user", parts=[types.Part(text=text)]
        )
        last_text = ""
        async for event in self._runner.run_async(
            user_id=self._user_id,
            session_id=self._session.id,
            new_message=content,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        last_text = part.text
        return last_text


@asynccontextmanager
async def create_session(builder: Any):
    """Create an interactive session context manager.

    Usage:
        async with create_session(agent_builder) as chat:
            response = await chat.send("Hello")
    """
    from google.adk.runners import InMemoryRunner

    agent = builder.build()
    app_name = f"_session_{agent.name}"
    user_id = "_session_user"
    runner = InMemoryRunner(agent=agent, app_name=app_name)
    session = await runner.session_service.create_session(
        app_name=app_name, user_id=user_id
    )

    try:
        yield ChatSession(runner, session, user_id)
    finally:
        pass  # InMemoryRunner has no cleanup needed
```

**Step 3: Add session extra to seed.toml and generator**

```toml
[[builders.Agent.extras]]
name = "session"
signature = "(self)"
doc = "Create an interactive session context manager. Use with 'async with'."
behavior = "runtime_helper_ctx"
helper_func = "create_session"
```

Add `runtime_helper_ctx` behavior to generator:

```python
        elif behavior == "runtime_helper_ctx":
            helper_func = extra.get("helper_func", name)
            body = f'''
        from adk_fluent._helpers import {helper_func}
        return {helper_func}(self)'''
```

**Step 4: Regenerate, test, commit**

```bash
python scripts/generator.py seeds/seed.toml manifest.json --output-dir src/adk_fluent --test-dir tests/generated
pytest tests/manual/test_session.py -v
git add src/adk_fluent/_helpers.py tests/manual/test_session.py seeds/seed.toml scripts/generator.py
git commit -m "feat: add .session() async context manager for interactive chat"
```

______________________________________________________________________

## Group 3: Update Stubs

### Task 10: Regenerate stubs to include all new methods

After all features are added, the `.pyi` stubs need to reflect the new methods.

**Files:**

- Modify: `scripts/generator.py` (stub generation for new behaviors)
- Regenerate: `src/adk_fluent/*.pyi`

**Step 1: Update stub generation for conditional callbacks**

In `gen_stub_class`, after the callback methods loop, add `_if` variants:

```python
    # Conditional callback stubs
    for short_name in spec.callback_aliases:
        lines.append(f"    def {short_name}_if(self, condition: bool, fn: Callable) -> Self: ...")
```

**Step 2: Update stub generation for new extra behaviors**

The existing stub generation already handles extras via their `signature` field. Verify that `deep_copy`, `runtime_helper`, `runtime_helper_async`, `runtime_helper_async_gen`, `dual_callback`, and `runtime_helper_ctx` extras all get their stubs generated from the signature in seed.toml.

For `async def` methods (`runtime_helper_async`, `runtime_helper_async_gen`), the stub needs to indicate async:

```python
    for extra in spec.extras:
        sig = extra.get("signature", "(self) -> Self")
        behavior = extra.get("behavior", "")
        prefix = "async " if behavior in ("runtime_helper_async", "runtime_helper_async_gen") else ""
        lines.append(f"    {prefix}def {extra['name']}{sig}: ...")
```

**Step 3: Regenerate everything**

Run: `python scripts/generator.py seeds/seed.toml manifest.json --output-dir src/adk_fluent --test-dir tests/generated`

**Step 4: Verify stubs contain new methods**

```bash
grep -n "def clone\|def ask\|def stream\|def test\|def session\|def guardrail\|def before_model_if" src/adk_fluent/agent.pyi
```

Expected: All new methods appear in the stub.

**Step 5: Run typecheck**

Run: `pyright src/adk_fluent/ --pythonversion 3.12` (informational — may have issues with ADK types)

**Step 6: Commit**

```bash
git add src/adk_fluent/
git commit -m "feat: regenerate all builders with new ergonomic methods + stubs"
```

______________________________________________________________________

## Group 4: Documentation Generator

### Task 11: Create `scripts/doc_generator.py` — API reference

**Files:**

- Create: `scripts/doc_generator.py`
- Create: `tests/test_doc_generator.py`

**Step 1: Write the test**

```python
# tests/test_doc_generator.py
"""Tests for documentation generator."""
import pytest
from scripts.doc_generator import gen_api_reference_for_builder


class TestApiReferenceGeneration:
    def test_generates_markdown_header(self):
        """API reference starts with builder name as H1."""
        spec_dict = {
            "name": "Agent",
            "source_class": "google.adk.agents.llm_agent.LlmAgent",
            "doc": "LLM-based Agent.",
            "constructor_args": ["name"],
            "aliases": {"instruct": "instruction"},
            "callback_aliases": {"before_model": "before_model_callback"},
            "extras": [{"name": "tool", "signature": "(self, fn_or_tool) -> Self", "doc": "Add a tool."}],
            "terminals": [{"name": "build", "returns": "LlmAgent"}],
            "fields": [
                {"name": "instruction", "type_str": "str", "description": "The instruction."},
                {"name": "model", "type_str": "str", "description": "The model name."},
            ],
            "skip_fields": set(),
        }
        md = gen_api_reference_for_builder(spec_dict)
        assert md.startswith("# Agent")
        assert "LlmAgent" in md
        assert "`.instruct(value)`" in md or ".instruct" in md
        assert ".before_model" in md
        assert ".tool" in md
        assert ".build()" in md
```

**Step 2: Implement `gen_api_reference_for_builder`**

```python
# scripts/doc_generator.py
"""
Documentation generator for adk-fluent.

Reads manifest + seed (via generator's BuilderSpec) and produces:
  1. API reference Markdown (one per module)
  2. Cookbook Markdown (from annotated example files)
  3. Migration guide (class + field mapping tables)
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from textwrap import dedent

try:
    import tomllib
except ImportError:
    import tomli as tomllib


def gen_api_reference_for_builder(spec: dict) -> str:
    """Generate API reference Markdown for a single builder."""
    lines = [
        f"# {spec['name']}",
        "",
        f"> Fluent builder for `{spec['source_class']}`",
        "",
        f"{spec['doc']}",
        "",
    ]

    # Constructor
    lines.append("## Constructor")
    lines.append("")
    args = spec.get("constructor_args", [])
    if args:
        lines.append("| Parameter | Type | Required |")
        lines.append("|-----------|------|----------|")
        for arg in args:
            lines.append(f"| `{arg}` | `str` | Yes |")
    else:
        lines.append("No constructor arguments.")
    lines.append("")

    # Alias methods
    aliases = spec.get("aliases", {})
    if aliases:
        lines.append("## Methods")
        lines.append("")
        for fluent_name, field_name in aliases.items():
            field_info = next(
                (f for f in spec.get("fields", []) if f["name"] == field_name),
                None
            )
            type_str = field_info["type_str"] if field_info else "Any"
            desc = field_info.get("description", "") if field_info else ""
            lines.append(f"### `.{fluent_name}(value)` -> `Self`")
            lines.append("")
            lines.append(f"Sets the `{field_name}` field.")
            if desc:
                lines.append(f"  {desc}")
            lines.append(f"- **Type**: `{type_str}`")
            lines.append("")

    # Callback methods
    cb_aliases = spec.get("callback_aliases", {})
    if cb_aliases:
        lines.append("## Callbacks")
        lines.append("")
        lines.append("All callback methods are **additive** — multiple calls accumulate.")
        lines.append("")
        for short_name, full_name in cb_aliases.items():
            lines.append(f"### `.{short_name}(*fns)` -> `Self`")
            lines.append("")
            lines.append(f"Appends callback(s) to `{full_name}`.")
            lines.append("")
            lines.append(f"### `.{short_name}_if(condition, fn)` -> `Self`")
            lines.append("")
            lines.append(f"Conditionally appends callback to `{full_name}`.")
            lines.append("")

    # Extra methods
    extras = spec.get("extras", [])
    if extras:
        lines.append("## Extra Methods")
        lines.append("")
        for extra in extras:
            sig = extra.get("signature", "(self) -> Self")
            lines.append(f"### `.{extra['name']}{sig}`")
            lines.append("")
            lines.append(f"{extra.get('doc', '')}")
            lines.append("")

    # Terminal methods
    terminals = spec.get("terminals", [])
    if terminals:
        lines.append("## Terminal Methods")
        lines.append("")
        for terminal in terminals:
            returns = terminal.get("returns", "Any")
            lines.append(f"### `.{terminal['name']}()` -> `{returns}`")
            lines.append("")
            lines.append(f"{terminal.get('doc', '')}")
            lines.append("")

    # Forwarded fields
    aliased = set(aliases.values()) | set(cb_aliases.values())
    skip = spec.get("skip_fields", set())
    forwarded = [
        f for f in spec.get("fields", [])
        if f["name"] not in aliased and f["name"] not in skip
        and f["name"] not in {e["name"] for e in extras}
        and f["name"] not in set(args)
    ]
    if forwarded:
        lines.append("## Forwarded Fields (via `__getattr__`)")
        lines.append("")
        lines.append("Any field not listed above can be set directly:")
        lines.append("")
        lines.append("| Field | Type | Default |")
        lines.append("|-------|------|---------|")
        for f in forwarded:
            default = f.get("default", "—")
            lines.append(f"| `{f['name']}` | `{f['type_str']}` | `{default}` |")
        lines.append("")

    return "\n".join(lines)
```

**Step 3: Run tests**

Run: `pytest tests/test_doc_generator.py -v`

**Step 4: Commit**

```bash
git add scripts/doc_generator.py tests/test_doc_generator.py
git commit -m "feat: add doc_generator.py with API reference generation"
```

______________________________________________________________________

### Task 12: Add cookbook processor to doc_generator.py

**Files:**

- Modify: `scripts/doc_generator.py`
- Modify: `tests/test_doc_generator.py`
- Create: `examples/cookbook/01_simple_agent.py` (first example as test fixture)

**Step 1: Write the test**

```python
# Add to tests/test_doc_generator.py
from scripts.doc_generator import process_cookbook_file


class TestCookbookProcessor:
    def test_splits_on_markers(self, tmp_path):
        """Cookbook processor splits on --- NATIVE --- / --- FLUENT --- markers."""
        example = tmp_path / "01_simple.py"
        example.write_text('''"""Simple Agent Creation"""

# --- NATIVE ---
from google.adk.agents import LlmAgent
agent = LlmAgent(name="a", model="m", instruction="i")

# --- FLUENT ---
from adk_fluent import Agent
agent = Agent("a").model("m").instruct("i").build()

# --- ASSERT ---
assert type(agent) is LlmAgent
''')
        result = process_cookbook_file(str(example))
        assert result["title"] == "Simple Agent Creation"
        assert "LlmAgent" in result["native"]
        assert "Agent(" in result["fluent"]
        assert "assert" in result["assertion"]

    def test_generates_markdown(self, tmp_path):
        """Cookbook processor produces valid Markdown."""
        example = tmp_path / "01_simple.py"
        example.write_text('''"""Simple Agent"""

# --- NATIVE ---
native_code = 1

# --- FLUENT ---
fluent_code = 1

# --- ASSERT ---
assert True
''')
        result = process_cookbook_file(str(example))
        md = cookbook_to_markdown(result)
        assert "# Simple Agent" in md
        assert "## Native ADK" in md
        assert "## adk-fluent" in md
```

**Step 2: Implement cookbook processor**

````python
def process_cookbook_file(filepath: str) -> dict:
    """Parse an annotated cookbook example file into sections."""
    text = Path(filepath).read_text()

    # Extract title from module docstring
    title_match = re.match(r'"""(.+?)"""', text, re.DOTALL)
    title = title_match.group(1).strip() if title_match else Path(filepath).stem

    # Split on markers
    sections = {"native": "", "fluent": "", "assertion": ""}
    current = None
    for line in text.split("\n"):
        if "# --- NATIVE ---" in line:
            current = "native"
            continue
        elif "# --- FLUENT ---" in line:
            current = "fluent"
            continue
        elif "# --- ASSERT ---" in line:
            current = "assertion"
            continue
        if current:
            sections[current] += line + "\n"

    return {
        "title": title,
        "native": sections["native"].strip(),
        "fluent": sections["fluent"].strip(),
        "assertion": sections["assertion"].strip(),
        "filename": Path(filepath).name,
    }


def cookbook_to_markdown(parsed: dict) -> str:
    """Convert parsed cookbook data to Markdown."""
    return f"""# {parsed['title']}

## Native ADK

```python
{parsed['native']}
````

## adk-fluent

```python
{parsed['fluent']}
```

## Equivalence

```python
{parsed['assertion']}
```

"""

````

**Step 3: Create first cookbook example**

```python
# examples/cookbook/01_simple_agent.py
"""Simple Agent Creation"""

# --- NATIVE ---
from google.adk.agents.llm_agent import LlmAgent

agent_native = LlmAgent(
    name="helper",
    model="gemini-2.5-flash",
    instruction="You are a helpful assistant.",
    description="A simple helper agent",
)

# --- FLUENT ---
from adk_fluent import Agent

agent_fluent = (
    Agent("helper")
    .model("gemini-2.5-flash")
    .instruct("You are a helpful assistant.")
    .describe("A simple helper agent")
    .build()
)

# --- ASSERT ---
assert type(agent_native) == type(agent_fluent)
assert agent_native.name == agent_fluent.name
assert agent_native.model == agent_fluent.model
assert agent_native.instruction == agent_fluent.instruction
````

**Step 4: Run tests and commit**

```bash
pytest tests/test_doc_generator.py -v
git add scripts/doc_generator.py tests/test_doc_generator.py examples/cookbook/01_simple_agent.py
git commit -m "feat: add cookbook processor with marker-based example parsing"
```

______________________________________________________________________

### Task 13: Add migration guide generator

**Files:**

- Modify: `scripts/doc_generator.py`
- Modify: `tests/test_doc_generator.py`

**Step 1: Write the test**

```python
# Add to tests/test_doc_generator.py
from scripts.doc_generator import gen_migration_guide


class TestMigrationGuide:
    def test_generates_class_mapping_table(self):
        """Migration guide contains native → fluent class mapping."""
        specs = [
            {"name": "Agent", "source_class": "google.adk.agents.llm_agent.LlmAgent",
             "aliases": {"instruct": "instruction"}, "callback_aliases": {}, "extras": [], "terminals": []},
            {"name": "Pipeline", "source_class": "google.adk.agents.sequential_agent.SequentialAgent",
             "aliases": {}, "callback_aliases": {}, "extras": [], "terminals": []},
        ]
        md = gen_migration_guide(specs)
        assert "LlmAgent" in md
        assert "Agent" in md
        assert "SequentialAgent" in md
        assert "Pipeline" in md
```

**Step 2: Implement**

```python
def gen_migration_guide(specs: list[dict]) -> str:
    """Generate migration guide Markdown from builder specs."""
    lines = [
        "# Migration from Native ADK",
        "",
        "## Class Mapping",
        "",
        "| Native ADK Class | adk-fluent Builder | Import |",
        "|-----------------|-------------------|--------|",
    ]

    for spec in specs:
        native = spec["source_class"].split(".")[-1]
        fluent = spec["name"]
        lines.append(f"| `{native}` | `{fluent}` | `from adk_fluent import {fluent}` |")

    lines.append("")

    # Field mappings for builders with aliases
    for spec in specs:
        aliases = spec.get("aliases", {})
        cb_aliases = spec.get("callback_aliases", {})
        if not aliases and not cb_aliases:
            continue

        lines.append(f"## {spec['name']} Field Mapping")
        lines.append("")
        lines.append("| Native Field | Fluent Method | Notes |")
        lines.append("|-------------|---------------|-------|")

        for fluent_name, field_name in aliases.items():
            lines.append(f"| `{field_name}` | `.{fluent_name}()` | Alias |")

        for short_name, full_name in cb_aliases.items():
            lines.append(f"| `{full_name}` | `.{short_name}()` | Additive |")

        for extra in spec.get("extras", []):
            lines.append(f"| — | `.{extra['name']}()` | {extra.get('doc', '')} |")

        lines.append("")

    return "\n".join(lines)
```

**Step 3: Run tests and commit**

```bash
pytest tests/test_doc_generator.py::TestMigrationGuide -v
git add scripts/doc_generator.py tests/test_doc_generator.py
git commit -m "feat: add migration guide generator"
```

______________________________________________________________________

### Task 14: Add CLI and orchestrator to doc_generator.py

**Files:**

- Modify: `scripts/doc_generator.py`

**Step 1: Add the main orchestrator**

```python
import argparse
import sys
# Add to existing imports at top of doc_generator.py

# Import BuilderSpec resolution from generator
sys.path.insert(0, str(Path(__file__).parent))
from generator import parse_seed, parse_manifest, resolve_builder_specs


def generate_docs(seed_path: str, manifest_path: str,
                  output_dir: str, cookbook_dir: str | None = None,
                  api_only: bool = False, cookbook_only: bool = False,
                  migration_only: bool = False):
    """Main documentation generation pipeline."""
    seed = parse_seed(seed_path)
    manifest = parse_manifest(manifest_path)
    specs = resolve_builder_specs(seed, manifest)

    output = Path(output_dir)

    if not cookbook_only and not migration_only:
        # API reference
        api_dir = output / "api"
        api_dir.mkdir(parents=True, exist_ok=True)

        from collections import defaultdict
        by_module = defaultdict(list)
        for spec in specs:
            by_module[spec.output_module].append(spec)

        for module_name, module_specs in by_module.items():
            md_parts = []
            for spec in module_specs:
                spec_dict = _spec_to_dict(spec)
                md_parts.append(gen_api_reference_for_builder(spec_dict))
            filepath = api_dir / f"{module_name}.md"
            filepath.write_text("\n---\n\n".join(md_parts))
            print(f"  Generated: {filepath}")

    if not api_only and not migration_only and cookbook_dir:
        # Cookbook
        cookbook_out = output / "cookbook"
        cookbook_out.mkdir(parents=True, exist_ok=True)
        cookbook_path = Path(cookbook_dir)
        if cookbook_path.exists():
            for example_file in sorted(cookbook_path.glob("*.py")):
                parsed = process_cookbook_file(str(example_file))
                md = cookbook_to_markdown(parsed)
                out_file = cookbook_out / f"{example_file.stem}.md"
                out_file.write_text(md)
                print(f"  Generated: {out_file}")

    if not api_only and not cookbook_only:
        # Migration guide
        migration_dir = output / "migration"
        migration_dir.mkdir(parents=True, exist_ok=True)
        spec_dicts = [_spec_to_dict(s) for s in specs]
        md = gen_migration_guide(spec_dicts)
        filepath = migration_dir / "from-native-adk.md"
        filepath.write_text(md)
        print(f"  Generated: {filepath}")


def _spec_to_dict(spec) -> dict:
    """Convert BuilderSpec to dict for doc generation."""
    return {
        "name": spec.name,
        "source_class": spec.source_class,
        "doc": spec.doc,
        "constructor_args": spec.constructor_args,
        "aliases": spec.aliases,
        "callback_aliases": spec.callback_aliases,
        "extras": spec.extras,
        "terminals": spec.terminals,
        "fields": spec.fields,
        "skip_fields": spec.skip_fields,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate adk-fluent documentation")
    parser.add_argument("seed", help="Path to seed.toml")
    parser.add_argument("manifest", help="Path to manifest.json")
    parser.add_argument("--output-dir", default="docs/generated", help="Output directory")
    parser.add_argument("--cookbook-dir", default="examples/cookbook", help="Cookbook examples directory")
    parser.add_argument("--api-only", action="store_true")
    parser.add_argument("--cookbook-only", action="store_true")
    parser.add_argument("--migration-only", action="store_true")
    args = parser.parse_args()

    generate_docs(
        seed_path=args.seed,
        manifest_path=args.manifest,
        output_dir=args.output_dir,
        cookbook_dir=args.cookbook_dir,
        api_only=args.api_only,
        cookbook_only=args.cookbook_only,
        migration_only=args.migration_only,
    )


if __name__ == "__main__":
    main()
```

**Step 2: Run manually to verify**

Run: `python scripts/doc_generator.py seeds/seed.toml manifest.json --output-dir docs/generated --cookbook-dir examples/cookbook`
Expected: Files generated in `docs/generated/api/`, `docs/generated/cookbook/`, `docs/generated/migration/`.

**Step 3: Commit**

```bash
git add scripts/doc_generator.py
git commit -m "feat: add doc_generator.py CLI with api/cookbook/migration targets"
```

______________________________________________________________________

## Group 5: Justfile & Pipeline Integration

### Task 15: Update justfile with documentation targets

**Files:**

- Modify: `justfile`

**Step 1: Add doc targets to justfile**

Add after the `typecheck` target, before `diff`:

```just
DOC_GEN       := "scripts/doc_generator.py"
DOC_DIR       := "docs/generated"
COOKBOOK_DIR   := "examples/cookbook"

# --- Documentation ---
docs: _require-manifest _require-seed
    @echo "Generating documentation..."
    @python {{DOC_GEN}} {{SEED}} {{MANIFEST}} \
        --output-dir {{DOC_DIR}} \
        --cookbook-dir {{COOKBOOK_DIR}}

docs-api: _require-manifest _require-seed
    @echo "Generating API reference..."
    @python {{DOC_GEN}} {{SEED}} {{MANIFEST}} \
        --output-dir {{DOC_DIR}} \
        --api-only

docs-cookbook: _require-manifest _require-seed
    @echo "Generating cookbook..."
    @python {{DOC_GEN}} {{SEED}} {{MANIFEST}} \
        --output-dir {{DOC_DIR}} \
        --cookbook-dir {{COOKBOOK_DIR}} \
        --cookbook-only

docs-migration: _require-manifest _require-seed
    @echo "Generating migration guide..."
    @python {{DOC_GEN}} {{SEED}} {{MANIFEST}} \
        --output-dir {{DOC_DIR}} \
        --migration-only
```

Update the `all` target:

```just
all: scan seed generate docs
    @echo "\nPipeline complete. Generated code in {{OUTPUT_DIR}}/ and docs in {{DOC_DIR}}/"
```

Update `clean`:

```just
clean:
    @echo "Cleaning generated files..."
    @rm -rf {{OUTPUT_DIR}}/*.py {{OUTPUT_DIR}}/*.pyi
    @rm -rf {{TEST_DIR}}/
    @rm -rf {{DOC_DIR}}/
    @rm -f {{MANIFEST}}
    @echo "Done."
```

Update `help`:

```just
help:
    @echo "ADK-FLUENT Development Commands:"
    @echo ""
    @echo "  just all            Full pipeline: scan -> seed -> generate -> docs"
    @echo "  just scan           Introspect ADK -> manifest.json"
    @echo "  just seed           manifest.json -> seed.toml"
    @echo "  just generate       seed.toml + manifest.json -> code"
    @echo "  just stubs          Regenerate .pyi stubs only"
    @echo "  just test           Run pytest suite"
    @echo "  just typecheck      Run pyright type-check"
    @echo "  just docs           Generate all documentation"
    @echo "  just docs-api       Generate API reference only"
    @echo "  just docs-cookbook   Generate cookbook only"
    @echo "  just docs-migration Generate migration guide only"
    @echo "  just diff           Show changes since last scan"
    @echo "  just build          Build pip package"
    @echo "  just publish        Publish to PyPI"
    @echo "  just clean          Remove generated files"
    @echo ""
    @echo "Workflow: just all -> just test -> commit"
```

**Step 2: Verify pipeline works**

Run: `just docs`
Expected: Documentation generated in `docs/generated/`.

**Step 3: Commit**

```bash
git add justfile
git commit -m "feat: add docs, docs-api, docs-cookbook, docs-migration to justfile"
```

______________________________________________________________________

## Group 6: Cookbook Examples

### Task 16: Create remaining cookbook examples

**Files:**

- Create: `examples/cookbook/02_agent_with_tools.py`
- Create: `examples/cookbook/03_callbacks.py`
- Create: `examples/cookbook/04_sequential_pipeline.py`
- Create: `examples/cookbook/05_parallel_fanout.py`
- Create: `examples/cookbook/06_loop_agent.py`
- Create: `examples/cookbook/07_team_coordinator.py`
- Create: `examples/cookbook/08_one_shot_ask.py`
- Create: `examples/cookbook/09_streaming.py`
- Create: `examples/cookbook/10_cloning.py`
- Create: `examples/cookbook/11_inline_testing.py`
- Create: `examples/cookbook/12_guardrails.py`
- Create: `examples/cookbook/13_interactive_session.py`
- Create: `examples/cookbook/14_dynamic_forwarding.py`
- Create: `examples/cookbook/15_production_runtime.py`

Each follows the marker format:

```python
"""Title"""

# --- NATIVE ---
# Native ADK code

# --- FLUENT ---
# Fluent adk-fluent code

# --- ASSERT ---
# Equivalence assertions
```

**Step 1: Create examples 02-07** (these use only `.build()` and can assert equivalence)

See `examples/cookbook/01_simple_agent.py` pattern from Task 12. Each example demonstrates one pattern with both native and fluent code, plus assertions.

**Step 2: Create examples 08-13** (these use new features — `.ask()`, `.stream()`, `.clone()`, etc.)

These examples don't have native equivalents — they show the new features. Use a modified marker format:

```python
"""One-Shot Execution with .ask()"""

# --- NATIVE ---
# 15+ lines of Runner/Session/async ceremony
from google.adk.agents.llm_agent import LlmAgent
from google.adk.runners import InMemoryRunner
from google.genai import types
import asyncio

agent = LlmAgent(name="q", model="gemini-2.5-flash", instruction="Answer concisely.")
runner = InMemoryRunner(agent=agent, app_name="app")

async def run():
    session = await runner.session_service.create_session(app_name="app", user_id="u")
    content = types.Content(role="user", parts=[types.Part(text="What is 2+2?")])
    async for event in runner.run_async(user_id="u", session_id=session.id, new_message=content):
        if event.content and event.content.parts:
            return event.content.parts[0].text

result = asyncio.run(run())

# --- FLUENT ---
from adk_fluent import Agent

result = Agent("q", "gemini-2.5-flash").instruct("Answer concisely.").ask("What is 2+2?")

# --- ASSERT ---
# Both produce a string response (can't assert equality due to LLM non-determinism)
assert isinstance(result, str)
```

**Step 3: Create examples 14-15** (dynamic forwarding, production runtime)

**Step 4: Run cookbook examples as tests**

Run: `pytest examples/cookbook/ -v --tb=short`
Expected: Examples 01-07 pass (pure builder equivalence). Examples 08-13 may fail without API key (expected).

**Step 5: Regenerate docs and commit**

```bash
just docs-cookbook
git add examples/cookbook/ docs/generated/cookbook/
git commit -m "feat: add 15 cookbook examples with native vs fluent comparisons"
```

______________________________________________________________________

## Group 7: Final Integration

### Task 17: Run full pipeline and verify everything

**Step 1: Run full pipeline**

```bash
just all
```

Expected: scan → seed → generate → docs all succeed.

**Step 2: Run all tests**

```bash
just test
```

Expected: All tests pass.

**Step 3: Verify generated docs look correct**

```bash
ls docs/generated/api/
ls docs/generated/cookbook/
ls docs/generated/migration/
```

Expected: API reference for each module, cookbook for each example, migration guide.

**Step 4: Build package**

```bash
just build
```

Expected: Package builds successfully.

**Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete ergonomic depth features + auto-generated documentation system"
```

______________________________________________________________________

## Summary

| Group | Tasks | Description                                                       |
| ----- | ----- | ----------------------------------------------------------------- |
| 1     | 1-5   | Clone, variadic callbacks, guardrail, conditional callbacks (TDD) |
| 2     | 6-9   | Ask, stream, test, session (runtime helpers)                      |
| 3     | 10    | Regenerate stubs with all new methods                             |
| 4     | 11-14 | Documentation generator (API ref, cookbook, migration)            |
| 5     | 15    | Justfile integration                                              |
| 6     | 16    | 15 cookbook examples                                              |
| 7     | 17    | Full pipeline verification                                        |

**Total: 17 tasks, ~50 bite-sized steps.**

**Key files created:**

- `src/adk_fluent/_helpers.py` — runtime implementations
- `scripts/doc_generator.py` — documentation generator
- `tests/manual/test_*.py` — 6 test files for new features
- `examples/cookbook/*.py` — 15 annotated examples
- `docs/generated/` — auto-generated documentation output

**Key files modified:**

- `scripts/generator.py` — new behaviors (deep_copy, dual_callback, runtime_helper, variadic/conditional callbacks)
- `seeds/seed.toml` — new extras and terminals for Agent builder
- `justfile` — docs targets
- `src/adk_fluent/agent.py` — regenerated with new methods
- `src/adk_fluent/agent.pyi` — regenerated stubs
