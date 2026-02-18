"""Tests for the ADK backend compiler."""
import pytest
from adk_fluent.backends.adk import ADKBackend
from adk_fluent._ir import TransformNode, TapNode, FallbackNode, RouteNode
from adk_fluent._ir_generated import AgentNode, SequenceNode, ParallelNode, LoopNode


@pytest.fixture
def backend():
    return ADKBackend()


def test_compile_agent_node(backend):
    from google.adk.agents.llm_agent import LlmAgent
    node = AgentNode(name="test", model="gemini-2.5-flash", instruction="Help")
    result = backend.compile(node)
    assert hasattr(result, 'root_agent')
    agent = result.root_agent
    assert isinstance(agent, LlmAgent)
    assert agent.name == "test"


def test_compile_sequence_node(backend):
    from google.adk.agents.sequential_agent import SequentialAgent
    children = (AgentNode(name="a"), AgentNode(name="b"))
    node = SequenceNode(name="pipe", children=children)
    result = backend.compile(node)
    agent = result.root_agent
    assert isinstance(agent, SequentialAgent)
    assert len(agent.sub_agents) == 2


def test_compile_parallel_node(backend):
    from google.adk.agents.parallel_agent import ParallelAgent
    children = (AgentNode(name="a"), AgentNode(name="b"))
    node = ParallelNode(name="fan", children=children)
    result = backend.compile(node)
    agent = result.root_agent
    assert isinstance(agent, ParallelAgent)


def test_compile_loop_node(backend):
    from google.adk.agents.loop_agent import LoopAgent
    body = AgentNode(name="step")
    node = LoopNode(name="loop", children=(body,), max_iterations=3)
    result = backend.compile(node)
    agent = result.root_agent
    assert isinstance(agent, LoopAgent)


def test_compile_transform_node(backend):
    from adk_fluent._base import FnAgent
    fn = lambda s: {"x": 1}
    node = TransformNode(name="t", fn=fn)
    result = backend.compile(node)
    agent = result.root_agent
    assert isinstance(agent, FnAgent)


def test_compile_tap_node(backend):
    from adk_fluent._base import TapAgent
    fn = lambda s: None
    node = TapNode(name="tap", fn=fn)
    result = backend.compile(node)
    agent = result.root_agent
    assert isinstance(agent, TapAgent)


def test_compile_nested_ir(backend):
    """Nested IR trees should compile recursively."""
    from google.adk.agents.sequential_agent import SequentialAgent

    inner = SequenceNode(name="inner", children=(
        AgentNode(name="a"), AgentNode(name="b")
    ))
    outer = SequenceNode(name="outer", children=(
        AgentNode(name="pre"), inner, AgentNode(name="post")
    ))
    result = backend.compile(outer)
    agent = result.root_agent
    assert isinstance(agent, SequentialAgent)
    assert isinstance(agent.sub_agents[1], SequentialAgent)


def test_compile_with_execution_config(backend):
    from adk_fluent._ir import ExecutionConfig
    node = AgentNode(name="test")
    config = ExecutionConfig(app_name="myapp")
    result = backend.compile(node, config=config)
    assert result.name == "myapp"


def test_round_trip_builder_to_ir_to_adk(backend):
    """Full round-trip: builder -> IR -> ADK object."""
    from adk_fluent import Agent
    from google.adk.agents.llm_agent import LlmAgent

    builder = Agent("classifier", "gemini-2.5-flash").instruct("Classify intent")
    ir = builder.to_ir()
    compiled = backend.compile(ir)
    agent = compiled.root_agent
    assert isinstance(agent, LlmAgent)
    assert agent.name == "classifier"


def test_compile_fallback_node(backend):
    from adk_fluent._base import FallbackAgent
    children = (AgentNode(name="primary"), AgentNode(name="backup"))
    node = FallbackNode(name="fb", children=children)
    result = backend.compile(node)
    agent = result.root_agent
    assert isinstance(agent, FallbackAgent)
    assert len(agent.sub_agents) == 2


def test_compile_gate_node(backend):
    from adk_fluent._base import GateAgent
    from adk_fluent._ir import GateNode
    pred = lambda s: s.get("risk") == "high"
    node = GateNode(name="gate", predicate=pred, message="Approve?", gate_key="_gate")
    result = backend.compile(node)
    agent = result.root_agent
    assert isinstance(agent, GateAgent)


def test_compile_mapover_node(backend):
    from adk_fluent._base import MapOverAgent
    from adk_fluent._ir import MapOverNode
    body = AgentNode(name="summarizer")
    node = MapOverNode(name="mapper", list_key="items", body=body, item_key="_item", output_key="results")
    result = backend.compile(node)
    agent = result.root_agent
    assert isinstance(agent, MapOverAgent)


def test_compile_timeout_node(backend):
    from adk_fluent._base import TimeoutAgent
    from adk_fluent._ir import TimeoutNode
    body = AgentNode(name="slow")
    node = TimeoutNode(name="timed", body=body, seconds=30.0)
    result = backend.compile(node)
    agent = result.root_agent
    assert isinstance(agent, TimeoutAgent)


def test_compile_race_node(backend):
    from adk_fluent._base import RaceAgent
    from adk_fluent._ir import RaceNode
    children = (AgentNode(name="fast"), AgentNode(name="slow"))
    node = RaceNode(name="racer", children=children)
    result = backend.compile(node)
    agent = result.root_agent
    assert isinstance(agent, RaceAgent)
    assert len(agent.sub_agents) == 2


def test_compile_route_node(backend):
    from adk_fluent._ir import RouteNode
    pred = lambda s: s.get("intent") == "book"
    target = AgentNode(name="booker")
    node = RouteNode(name="router", key="intent", rules=((pred, target),), default=None)
    result = backend.compile(node)
    # RouteAgent is created via closure, check it has sub_agents
    agent = result.root_agent
    assert agent.name == "router"
    assert len(agent.sub_agents) == 1


def test_compile_transfer_node(backend):
    from adk_fluent._ir import TransferNode
    node = TransferNode(name="xfer", target="other_agent")
    result = backend.compile(node)
    agent = result.root_agent
    assert agent.name == "xfer"


def test_backend_satisfies_protocol(backend):
    from adk_fluent.backends._protocol import Backend
    assert isinstance(backend, Backend)


def test_compile_agent_node_with_callbacks(backend):
    """AgentNode with callbacks should pass them through to the LlmAgent."""
    from google.adk.agents.llm_agent import LlmAgent
    cb = lambda ctx: None
    node = AgentNode(
        name="cbtest",
        model="gemini-2.5-flash",
        callbacks={"before_agent_callback": (cb,)},
    )
    result = backend.compile(node)
    agent = result.root_agent
    assert isinstance(agent, LlmAgent)
    assert agent.before_agent_callback is not None


def test_compile_agent_node_with_tools(backend):
    """AgentNode with tools should pass them through."""
    from google.adk.agents.llm_agent import LlmAgent

    def my_tool() -> str:
        """A sample tool."""
        return "result"

    node = AgentNode(name="tooltest", model="gemini-2.5-flash", tools=(my_tool,))
    result = backend.compile(node)
    agent = result.root_agent
    assert isinstance(agent, LlmAgent)
    assert len(agent.tools) == 1


def test_default_app_name(backend):
    """Without ExecutionConfig, default app name should be used."""
    node = AgentNode(name="test")
    result = backend.compile(node)
    assert result.name == "adk_fluent_app"


def test_compile_resumable_config(backend):
    from adk_fluent._ir import ExecutionConfig
    node = AgentNode(name="test")
    config = ExecutionConfig(app_name="myapp", resumable=True)
    result = backend.compile(node, config=config)
    assert result.resumability_config is not None
    assert result.resumability_config.is_resumable is True
