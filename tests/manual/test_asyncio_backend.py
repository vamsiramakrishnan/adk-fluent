"""Tests for the asyncio backend (Phase 6 of five-layer decoupling)."""

import asyncio

from adk_fluent._ir import FallbackNode, TapNode, TransformNode
from adk_fluent._ir_generated import AgentNode, LoopNode, ParallelNode, SequenceNode
from adk_fluent.backends.asyncio_backend import AsyncioBackend
from adk_fluent.compute._protocol import GenerateResult

# ======================================================================
# Fake ModelProvider for testing
# ======================================================================


class FakeModelProvider:
    """Returns canned responses for testing."""

    def __init__(self, responses: dict[str, str] | None = None, default: str = "Hello"):
        self._responses = responses or {}
        self._default = default
        self._call_count = 0
        self.calls: list[dict] = []

    @property
    def model_id(self) -> str:
        return "fake-model"

    @property
    def supports_tools(self) -> bool:
        return True

    @property
    def supports_structured_output(self) -> bool:
        return False

    async def generate(self, messages, tools=None, config=None):
        self._call_count += 1
        self.calls.append({"messages": messages, "tools": tools})

        # Find instruction to match against responses
        instruction = ""
        for msg in messages:
            if msg.role == "system":
                instruction = msg.content
                break

        response_text = self._default
        for key, text in self._responses.items():
            if key in instruction:
                response_text = text
                break

        return GenerateResult(text=response_text)

    async def generate_stream(self, messages, tools=None, config=None):
        result = await self.generate(messages, tools, config)
        from adk_fluent.compute._protocol import Chunk

        yield Chunk(text=result.text, is_final=True)


# ======================================================================
# Tests
# ======================================================================


class TestAsyncioBackendCapabilities:
    def test_capabilities(self):
        backend = AsyncioBackend()
        cap = backend.capabilities
        assert cap.streaming is True
        assert cap.parallel is True
        assert cap.durable is False
        assert cap.replay is False

    def test_name(self):
        assert AsyncioBackend().name == "asyncio"


class TestAsyncioBackendCompile:
    def test_compile_wraps_ir(self):
        """Compile wraps the IR in an AsyncioRunnable."""
        backend = AsyncioBackend()
        node = AgentNode(name="test")
        compiled = backend.compile(node)
        assert compiled.node is node


class TestAsyncioBackendAgentNode:
    def test_agent_without_provider(self):
        """AgentNode without provider returns placeholder."""
        backend = AsyncioBackend()

        async def _test():
            node = AgentNode(name="test")
            compiled = backend.compile(node)
            events = await backend.run(compiled, "Hello")
            assert any("no model provider" in (e.content or "") for e in events)

        asyncio.run(_test())

    def test_agent_with_provider(self):
        """AgentNode with provider calls generate()."""
        provider = FakeModelProvider(default="I'm an AI")
        backend = AsyncioBackend(model_provider=provider)

        async def _test():
            node = AgentNode(name="helper", instruction="You are helpful")
            compiled = backend.compile(node)
            events = await backend.run(compiled, "Hi")
            assert any(e.content == "I'm an AI" for e in events)
            assert len(provider.calls) == 1

        asyncio.run(_test())

    def test_agent_instruction_passed(self):
        """Agent instruction is passed as system message."""
        provider = FakeModelProvider()
        backend = AsyncioBackend(model_provider=provider)

        async def _test():
            node = AgentNode(name="expert", instruction="You are an expert")
            compiled = backend.compile(node)
            await backend.run(compiled, "Help me")
            messages = provider.calls[0]["messages"]
            assert any(m.role == "system" and "expert" in m.content for m in messages)

        asyncio.run(_test())

    def test_agent_output_key(self):
        """Agent with output_key stores result in state."""
        provider = FakeModelProvider(default="my output")
        backend = AsyncioBackend(model_provider=provider)

        async def _test():
            node = AgentNode(name="writer", output_key="draft")
            compiled = backend.compile(node)
            events = await backend.run(compiled, "Write")
            state_event = next(e for e in events if e.state_delta)
            assert state_event.state_delta.get("draft") == "my output"

        asyncio.run(_test())


class TestAsyncioBackendSequence:
    def test_sequence_runs_in_order(self):
        """SequenceNode runs children sequentially."""
        responses = {"Step 1": "Result 1", "Step 2": "Result 2"}
        provider = FakeModelProvider(responses=responses, default="default")
        backend = AsyncioBackend(model_provider=provider)

        async def _test():
            seq = SequenceNode(
                name="pipeline",
                children=(
                    AgentNode(name="a", instruction="Step 1"),
                    AgentNode(name="b", instruction="Step 2"),
                ),
            )
            compiled = backend.compile(seq)
            events = await backend.run(compiled, "Go")

            contents = [e.content for e in events if e.content]
            assert contents == ["Result 1", "Result 2"]
            assert len(provider.calls) == 2

        asyncio.run(_test())


class TestAsyncioBackendParallel:
    def test_parallel_runs_concurrently(self):
        """ParallelNode runs children concurrently."""
        provider = FakeModelProvider(default="parallel result")
        backend = AsyncioBackend(model_provider=provider)

        async def _test():
            par = ParallelNode(
                name="fanout",
                children=(
                    AgentNode(name="a", instruction="Branch 1"),
                    AgentNode(name="b", instruction="Branch 2"),
                ),
            )
            compiled = backend.compile(par)
            events = await backend.run(compiled, "Go")

            contents = [e.content for e in events if e.content]
            assert len(contents) == 2
            assert len(provider.calls) == 2

        asyncio.run(_test())


class TestAsyncioBackendLoop:
    def test_loop_iterates(self):
        """LoopNode iterates children."""
        provider = FakeModelProvider(default="iteration")
        backend = AsyncioBackend(model_provider=provider)

        async def _test():
            loop = LoopNode(
                name="repeat", children=(AgentNode(name="worker", instruction="Do work"),), max_iterations=3
            )
            compiled = backend.compile(loop)
            events = await backend.run(compiled, "Go")

            contents = [e.content for e in events if e.content]
            assert len(contents) == 3

        asyncio.run(_test())


class TestAsyncioBackendTransform:
    def test_transform_updates_state(self):
        """TransformNode applies function to state."""
        backend = AsyncioBackend()

        async def _test():
            node = TransformNode(
                name="set_key",
                fn=lambda s: {**s, "greeting": "hello"},
            )
            compiled = backend.compile(node)
            events = await backend.run(compiled, "Go")

            state_events = [e for e in events if e.state_delta]
            assert len(state_events) == 1
            assert state_events[0].state_delta.get("greeting") == "hello"

        asyncio.run(_test())


class TestAsyncioBackendTap:
    def test_tap_no_state_mutation(self):
        """TapNode runs observation without mutating state."""
        observed: list[dict] = []
        backend = AsyncioBackend()

        async def _test():
            node = TapNode(name="observe", fn=lambda s: observed.append(dict(s)))
            compiled = backend.compile(node)
            events = await backend.run(compiled, "Go")

            assert len(observed) == 1
            assert not any(e.state_delta for e in events)

        asyncio.run(_test())


class TestAsyncioBackendFallback:
    def test_fallback_tries_children(self):
        """FallbackNode tries children in order."""
        provider = FakeModelProvider(default="fallback result")
        backend = AsyncioBackend(model_provider=provider)

        async def _test():
            fallback = FallbackNode(
                name="fallback",
                children=(
                    AgentNode(name="fast"),
                    AgentNode(name="slow"),
                ),
            )
            compiled = backend.compile(fallback)
            events = await backend.run(compiled, "Go")

            # First child succeeds, so only one result
            contents = [e.content for e in events if e.content]
            assert len(contents) == 1

        asyncio.run(_test())


class TestAsyncioBackendRegistry:
    def test_registered(self):
        from adk_fluent.backends import available_backends

        assert "asyncio" in available_backends()

    def test_get_backend(self):
        from adk_fluent.backends import get_backend

        backend = get_backend("asyncio")
        assert backend.name == "asyncio"


class TestAsyncioBackendCompileViaCompile:
    def test_compile_function(self):
        """compile() with backend="asyncio" works."""
        from adk_fluent.compile import compile

        ir = AgentNode(name="test")
        result = compile(ir, backend="asyncio")
        assert result.backend_name == "asyncio"
        assert result.capabilities.durable is False


class TestAsyncioBackendStream:
    def test_stream_yields_events(self):
        """stream() yields the same events as run()."""
        provider = FakeModelProvider(default="streamed")
        backend = AsyncioBackend(model_provider=provider)

        async def _test():
            node = AgentNode(name="test", instruction="Say hello")
            compiled = backend.compile(node)
            events = []
            async for event in backend.stream(compiled, "Hi"):
                events.append(event)
            assert any(e.content == "streamed" for e in events)

        asyncio.run(_test())


class TestAsyncioBackendFinalEvent:
    def test_last_event_is_final(self):
        """The last event is marked as final."""
        provider = FakeModelProvider(default="done")
        backend = AsyncioBackend(model_provider=provider)

        async def _test():
            node = AgentNode(name="test")
            compiled = backend.compile(node)
            events = await backend.run(compiled, "Hi")
            assert events[-1].is_final is True

        asyncio.run(_test())
