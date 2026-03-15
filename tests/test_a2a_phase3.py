"""Tests for A2A Phase 3: Discovery & Lifecycle.

Tests verify:
1. RemoteAgent.discover() — well-known URL discovery
2. RemoteAgent env= parameter — environment-based configuration
3. AgentRegistry — registry-based discovery
4. A2AServer.health_check() — health check endpoints
5. A2AServer.graceful_shutdown() — graceful shutdown
6. Updated exports in __init__ and prelude
"""

import warnings

import pytest

from adk_fluent.a2a import A2AServer, AgentRegistry, RemoteAgent
from adk_fluent.agent import Agent

# ======================================================================
# 1. RemoteAgent.discover()
# ======================================================================


class TestRemoteAgentDiscover:
    """Tests for well-known URL discovery."""

    def test_discover_creates_builder(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = RemoteAgent.discover("helper", "helper.agents.acme.com")
        assert isinstance(builder, RemoteAgent)
        assert builder._config["name"] == "helper"
        assert builder._config["agent_card"] == "https://helper.agents.acme.com/.well-known/agent.json"

    def test_discover_custom_protocol(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = RemoteAgent.discover("helper", "helper.local", protocol="http")
        assert builder._config["agent_card"] == "http://helper.local/.well-known/agent.json"

    def test_discover_custom_path(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = RemoteAgent.discover(
                "helper", "acme.com", path="/.well-known/agent-card.json"
            )
        assert builder._config["agent_card"] == "https://acme.com/.well-known/agent-card.json"

    def test_discover_chainable(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = (
                RemoteAgent.discover("helper", "helper.acme.com")
                .describe("Research helper")
                .timeout(120)
            )
        assert builder._config["description"] == "Research helper"
        assert builder._config["timeout"] == 120

    def test_discover_with_operators(self):
        """Discovered agent works with >> operator."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            local = Agent("coordinator")
            remote = RemoteAgent.discover("helper", "helper.acme.com")
            pipeline = local >> remote
        assert pipeline is not None
        assert hasattr(pipeline, "build")


# ======================================================================
# 2. RemoteAgent env= parameter
# ======================================================================


class TestRemoteAgentEnv:
    """Tests for environment-based configuration."""

    def test_env_reads_url(self, monkeypatch):
        monkeypatch.setenv("HELPER_URL", "http://helper:8001")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = RemoteAgent("helper", env="HELPER_URL")
        assert builder._config["agent_card"] == "http://helper:8001"

    def test_env_strips_whitespace(self, monkeypatch):
        monkeypatch.setenv("HELPER_URL", "  http://helper:8001  ")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = RemoteAgent("helper", env="HELPER_URL")
        assert builder._config["agent_card"] == "http://helper:8001"

    def test_env_missing_logs_warning(self, monkeypatch):
        monkeypatch.delenv("MISSING_VAR", raising=False)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = RemoteAgent("helper", env="MISSING_VAR")
        assert "agent_card" not in builder._config

    def test_env_empty_raises(self, monkeypatch):
        monkeypatch.setenv("EMPTY_VAR", "")
        with pytest.raises(ValueError, match="set but empty"), warnings.catch_warnings():
            warnings.simplefilter("ignore")
            RemoteAgent("helper", env="EMPTY_VAR")

    def test_env_whitespace_only_raises(self, monkeypatch):
        monkeypatch.setenv("WS_VAR", "   ")
        with pytest.raises(ValueError, match="set but empty"), warnings.catch_warnings():
            warnings.simplefilter("ignore")
            RemoteAgent("helper", env="WS_VAR")

    def test_explicit_url_takes_precedence(self, monkeypatch):
        """agent_card arg takes precedence over env."""
        monkeypatch.setenv("HELPER_URL", "http://from-env:8001")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = RemoteAgent("helper", "http://explicit:8001", env="HELPER_URL")
        assert builder._config["agent_card"] == "http://explicit:8001"

    def test_env_chainable(self, monkeypatch):
        monkeypatch.setenv("HELPER_URL", "http://helper:8001")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = RemoteAgent("helper", env="HELPER_URL").timeout(30).describe("Helper")
        assert builder._config["agent_card"] == "http://helper:8001"
        assert builder._config["timeout"] == 30


# ======================================================================
# 3. AgentRegistry
# ======================================================================


class TestAgentRegistry:
    """Tests for registry-based discovery."""

    def test_creation(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            registry = AgentRegistry("http://registry.internal:9000")
        assert registry._base_url == "http://registry.internal:9000"
        assert registry._timeout == 30

    def test_creation_strips_trailing_slash(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            registry = AgentRegistry("http://registry.internal:9000/")
        assert registry._base_url == "http://registry.internal:9000"

    def test_creation_custom_timeout(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            registry = AgentRegistry("http://registry:9000", timeout=60)
        assert registry._timeout == 60

    def test_find_by_name(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            registry = AgentRegistry("http://registry:9000")
            remote = registry.find("researcher")
        assert isinstance(remote, RemoteAgent)
        assert remote._config["name"] == "researcher"
        assert remote._config["agent_card"] == "http://registry:9000/agents/researcher"

    def test_find_by_skill(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            registry = AgentRegistry("http://registry:9000")
            remote = registry.find("researcher", skill="academic-research")
        assert "skill=academic-research" in remote._config["agent_card"]

    def test_find_by_tag(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            registry = AgentRegistry("http://registry:9000")
            remote = registry.find("coder", tag="python")
        assert "tag=python" in remote._config["agent_card"]

    def test_find_by_skill_and_tag(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            registry = AgentRegistry("http://registry:9000")
            remote = registry.find("agent", skill="research", tag="academic")
        card_url = remote._config["agent_card"]
        assert "skill=research" in card_url
        assert "tag=academic" in card_url

    def test_find_inherits_timeout(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            registry = AgentRegistry("http://registry:9000", timeout=120)
            remote = registry.find("agent")
        assert remote._config["timeout"] == 120

    def test_find_chainable(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            registry = AgentRegistry("http://registry:9000")
            remote = registry.find("agent").describe("Found agent").streaming()
        assert remote._config["description"] == "Found agent"
        assert remote._config["_streaming"] is True

    def test_repr(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            registry = AgentRegistry("http://registry:9000")
        assert "registry:9000" in repr(registry)

    def test_experimental_warning(self):
        with pytest.warns(match="experimental"):
            AgentRegistry("http://registry:9000")


# ======================================================================
# 4. A2AServer health check
# ======================================================================


class TestA2AServerHealthCheck:
    """Tests for health check endpoint configuration."""

    def test_health_check_sets_path(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            server = A2AServer(Agent("test")).health_check()
        assert server._health_path == "/health"

    def test_health_check_custom_path(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            server = A2AServer(Agent("test")).health_check("/status")
        assert server._health_path == "/status"

    def test_health_check_ready_default(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            server = A2AServer(Agent("test")).health_check()
        assert server._health_ready is True

    def test_health_check_no_ready(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            server = A2AServer(Agent("test")).health_check(include_ready=False)
        assert server._health_ready is False

    def test_health_check_returns_self(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            server = A2AServer(Agent("test"))
            result = server.health_check()
        assert result is server

    def test_health_check_chainable(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            server = (
                A2AServer(Agent("test"))
                .port(8001)
                .health_check("/healthz")
                .streaming()
            )
        assert server._port == 8001
        assert server._health_path == "/healthz"
        assert server._streaming_enabled is True


# ======================================================================
# 5. A2AServer graceful shutdown
# ======================================================================


class TestA2AServerGracefulShutdown:
    """Tests for graceful shutdown configuration."""

    def test_graceful_shutdown_default_timeout(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            server = A2AServer(Agent("test")).graceful_shutdown()
        assert server._shutdown_timeout == 30

    def test_graceful_shutdown_custom_timeout(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            server = A2AServer(Agent("test")).graceful_shutdown(timeout=60)
        assert server._shutdown_timeout == 60

    def test_graceful_shutdown_returns_self(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            server = A2AServer(Agent("test"))
            result = server.graceful_shutdown()
        assert result is server

    def test_graceful_shutdown_chainable(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            server = (
                A2AServer(Agent("test"))
                .port(8001)
                .graceful_shutdown(45)
                .health_check()
            )
        assert server._port == 8001
        assert server._shutdown_timeout == 45
        assert server._health_path == "/health"


# ======================================================================
# 6. Full fluent chain with Phase 3 features
# ======================================================================


class TestPhase3FullChain:
    """Integration tests for Phase 3 features combined."""

    def test_discover_with_state_bridging(self):
        """Discovery + Phase 2 state bridging works together."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = (
                RemoteAgent.discover("reviewer", "reviewer.agents.acme.com")
                .sends("draft")
                .receives("feedback")
                .persistent_context()
                .timeout(120)
            )
        assert "agent_card" in builder._config
        assert builder._config["_sends_keys"] == ["draft"]
        assert builder._config["_receives_keys"] == ["feedback"]
        assert builder._config["_persistent_context"] is True

    def test_env_with_state_bridging(self, monkeypatch):
        monkeypatch.setenv("REVIEWER_URL", "http://reviewer:8001")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = (
                RemoteAgent("reviewer", env="REVIEWER_URL")
                .sends("draft")
                .receives("feedback")
            )
        assert builder._config["agent_card"] == "http://reviewer:8001"
        assert builder._config["_sends_keys"] == ["draft"]

    def test_server_with_health_and_shutdown(self):
        """A2AServer with health check + graceful shutdown."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            server = (
                A2AServer(Agent("test"))
                .port(8001)
                .host("0.0.0.0")
                .version("2.0.0")
                .provider("Acme", "https://acme.com")
                .health_check("/healthz")
                .graceful_shutdown(60)
                .streaming()
                .skill("research", "Research", tags=["search"])
            )
        assert server._port == 8001
        assert server._health_path == "/healthz"
        assert server._shutdown_timeout == 60
        assert server._streaming_enabled is True
        assert len(server._skills) == 1

    def test_registry_find_with_operators(self):
        """Registry-found agents work with composition operators."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            registry = AgentRegistry("http://registry:9000")
            r1 = registry.find("researcher", skill="research")
            r2 = registry.find("coder", skill="code")
            fanout = r1 | r2
        assert fanout is not None


# ======================================================================
# 7. Updated exports
# ======================================================================


class TestPhase3Exports:
    """Tests for updated exports."""

    def test_import_from_package(self):
        from adk_fluent import AgentRegistry

        assert AgentRegistry is not None

    def test_import_from_prelude(self):
        from adk_fluent.prelude import AgentRegistry

        assert AgentRegistry is not None

    def test_in_all(self):
        import adk_fluent

        assert "AgentRegistry" in adk_fluent.__all__

    def test_in_prelude_all(self):
        import adk_fluent.prelude as prelude

        assert "AgentRegistry" in prelude.__all__
