"""Tests for engine wiring — .engine(), .compute(), configure(), and E2E execution.

Verifies that:
1. .engine("asyncio") routes execution through the asyncio backend
2. configure(engine="asyncio") sets global defaults
3. The asyncio backend executes IR end-to-end with a mock ModelProvider
4. Pipeline and FanOut operators work through the engine path
5. Temporal codegen produces valid workflow/activity code
"""

from collections.abc import AsyncIterator

import pytest

from adk_fluent import (
    Agent,
    FanOut,
    Pipeline,
    configure,
    reset_config,
)
from adk_fluent._helpers import _resolve_engine, _run_via_engine
from adk_fluent.compute import ComputeConfig
from adk_fluent.compute._protocol import (
    Chunk,
    GenerateConfig,
    GenerateResult,
    Message,
    ToolDef,
)

# ======================================================================
# Mock ModelProvider for testing
# ======================================================================


class MockModelProvider:
    """Deterministic model provider for testing the asyncio backend E2E."""

    model_id = "mock-model"
    supports_tools = False
    supports_structured_output = False

    def __init__(self, responses: dict[str, str] | None = None, default: str = "Hello from mock!"):
        self._responses = responses or {}
        self._default = default
        self._call_count = 0

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
        config: GenerateConfig | None = None,
    ) -> GenerateResult:
        self._call_count += 1
        # Check for instruction-based routing
        for msg in messages:
            if msg.role == "user" and msg.content in self._responses:
                return GenerateResult(text=self._responses[msg.content])
            if msg.role == "system" and msg.content in self._responses:
                return GenerateResult(text=self._responses[msg.content])
        return GenerateResult(text=self._default)

    async def generate_stream(
        self,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
        config: GenerateConfig | None = None,
    ) -> AsyncIterator[Chunk]:
        result = await self.generate(messages, tools, config)
        yield Chunk(text=result.text, is_final=True)


class MockToolProvider:
    """Deterministic model provider that returns tool calls."""

    model_id = "mock-tool-model"
    supports_tools = True
    supports_structured_output = False

    def __init__(self):
        self._call_count = 0

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
        config: GenerateConfig | None = None,
    ) -> GenerateResult:
        self._call_count += 1
        # First call returns tool call, second returns final answer
        if self._call_count == 1 and tools:
            return GenerateResult(
                text="",
                tool_calls=[{"name": tools[0].name, "args": {"x": 42}}],
            )
        return GenerateResult(text="Tool result processed")

    async def generate_stream(self, messages, tools=None, config=None):
        result = await self.generate(messages, tools, config)
        yield Chunk(text=result.text, is_final=True)


# ======================================================================
# _resolve_engine tests
# ======================================================================


class TestResolveEngine:
    def setup_method(self):
        reset_config()

    def teardown_method(self):
        reset_config()

    def test_no_engine_returns_none(self):
        agent = Agent("test")
        assert _resolve_engine(agent) is None

    def test_builder_engine_override(self):
        agent = Agent("test").engine("asyncio")
        assert _resolve_engine(agent) == "asyncio"

    def test_global_config_fallback(self):
        configure(engine="temporal")
        agent = Agent("test")
        assert _resolve_engine(agent) == "temporal"

    def test_builder_overrides_global(self):
        configure(engine="temporal")
        agent = Agent("test").engine("asyncio")
        assert _resolve_engine(agent) == "asyncio"


# ======================================================================
# Asyncio backend E2E via .engine("asyncio")
# ======================================================================


class TestAsyncioEngineE2E:
    """End-to-end tests: builder → IR → asyncio backend → response."""

    @pytest.mark.asyncio
    async def test_simple_agent(self):
        """Single agent with mock provider returns expected text."""
        provider = MockModelProvider(default="The answer is 42.")
        agent = Agent("solver", "mock-model").instruct("Solve the problem.").engine("asyncio", model_provider=provider)
        text, events = await _run_via_engine(agent, "What is the answer?")
        assert text == "The answer is 42."
        assert len(events) >= 1
        assert provider._call_count == 1

    @pytest.mark.asyncio
    async def test_agent_with_output_key(self):
        """Agent .writes(key) stores output in state."""
        provider = MockModelProvider(default="result_value")
        agent = Agent("writer").instruct("Write something.").writes("output").engine("asyncio", model_provider=provider)
        text, events = await _run_via_engine(agent, "go")
        assert text == "result_value"
        # Check state delta contains output key
        has_output_key = any(e.state_delta and "output" in e.state_delta for e in events)
        assert has_output_key

    @pytest.mark.asyncio
    async def test_pipeline_sequential(self):
        """Pipeline runs agents sequentially through asyncio backend."""
        provider = MockModelProvider(default="step done")
        pipeline = (
            Pipeline("flow")
            .step(Agent("a").instruct("Step 1"))
            .step(Agent("b").instruct("Step 2"))
            .engine("asyncio", model_provider=provider)
        )
        text, events = await _run_via_engine(pipeline, "go")
        assert text == "step done"
        assert provider._call_count == 2
        # Both agents should have produced events
        authors = [e.author for e in events if e.author]
        assert "a" in authors
        assert "b" in authors

    @pytest.mark.asyncio
    async def test_fanout_parallel(self):
        """FanOut runs agents in parallel through asyncio backend."""
        provider = MockModelProvider(default="branch result")
        fanout = (
            FanOut("parallel")
            .branch(Agent("x").instruct("Branch X"))
            .branch(Agent("y").instruct("Branch Y"))
            .engine("asyncio", model_provider=provider)
        )
        text, events = await _run_via_engine(fanout, "go")
        assert provider._call_count == 2
        authors = [e.author for e in events if e.author]
        assert "x" in authors
        assert "y" in authors

    @pytest.mark.asyncio
    async def test_global_configure_asyncio(self):
        """configure(engine="asyncio") routes all agents through asyncio."""
        provider = MockModelProvider(default="global result")
        configure(
            engine="asyncio",
            engine_config={"model_provider": provider},
        )
        agent = Agent("test").instruct("Hello")
        text, events = await _run_via_engine(agent, "hi")
        assert text == "global result"
        reset_config()

    @pytest.mark.asyncio
    async def test_compute_config_provider(self):
        """ComputeConfig.model_provider is injected into asyncio backend."""
        provider = MockModelProvider(default="via compute")
        agent = Agent("test").instruct("Hello").engine("asyncio").compute(ComputeConfig(model_provider=provider))
        text, events = await _run_via_engine(agent, "hi")
        assert text == "via compute"

    @pytest.mark.asyncio
    async def test_tool_execution(self):
        """Agent with tools executes tool calls through asyncio backend."""

        def my_tool(x: int) -> str:
            """A test tool."""
            return f"result: {x * 2}"

        provider = MockToolProvider()
        agent = Agent("tool_user").instruct("Use the tool.").tool(my_tool).engine("asyncio", model_provider=provider)
        text, events = await _run_via_engine(agent, "test")
        assert text == "Tool result processed"
        assert provider._call_count == 2  # tool call + final response


# ======================================================================
# Expression operators with engine
# ======================================================================


class TestExpressionOperatorsWithEngine:
    @pytest.mark.asyncio
    async def test_pipeline_operator(self):
        """>> operator works with .engine()."""
        provider = MockModelProvider(default="chained")
        pipeline = Agent("a").instruct("1") >> Agent("b").instruct("2")
        # Set engine on the resulting pipeline
        pipeline = pipeline.engine("asyncio", model_provider=provider)
        text, events = await _run_via_engine(pipeline, "go")
        assert text == "chained"
        assert provider._call_count == 2

    @pytest.mark.asyncio
    async def test_fanout_operator(self):
        """|  operator works with .engine()."""
        provider = MockModelProvider(default="parallel")
        fanout = Agent("a").instruct("1") | Agent("b").instruct("2")
        fanout = fanout.engine("asyncio", model_provider=provider)
        text, events = await _run_via_engine(fanout, "go")
        assert provider._call_count == 2


# ======================================================================
# Transform / Tap through asyncio
# ======================================================================


class TestTransformTapE2E:
    @pytest.mark.asyncio
    async def test_transform_in_pipeline(self):
        """S.transform in pipeline modifies state."""
        from adk_fluent._transforms import S

        provider = MockModelProvider(default="final")
        pipeline = (
            Pipeline("flow")
            .step(Agent("a").instruct("Go").writes("raw"))
            .step(S.set(processed="yes"))
            .step(Agent("b").instruct("Check {processed}"))
            .engine("asyncio", model_provider=provider)
        )
        text, events = await _run_via_engine(pipeline, "go")
        assert text == "final"
        assert provider._call_count == 2

    @pytest.mark.asyncio
    async def test_function_step_in_pipeline(self):
        """Plain function as pipeline step works via asyncio."""
        provider = MockModelProvider(default="done")

        def double(state):
            return {"count": state.get("count", 0) * 2}

        pipeline = Agent("a").instruct("go").writes("count") >> double >> Agent("b").instruct("finish")
        pipeline = pipeline.engine("asyncio", model_provider=provider)
        text, events = await _run_via_engine(pipeline, "go")
        assert text == "done"


# ======================================================================
# Temporal codegen
# ======================================================================


class TestTemporalCodegen:
    def test_generate_worker_code(self):
        """generate_worker_code produces valid Python with activities and workflow."""
        from adk_fluent.backends.temporal import TemporalBackend
        from adk_fluent.backends.temporal_worker import (
            generate_worker_code,
        )

        ir = (
            Pipeline("flow")
            .step(Agent("researcher").instruct("Research the topic."))
            .step(Agent("writer").instruct("Write the report."))
            .to_ir()
        )

        backend = TemporalBackend()
        runnable = backend.compile(ir)
        code = generate_worker_code(runnable)

        # Verify structure
        assert "@activity.defn" in code
        assert "@workflow.defn" in code
        assert "@workflow.run" in code
        assert "researcher" in code
        assert "writer" in code
        assert "create_temporal_worker" in code
        assert "timedelta" in code

    def test_generate_code_parallel(self):
        """Parallel agents generate concurrent activity calls."""
        from adk_fluent.backends.temporal import TemporalBackend
        from adk_fluent.backends.temporal_worker import generate_worker_code

        ir = (
            FanOut("parallel")
            .branch(Agent("web").instruct("Search web."))
            .branch(Agent("papers").instruct("Search papers."))
            .to_ir()
        )

        backend = TemporalBackend()
        runnable = backend.compile(ir)
        code = generate_worker_code(runnable)

        assert "web" in code
        assert "papers" in code
        assert "start_activity" in code  # parallel uses start_activity

    def test_generate_code_loop(self):
        """Loop generates iteration code."""
        from adk_fluent import Loop
        from adk_fluent.backends.temporal import TemporalBackend
        from adk_fluent.backends.temporal_worker import generate_worker_code

        ir = (
            Loop("refine")
            .step(Agent("writer").instruct("Write."))
            .step(Agent("critic").instruct("Critique."))
            .max_iterations(3)
            .to_ir()
        )

        backend = TemporalBackend()
        runnable = backend.compile(ir)
        code = generate_worker_code(runnable)

        assert "range(3)" in code
        assert "writer" in code
        assert "critic" in code

    def test_collect_activities(self):
        """_collect_activities finds all AgentNodes in nested plan."""
        from adk_fluent.backends.temporal import TemporalBackend
        from adk_fluent.backends.temporal_worker import _collect_activities

        ir = (
            Pipeline("flow")
            .step(Agent("a").instruct("1"))
            .step(Agent("b").instruct("2"))
            .step(Agent("c").instruct("3"))
            .to_ir()
        )

        backend = TemporalBackend()
        runnable = backend.compile(ir)
        activities = _collect_activities(runnable.node_plan)

        names = [a["name"] for a in activities]
        assert "a" in names
        assert "b" in names
        assert "c" in names

    def test_generated_code_compiles(self):
        """Generated code is valid Python (compile check)."""
        from adk_fluent.backends.temporal import TemporalBackend
        from adk_fluent.backends.temporal_worker import generate_worker_code

        ir = Agent("solo").instruct("Do something.").to_ir()
        backend = TemporalBackend()
        runnable = backend.compile(ir)
        code = generate_worker_code(runnable)

        # Should compile without SyntaxError
        compile(code, "<generated>", "exec")

    def test_signal_handler_in_workflow(self):
        """Workflow includes signal handler for gate approval."""
        from adk_fluent.backends.temporal import TemporalBackend
        from adk_fluent.backends.temporal_worker import generate_worker_code

        ir = Agent("test").instruct("Test").to_ir()
        backend = TemporalBackend()
        runnable = backend.compile(ir)
        code = generate_worker_code(runnable)

        assert '@workflow.signal(name="approve")' in code
        assert "async def approve" in code


# ======================================================================
# Fallback through asyncio
# ======================================================================


class TestFallbackE2E:
    @pytest.mark.asyncio
    async def test_fallback_first_success(self):
        """Fallback chain returns first successful result."""
        provider = MockModelProvider(default="success")
        pipeline = Agent("fast").instruct("Try fast") // Agent("slow").instruct("Try slow")
        pipeline = pipeline.engine("asyncio", model_provider=provider)
        text, events = await _run_via_engine(pipeline, "go")
        assert text == "success"
        assert provider._call_count == 1  # Only first agent called


# ======================================================================
# Loop through asyncio
# ======================================================================


class TestLoopE2E:
    @pytest.mark.asyncio
    async def test_loop_runs_iterations(self):
        """Loop runs correct number of iterations."""
        from adk_fluent import Loop

        provider = MockModelProvider(default="iteration")
        loop = (
            Loop("refine")
            .step(Agent("writer").instruct("Write."))
            .max_iterations(3)
            .engine("asyncio", model_provider=provider)
        )
        text, events = await _run_via_engine(loop, "go")
        assert provider._call_count == 3
