"""Tests for to_ir() on generated builders (Pipeline, FanOut, Loop)."""
from adk_fluent._ir_generated import AgentNode, SequenceNode, ParallelNode, LoopNode


def test_pipeline_to_ir():
    from adk_fluent import Agent
    pipeline = Agent("a") >> Agent("b") >> Agent("c")
    ir = pipeline.to_ir()
    assert isinstance(ir, SequenceNode)
    assert len(ir.children) == 3
    assert all(isinstance(c, AgentNode) for c in ir.children)


def test_pipeline_with_fn_step():
    from adk_fluent import Agent
    from adk_fluent._ir import TransformNode
    pipeline = Agent("a") >> (lambda s: {"x": 1}) >> Agent("b")
    ir = pipeline.to_ir()
    assert isinstance(ir, SequenceNode)
    assert isinstance(ir.children[1], TransformNode)


def test_fanout_to_ir():
    from adk_fluent import Agent
    fanout = Agent("a") | Agent("b")
    ir = fanout.to_ir()
    assert isinstance(ir, ParallelNode)
    assert len(ir.children) == 2


def test_loop_to_ir():
    from adk_fluent import Agent
    loop = Agent("step") * 5
    ir = loop.to_ir()
    assert isinstance(ir, LoopNode)
    assert ir.max_iterations == 5


def test_nested_pipeline_to_ir():
    """Nested structures should recursively convert."""
    from adk_fluent import Agent
    pipeline = Agent("a") >> (Agent("b") | Agent("c")) >> Agent("d")
    ir = pipeline.to_ir()
    assert isinstance(ir, SequenceNode)
    assert isinstance(ir.children[1], ParallelNode)


def test_pipeline_name():
    """Pipeline IR should carry the builder name."""
    from adk_fluent import Agent
    pipeline = Agent("a") >> Agent("b")
    ir = pipeline.to_ir()
    assert isinstance(ir, SequenceNode)
    assert ir.name  # should have some name


def test_fanout_children_are_agent_nodes():
    """FanOut children should be recursively converted."""
    from adk_fluent import Agent
    fanout = Agent("x") | Agent("y") | Agent("z")
    ir = fanout.to_ir()
    assert isinstance(ir, ParallelNode)
    assert len(ir.children) == 3
    assert all(isinstance(c, AgentNode) for c in ir.children)


def test_loop_body_converted():
    """Loop children should be recursively converted to IR nodes."""
    from adk_fluent import Agent
    loop = Agent("step") * 3
    ir = loop.to_ir()
    assert isinstance(ir, LoopNode)
    assert len(ir.children) == 1
    assert isinstance(ir.children[0], AgentNode)


def test_loop_pipeline_body():
    """A pipeline looped should have all steps as children in the LoopNode."""
    from adk_fluent import Agent
    loop = (Agent("a") >> Agent("b")) * 3
    ir = loop.to_ir()
    assert isinstance(ir, LoopNode)
    assert ir.max_iterations == 3
    assert len(ir.children) == 2
    assert all(isinstance(c, AgentNode) for c in ir.children)
