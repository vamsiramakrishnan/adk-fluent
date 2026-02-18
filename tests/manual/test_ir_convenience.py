"""Tests for IR convenience methods on builders."""

from adk_fluent import Agent


def test_to_app_returns_adk_app():
    from google.adk.apps.app import App

    pipeline = Agent("a") >> Agent("b")
    app = pipeline.to_app()
    assert isinstance(app, App)
    assert app.name == "adk_fluent_app"


def test_to_app_with_custom_name():
    from adk_fluent._ir import ExecutionConfig

    pipeline = Agent("a")
    app = pipeline.to_app(ExecutionConfig(app_name="my_app"))
    assert app.name == "my_app"


def test_build_still_returns_adk_object():
    """build() must remain unchanged for backward compat."""
    from google.adk.agents.llm_agent import LlmAgent

    agent = Agent("test", "gemini-2.5-flash")
    built = agent.build()
    assert isinstance(built, LlmAgent)


def test_to_ir_on_agent():
    from adk_fluent._ir_generated import AgentNode

    ir = Agent("test").to_ir()
    assert isinstance(ir, AgentNode)


def test_exports_available():
    """New IR/backend types should be importable from adk_fluent."""
    from adk_fluent import ADKBackend, AgentEvent, Backend, CompactionConfig, ExecutionConfig, final_text

    assert ExecutionConfig is not None
    assert CompactionConfig is not None
    assert AgentEvent is not None
    assert Backend is not None
    assert ADKBackend is not None
    assert final_text is not None
