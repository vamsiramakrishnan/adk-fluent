"""Tests for FEATURE #8 -- T-namespace factories wrapping ADK toolsets/tools.

Covers the additive T.* factories for high-value ADK toolsets:
bigquery / spanner / bigtable / vertex_ai_search / vertex_search /
enterprise_search / url_context / computer_use.

These assert:
- each factory returns a composable ``TComposite``
- the underlying object is the right ADK class (no network/cloud I/O)
- composability via ``|`` flattens correctly
- credential/dependency-gated factories (BigQuery/Spanner/Bigtable) construct
  lazily and surface a clear error when client extras are missing
"""

from __future__ import annotations

import pytest

from adk_fluent import T
from adk_fluent._tools import TComposite


# ---------------------------------------------------------------------------
# Search / grounding tools (no credentials required to construct)
# ---------------------------------------------------------------------------


def test_vertex_ai_search_returns_composite_with_right_class():
    from google.adk.tools.vertex_ai_search_tool import VertexAiSearchTool

    comp = T.vertex_ai_search(
        data_store_id="projects/p/locations/l/collections/c/dataStores/d"
    )
    assert isinstance(comp, TComposite)
    tools = comp.to_tools()
    assert len(tools) == 1
    assert isinstance(tools[0], VertexAiSearchTool)


def test_vertex_ai_search_passes_through_args():
    comp = T.vertex_ai_search(
        data_store_id="projects/p/locations/l/collections/c/dataStores/d",
        max_results=7,
        bypass_multi_tools_limit=True,
    )
    tool = comp.to_tools()[0]
    # ADK stores these on the tool instance.
    assert tool.max_results == 7
    assert tool.bypass_multi_tools_limit is True


def test_vertex_search_alias_is_same_factory():
    from google.adk.tools.vertex_ai_search_tool import VertexAiSearchTool

    comp = T.vertex_search(
        data_store_id="projects/p/locations/l/collections/c/dataStores/d"
    )
    assert isinstance(comp, TComposite)
    assert isinstance(comp.to_tools()[0], VertexAiSearchTool)


def test_enterprise_search_returns_composite_with_right_class():
    from google.adk.tools.enterprise_search_tool import EnterpriseWebSearchTool

    comp = T.enterprise_search()
    assert isinstance(comp, TComposite)
    tools = comp.to_tools()
    assert len(tools) == 1
    assert isinstance(tools[0], EnterpriseWebSearchTool)


def test_url_context_returns_composite_with_right_class():
    from google.adk.tools.url_context_tool import UrlContextTool

    comp = T.url_context()
    assert isinstance(comp, TComposite)
    tools = comp.to_tools()
    assert len(tools) == 1
    assert isinstance(tools[0], UrlContextTool)


# ---------------------------------------------------------------------------
# Composability
# ---------------------------------------------------------------------------


def test_factories_compose_with_pipe_and_flatten():
    from google.adk.tools.function_tool import FunctionTool
    from google.adk.tools.url_context_tool import UrlContextTool
    from google.adk.tools.vertex_ai_search_tool import VertexAiSearchTool

    def my_fn(x: str) -> str:
        """A tool."""
        return x

    chain = (
        T.vertex_ai_search(data_store_id="projects/p/locations/l/collections/c/dataStores/d")
        | T.fn(my_fn)
        | T.url_context()
    )
    assert isinstance(chain, TComposite)
    tools = chain.to_tools()
    assert len(tools) == 3
    assert isinstance(tools[0], VertexAiSearchTool)
    assert isinstance(tools[1], FunctionTool)
    assert isinstance(tools[2], UrlContextTool)


def test_composite_usable_in_agent_tools():
    from adk_fluent import Agent

    agent = (
        Agent("searcher", "gemini-2.5-flash")
        .instruct("Search.")
        .tools(T.enterprise_search() | T.url_context())
        .build()
    )
    assert len(agent.tools) == 2


# ---------------------------------------------------------------------------
# Computer use
# ---------------------------------------------------------------------------


def _make_fake_computer():
    from google.adk.tools.computer_use.base_computer import (
        BaseComputer,
        ComputerEnvironment,
    )

    class FakeComputer(BaseComputer):
        async def screen_size(self):
            return (1920, 1080)

        async def environment(self):
            return ComputerEnvironment.ENVIRONMENT_BROWSER

        async def open_web_browser(self): ...
        async def click_at(self, x, y): ...
        async def hover_at(self, x, y): ...
        async def type_text_at(
            self, x, y, text, press_enter=True, clear_before_typing=True
        ): ...
        async def scroll_document(self, direction): ...
        async def scroll_at(self, x, y, direction, magnitude): ...
        async def wait(self, seconds): ...
        async def go_back(self): ...
        async def go_forward(self): ...
        async def search(self): ...
        async def navigate(self, url): ...
        async def key_combination(self, keys): ...
        async def drag_and_drop(self, x, y, destination_x, destination_y): ...
        async def current_state(self): ...

    return FakeComputer()


def test_computer_use_returns_composite_with_right_class():
    from google.adk.tools.computer_use.computer_use_toolset import ComputerUseToolset

    comp = T.computer_use(_make_fake_computer())
    assert isinstance(comp, TComposite)
    tools = comp.to_tools()
    assert len(tools) == 1
    assert isinstance(tools[0], ComputerUseToolset)


# ---------------------------------------------------------------------------
# Google Cloud data toolsets (credential/dependency-gated)
# ---------------------------------------------------------------------------
#
# BigQuery/Spanner/Bigtable toolsets require the corresponding
# ``google-cloud-*`` client libraries, which are not installed in the test
# environment. We assert lazy construction: the factory only fails when those
# extras are missing, and the error is the underlying import error (clear).


def _gcloud_available() -> bool:
    try:
        import google.cloud  # noqa: F401

        return True
    except ImportError:
        return False


@pytest.mark.parametrize(
    "factory",
    [T.bigquery, T.spanner, T.bigtable],
)
def test_gcloud_toolsets_construct_or_raise_clearly(factory):
    if _gcloud_available():
        from google.adk.tools.base_toolset import BaseToolset

        comp = factory()
        assert isinstance(comp, TComposite)
        assert isinstance(comp.to_tools()[0], BaseToolset)
    else:
        # Lazy: failure happens only at call time, with a clear import error
        # pointing at the missing google.cloud client extras.
        with pytest.raises(ModuleNotFoundError) as exc:
            factory()
        assert "google.cloud" in str(exc.value)


def test_gcloud_factories_do_not_import_at_module_load():
    # The T factories import ADK toolsets lazily inside the method body, so
    # merely referencing them must not raise even without google.cloud.
    assert callable(T.bigquery)
    assert callable(T.spanner)
    assert callable(T.bigtable)
