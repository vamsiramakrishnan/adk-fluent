"""Tests for ToolConfirmation pass-through."""


def greet(name: str) -> str:
    return f"Hello, {name}!"


def test_tool_with_require_confirmation():
    """Agent.tool(fn, require_confirmation=True) wraps in FunctionTool with flag."""
    from adk_fluent import Agent
    a = Agent("a").tool(greet, require_confirmation=True)
    built = a.build()
    from google.adk.tools.function_tool import FunctionTool
    tool = built.tools[0]
    assert isinstance(tool, FunctionTool)
    assert tool._require_confirmation is True


def test_tool_without_confirmation_unchanged():
    """Agent.tool(fn) without flag still works as before."""
    from adk_fluent import Agent
    a = Agent("a").tool(greet)
    built = a.build()
    tools = built.tools
    assert len(tools) == 1


def test_tool_confirmation_chainable():
    """tool() with require_confirmation returns self."""
    from adk_fluent import Agent
    a = Agent("a")
    result = a.tool(greet, require_confirmation=True)
    assert result is a


def test_tool_confirmation_in_ir():
    """FunctionTool with confirmation is preserved through IR."""
    from adk_fluent import Agent
    from google.adk.tools.function_tool import FunctionTool
    a = Agent("a").tool(greet, require_confirmation=True)
    ir = a.to_ir()
    assert len(ir.tools) == 1
    assert isinstance(ir.tools[0], FunctionTool)
    assert ir.tools[0]._require_confirmation is True
