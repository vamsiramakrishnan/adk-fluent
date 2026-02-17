"""Tests for @agent decorator."""
from adk_fluent.decorators import agent
from adk_fluent.agent import Agent as AgentBuilder


def _before_model_cb(ctx):
    pass


def _another_cb(ctx):
    pass


class TestAgentDecorator:
    def test_returns_agent_builder(self):
        @agent("solver")
        def solver():
            """You are a solver."""
            pass

        assert isinstance(solver, AgentBuilder)

    def test_docstring_becomes_instruction(self):
        @agent("solver")
        def solver():
            """You are a math solver."""
            pass

        assert solver._config["instruction"] == "You are a math solver."

    def test_kwargs_applied(self):
        @agent("solver", model="gemini-2.5-flash")
        def solver():
            """Solve things."""
            pass

        assert solver._config["model"] == "gemini-2.5-flash"

    def test_tool_decorator_adds_to_tools(self):
        @agent("solver")
        def solver():
            """Solve things."""
            pass

        @solver.tool
        def add(a: int, b: int) -> int:
            return a + b

        assert add in solver._lists["tools"]

    def test_tool_decorator_preserves_function(self):
        @agent("solver")
        def solver():
            """Solve things."""
            pass

        @solver.tool
        def add(a: int, b: int) -> int:
            return a + b

        # The decorator should return the original function
        assert callable(add)
        assert add(2, 3) == 5

    def test_on_decorator_adds_callback(self):
        @agent("solver")
        def solver():
            """Solve things."""
            pass

        @solver.on("before_model")
        def my_cb(ctx):
            pass

        assert my_cb in solver._callbacks["before_model_callback"]

    def test_on_decorator_preserves_function(self):
        @agent("solver")
        def solver():
            """Solve things."""
            pass

        @solver.on("before_model")
        def my_cb(ctx):
            return 42

        assert callable(my_cb)
        assert my_cb(None) == 42

    def test_no_docstring_no_instruction(self):
        @agent("solver")
        def solver():
            pass

        assert "instruction" not in solver._config

    def test_multiple_tools_accumulate(self):
        @agent("solver")
        def solver():
            """Solve things."""
            pass

        @solver.tool
        def add(a: int, b: int) -> int:
            return a + b

        @solver.tool
        def multiply(a: int, b: int) -> int:
            return a * b

        assert len(solver._lists["tools"]) == 2
        assert add in solver._lists["tools"]
        assert multiply in solver._lists["tools"]
