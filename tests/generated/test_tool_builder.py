"""Auto-generated builder-mechanics tests. Verify fluent API surface without constructing ADK objects."""

import pytest  # noqa: F401 (used inside test methods)

from adk_fluent.tool import ActiveStreamingTool
from adk_fluent.tool import AgentTool
from adk_fluent.tool import APIHubToolset
from adk_fluent.tool import ApplicationIntegrationToolset
from adk_fluent.tool import IntegrationConnectorTool
from adk_fluent.tool import BaseAuthenticatedTool
from adk_fluent.tool import BaseTool
from adk_fluent.tool import BaseToolset
from adk_fluent.tool import BigQueryToolset
from adk_fluent.tool import BigtableToolset
from adk_fluent.tool import ComputerUseTool
from adk_fluent.tool import ComputerUseToolset
from adk_fluent.tool import DataAgentToolset
from adk_fluent.tool import DiscoveryEngineSearchTool
from adk_fluent.tool import EnterpriseWebSearchTool
from adk_fluent.tool import ExampleTool
from adk_fluent.tool import FunctionTool
from adk_fluent.tool import GoogleApiTool
from adk_fluent.tool import GoogleApiToolset
from adk_fluent.tool import CalendarToolset
from adk_fluent.tool import DocsToolset
from adk_fluent.tool import GmailToolset
from adk_fluent.tool import SheetsToolset
from adk_fluent.tool import SlidesToolset
from adk_fluent.tool import YoutubeToolset
from adk_fluent.tool import GoogleMapsGroundingTool
from adk_fluent.tool import GoogleSearchAgentTool
from adk_fluent.tool import GoogleSearchTool
from adk_fluent.tool import GoogleTool
from adk_fluent.tool import LoadArtifactsTool
from adk_fluent.tool import LoadMcpResourceTool
from adk_fluent.tool import LoadMemoryTool
from adk_fluent.tool import LongRunningFunctionTool
from adk_fluent.tool import MCPTool
from adk_fluent.tool import McpTool
from adk_fluent.tool import MCPToolset
from adk_fluent.tool import McpToolset
from adk_fluent.tool import OpenAPIToolset
from adk_fluent.tool import RestApiTool
from adk_fluent.tool import PreloadMemoryTool
from adk_fluent.tool import PubSubToolset
from adk_fluent.tool import BaseRetrievalTool
from adk_fluent.tool import SetModelResponseTool
from adk_fluent.tool import LoadSkillResourceTool
from adk_fluent.tool import LoadSkillTool
from adk_fluent.tool import SkillToolset
from adk_fluent.tool import SpannerToolset
from adk_fluent.tool import ToolboxToolset
from adk_fluent.tool import TransferToAgentTool
from adk_fluent.tool import UrlContextTool
from adk_fluent.tool import VertexAiSearchTool


class TestActiveStreamingToolBuilder:
    """Tests for ActiveStreamingTool builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = ActiveStreamingTool()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.task() returns the builder instance for chaining."""
        builder = ActiveStreamingTool()
        result = builder.task(None)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .task() stores the value in builder._config."""
        builder = ActiveStreamingTool()
        builder.task(None)
        assert builder._config["task"] == None


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = ActiveStreamingTool()
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestAgentToolBuilder:
    """Tests for AgentTool builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = AgentTool('test_agent')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.skip_summarization() returns the builder instance for chaining."""
        builder = AgentTool('test_agent')
        result = builder.skip_summarization(True)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .skip_summarization() stores the value in builder._config."""
        builder = AgentTool('test_agent')
        builder.skip_summarization(True)
        assert builder._config["skip_summarization"] == True


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = AgentTool('test_agent')
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestAPIHubToolsetBuilder:
    """Tests for APIHubToolset builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = APIHubToolset('test_apihub_resource_name')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.name() returns the builder instance for chaining."""
        builder = APIHubToolset('test_apihub_resource_name')
        result = builder.name("test_value")
        assert result is builder


    def test_config_accumulation(self):
        """Setting .name() stores the value in builder._config."""
        builder = APIHubToolset('test_apihub_resource_name')
        builder.name("test_value")
        assert builder._config["name"] == "test_value"


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = APIHubToolset('test_apihub_resource_name')
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestApplicationIntegrationToolsetBuilder:
    """Tests for ApplicationIntegrationToolset builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = ApplicationIntegrationToolset('test_project', 'test_location')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = ApplicationIntegrationToolset('test_project', 'test_location')
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestIntegrationConnectorToolBuilder:
    """Tests for IntegrationConnectorTool builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = IntegrationConnectorTool('test_name', 'test_description', 'test_connection_name')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.connection_host() returns the builder instance for chaining."""
        builder = IntegrationConnectorTool('test_name', 'test_description', 'test_connection_name')
        result = builder.connection_host("test_value")
        assert result is builder


    def test_config_accumulation(self):
        """Setting .connection_host() stores the value in builder._config."""
        builder = IntegrationConnectorTool('test_name', 'test_description', 'test_connection_name')
        builder.connection_host("test_value")
        assert builder._config["connection_host"] == "test_value"


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = IntegrationConnectorTool('test_name', 'test_description', 'test_connection_name')
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestBaseAuthenticatedToolBuilder:
    """Tests for BaseAuthenticatedTool builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = BaseAuthenticatedTool('test_name', 'test_description')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = BaseAuthenticatedTool('test_name', 'test_description')
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestBaseToolBuilder:
    """Tests for BaseTool builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = BaseTool('test_name', 'test_description')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.is_long_running() returns the builder instance for chaining."""
        builder = BaseTool('test_name', 'test_description')
        result = builder.is_long_running(True)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .is_long_running() stores the value in builder._config."""
        builder = BaseTool('test_name', 'test_description')
        builder.is_long_running(True)
        assert builder._config["is_long_running"] == True


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = BaseTool('test_name', 'test_description')
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestBaseToolsetBuilder:
    """Tests for BaseToolset builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = BaseToolset()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = BaseToolset()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestBigQueryToolsetBuilder:
    """Tests for BigQueryToolset builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = BigQueryToolset()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = BigQueryToolset()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestBigtableToolsetBuilder:
    """Tests for BigtableToolset builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = BigtableToolset()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = BigtableToolset()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestComputerUseToolBuilder:
    """Tests for ComputerUseTool builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = ComputerUseTool('test_func', 'test_screen_size')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = ComputerUseTool('test_func', 'test_screen_size')
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestComputerUseToolsetBuilder:
    """Tests for ComputerUseToolset builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = ComputerUseToolset('test_computer')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = ComputerUseToolset('test_computer')
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestDataAgentToolsetBuilder:
    """Tests for DataAgentToolset builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = DataAgentToolset()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = DataAgentToolset()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestDiscoveryEngineSearchToolBuilder:
    """Tests for DiscoveryEngineSearchTool builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = DiscoveryEngineSearchTool()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = DiscoveryEngineSearchTool()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestEnterpriseWebSearchToolBuilder:
    """Tests for EnterpriseWebSearchTool builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = EnterpriseWebSearchTool()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = EnterpriseWebSearchTool()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestExampleToolBuilder:
    """Tests for ExampleTool builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = ExampleTool('test_examples')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = ExampleTool('test_examples')
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestFunctionToolBuilder:
    """Tests for FunctionTool builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = FunctionTool('test_func')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = FunctionTool('test_func')
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestGoogleApiToolBuilder:
    """Tests for GoogleApiTool builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = GoogleApiTool('test_rest_api_tool')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = GoogleApiTool('test_rest_api_tool')
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestGoogleApiToolsetBuilder:
    """Tests for GoogleApiToolset builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = GoogleApiToolset('test_api_name', 'test_api_version')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = GoogleApiToolset('test_api_name', 'test_api_version')
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestCalendarToolsetBuilder:
    """Tests for CalendarToolset builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = CalendarToolset()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = CalendarToolset()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestDocsToolsetBuilder:
    """Tests for DocsToolset builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = DocsToolset()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = DocsToolset()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestGmailToolsetBuilder:
    """Tests for GmailToolset builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = GmailToolset()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = GmailToolset()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestSheetsToolsetBuilder:
    """Tests for SheetsToolset builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = SheetsToolset()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = SheetsToolset()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestSlidesToolsetBuilder:
    """Tests for SlidesToolset builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = SlidesToolset()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = SlidesToolset()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestYoutubeToolsetBuilder:
    """Tests for YoutubeToolset builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = YoutubeToolset()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = YoutubeToolset()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestGoogleMapsGroundingToolBuilder:
    """Tests for GoogleMapsGroundingTool builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = GoogleMapsGroundingTool()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = GoogleMapsGroundingTool()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestGoogleSearchAgentToolBuilder:
    """Tests for GoogleSearchAgentTool builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = GoogleSearchAgentTool('test_agent')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = GoogleSearchAgentTool('test_agent')
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestGoogleSearchToolBuilder:
    """Tests for GoogleSearchTool builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = GoogleSearchTool()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.bypass_multi_tools_limit() returns the builder instance for chaining."""
        builder = GoogleSearchTool()
        result = builder.bypass_multi_tools_limit(True)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .bypass_multi_tools_limit() stores the value in builder._config."""
        builder = GoogleSearchTool()
        builder.bypass_multi_tools_limit(True)
        assert builder._config["bypass_multi_tools_limit"] == True


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = GoogleSearchTool()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestGoogleToolBuilder:
    """Tests for GoogleTool builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = GoogleTool('test_func')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = GoogleTool('test_func')
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestLoadArtifactsToolBuilder:
    """Tests for LoadArtifactsTool builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = LoadArtifactsTool()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = LoadArtifactsTool()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestLoadMcpResourceToolBuilder:
    """Tests for LoadMcpResourceTool builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = LoadMcpResourceTool('test_mcp_toolset')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = LoadMcpResourceTool('test_mcp_toolset')
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestLoadMemoryToolBuilder:
    """Tests for LoadMemoryTool builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = LoadMemoryTool()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = LoadMemoryTool()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestLongRunningFunctionToolBuilder:
    """Tests for LongRunningFunctionTool builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = LongRunningFunctionTool('test_func')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = LongRunningFunctionTool('test_func')
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestMCPToolBuilder:
    """Tests for MCPTool builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = MCPTool('test_args', 'test_kwargs')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = MCPTool('test_args', 'test_kwargs')
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestMcpToolBuilder:
    """Tests for McpTool builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = McpTool('test_mcp_tool', 'test_mcp_session_manager')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = McpTool('test_mcp_tool', 'test_mcp_session_manager')
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestMCPToolsetBuilder:
    """Tests for MCPToolset builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = MCPToolset('test_args', 'test_kwargs')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = MCPToolset('test_args', 'test_kwargs')
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestMcpToolsetBuilder:
    """Tests for McpToolset builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = McpToolset('test_connection_params')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = McpToolset('test_connection_params')
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestOpenAPIToolsetBuilder:
    """Tests for OpenAPIToolset builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = OpenAPIToolset()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = OpenAPIToolset()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestRestApiToolBuilder:
    """Tests for RestApiTool builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = RestApiTool('test_name', 'test_description', 'test_endpoint')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = RestApiTool('test_name', 'test_description', 'test_endpoint')
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestPreloadMemoryToolBuilder:
    """Tests for PreloadMemoryTool builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = PreloadMemoryTool()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = PreloadMemoryTool()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestPubSubToolsetBuilder:
    """Tests for PubSubToolset builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = PubSubToolset()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.tool_filter() returns the builder instance for chaining."""
        builder = PubSubToolset()
        result = builder.tool_filter(None)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .tool_filter() stores the value in builder._config."""
        builder = PubSubToolset()
        builder.tool_filter(None)
        assert builder._config["tool_filter"] == None


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = PubSubToolset()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestBaseRetrievalToolBuilder:
    """Tests for BaseRetrievalTool builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = BaseRetrievalTool('test_name', 'test_description')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.is_long_running() returns the builder instance for chaining."""
        builder = BaseRetrievalTool('test_name', 'test_description')
        result = builder.is_long_running(True)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .is_long_running() stores the value in builder._config."""
        builder = BaseRetrievalTool('test_name', 'test_description')
        builder.is_long_running(True)
        assert builder._config["is_long_running"] == True


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = BaseRetrievalTool('test_name', 'test_description')
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestSetModelResponseToolBuilder:
    """Tests for SetModelResponseTool builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = SetModelResponseTool('test_output_schema')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = SetModelResponseTool('test_output_schema')
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestLoadSkillResourceToolBuilder:
    """Tests for LoadSkillResourceTool builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = LoadSkillResourceTool('test_toolset')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = LoadSkillResourceTool('test_toolset')
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestLoadSkillToolBuilder:
    """Tests for LoadSkillTool builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = LoadSkillTool('test_toolset')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = LoadSkillTool('test_toolset')
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestSkillToolsetBuilder:
    """Tests for SkillToolset builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = SkillToolset('test_skills')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = SkillToolset('test_skills')
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestSpannerToolsetBuilder:
    """Tests for SpannerToolset builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = SpannerToolset()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = SpannerToolset()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestToolboxToolsetBuilder:
    """Tests for ToolboxToolset builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = ToolboxToolset('test_server_url', 'test_kwargs')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = ToolboxToolset('test_server_url', 'test_kwargs')
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestTransferToAgentToolBuilder:
    """Tests for TransferToAgentTool builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = TransferToAgentTool('test_agent_names')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = TransferToAgentTool('test_agent_names')
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestUrlContextToolBuilder:
    """Tests for UrlContextTool builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = UrlContextTool()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = UrlContextTool()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestVertexAiSearchToolBuilder:
    """Tests for VertexAiSearchTool builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = VertexAiSearchTool()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.bypass_multi_tools_limit() returns the builder instance for chaining."""
        builder = VertexAiSearchTool()
        result = builder.bypass_multi_tools_limit(True)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .bypass_multi_tools_limit() stores the value in builder._config."""
        builder = VertexAiSearchTool()
        builder.bypass_multi_tools_limit(True)
        assert builder._config["bypass_multi_tools_limit"] == True


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        import pytest
        builder = VertexAiSearchTool()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")
