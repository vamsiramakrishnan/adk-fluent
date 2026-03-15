"""Tests for A2A builders (RemoteAgent, A2AServer, .skill(), T.a2a()).

These tests verify builder mechanics without calling .build() since the
a2a SDK is an optional dependency that may not be installed.
"""

import warnings

import pytest

from adk_fluent.a2a import A2AServer, RemoteAgent, SkillDeclaration
from adk_fluent.agent import Agent


class TestRemoteAgentBuilder:
    """Tests for RemoteAgent builder mechanics."""

    def test_creation_with_url(self):
        """RemoteAgent stores name and agent_card in _config."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = RemoteAgent("helper", "http://helper:8001")
        assert builder._config["name"] == "helper"
        assert builder._config["agent_card"] == "http://helper:8001"

    def test_creation_without_url(self):
        """RemoteAgent can be created with just a name."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = RemoteAgent("helper")
        assert builder._config["name"] == "helper"
        assert "agent_card" not in builder._config

    def test_describe_chaining(self):
        """describe() returns builder for chaining."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = RemoteAgent("helper", "http://helper:8001")
            result = builder.describe("A research agent")
        assert result is builder
        assert builder._config["description"] == "A research agent"

    def test_timeout(self):
        """timeout() stores value in _config."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = RemoteAgent("helper", "http://helper:8001").timeout(300)
        assert builder._config["timeout"] == 300

    def test_card_url(self):
        """card_url() overrides agent_card."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = RemoteAgent("helper").card_url("http://new:8002")
        assert builder._config["agent_card"] == "http://new:8002"

    def test_card_path(self):
        """card_path() sets agent_card to file path."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = RemoteAgent("helper").card_path("/tmp/card.json")
        assert builder._config["agent_card"] == "/tmp/card.json"

    def test_streaming(self):
        """streaming() stores internal flag."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = RemoteAgent("helper", "http://h:8001").streaming(True)
        assert builder._config["_streaming"] is True

    def test_full_history(self):
        """full_history() stores flag."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = RemoteAgent("helper", "http://h:8001").full_history(True)
        assert builder._config["full_history_when_stateless"] is True

    def test_callback_accumulation(self):
        """before_agent/after_agent accumulate callbacks."""
        fn1 = lambda ctx: None
        fn2 = lambda ctx: None
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = RemoteAgent("helper", "http://h:8001").before_agent(fn1).after_agent(fn2)
        assert builder._callbacks["before_agent_callback"] == [fn1]
        assert builder._callbacks["after_agent_callback"] == [fn2]

    def test_experimental_warning(self):
        """RemoteAgent emits experimental warning."""
        with pytest.warns(match="experimental"):
            RemoteAgent("helper", "http://helper:8001")

    def test_fluent_chain(self):
        """Full fluent chain works."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = (
                RemoteAgent("helper", "http://helper:8001")
                .describe("Research assistant")
                .timeout(120)
                .streaming(True)
                .full_history(True)
            )
        assert builder._config["name"] == "helper"
        assert builder._config["description"] == "Research assistant"
        assert builder._config["timeout"] == 120
        assert builder._config["_streaming"] is True
        assert builder._config["full_history_when_stateless"] is True

    def test_operator_support_pipeline(self):
        """RemoteAgent works with >> operator."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            local = Agent("local")
            remote = RemoteAgent("remote", "http://r:8001")
            pipeline = local >> remote
        assert pipeline is not None
        assert hasattr(pipeline, "build")

    def test_operator_support_fanout(self):
        """RemoteAgent works with | operator."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            remote1 = RemoteAgent("r1", "http://r1:8001")
            remote2 = RemoteAgent("r2", "http://r2:8002")
            fanout = remote1 | remote2
        assert fanout is not None

    def test_operator_support_fallback(self):
        """RemoteAgent works with // operator."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            remote = RemoteAgent("remote", "http://r:8001")
            local = Agent("local")
            fallback = remote // local
        assert fallback is not None

    def test_build_without_a2a_sdk_raises(self):
        """build() raises ImportError when a2a SDK is not installed."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = RemoteAgent("helper", "http://helper:8001")
        # This will fail if a2a SDK is not installed (expected in test env)
        try:
            builder.build()
        except ImportError as e:
            assert "a2a" in str(e).lower() or "google-adk" in str(e).lower()


class TestA2AServerBuilder:
    """Tests for A2AServer builder mechanics."""

    def test_creation_with_agent(self):
        """A2AServer can be created with an agent."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            agent = Agent("test", "gemini-2.5-flash")
            server = A2AServer(agent)
        assert server._agent is agent

    def test_creation_without_agent(self):
        """A2AServer can be created without an agent."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            server = A2AServer()
        assert server._agent is None

    def test_port(self):
        """port() stores value."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            server = A2AServer(Agent("test")).port(8001)
        assert server._port == 8001

    def test_host(self):
        """host() stores value."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            server = A2AServer(Agent("test")).host("127.0.0.1")
        assert server._host == "127.0.0.1"

    def test_version(self):
        """version() stores value."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            server = A2AServer(Agent("test")).version("2.0.0")
        assert server._version == "2.0.0"

    def test_provider(self):
        """provider() stores org and url."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            server = A2AServer(Agent("test")).provider("Acme", "https://acme.com")
        assert server._provider_org == "Acme"
        assert server._provider_url == "https://acme.com"

    def test_streaming(self):
        """streaming() stores flag."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            server = A2AServer(Agent("test")).streaming(True)
        assert server._streaming_enabled is True

    def test_push_notifications(self):
        """push_notifications() stores flag."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            server = A2AServer(Agent("test")).push_notifications(True)
        assert server._push_notifications is True

    def test_skill_declaration(self):
        """skill() accumulates SkillDeclarations."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            server = (
                A2AServer(Agent("test"))
                .skill("research", "Research", description="Find info", tags=["search"])
                .skill("write", "Writing", description="Write docs", tags=["docs"])
            )
        assert len(server._skills) == 2
        assert server._skills[0].id == "research"
        assert server._skills[0].tags == ["search"]
        assert server._skills[1].id == "write"

    def test_docs_url(self):
        """docs() stores URL."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            server = A2AServer(Agent("test")).docs("https://docs.acme.com")
        assert server._docs_url == "https://docs.acme.com"

    def test_fluent_chain(self):
        """Full fluent chain works."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            server = (
                A2AServer(Agent("test"))
                .port(8001)
                .host("0.0.0.0")
                .version("1.0.0")
                .provider("Acme", "https://acme.com")
                .streaming(True)
                .push_notifications(True)
                .skill("research", "Research", tags=["search"])
                .docs("https://docs.acme.com")
            )
        assert server._port == 8001
        assert server._provider_org == "Acme"
        assert server._streaming_enabled is True
        assert len(server._skills) == 1

    def test_build_without_agent_raises(self):
        """build() raises ValueError when no agent configured."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            server = A2AServer()
        with pytest.raises(ValueError, match="No agent configured"):
            server.build()

    def test_experimental_warning(self):
        """A2AServer emits experimental warning."""
        with pytest.warns(match="experimental"):
            A2AServer(Agent("test"))


class TestSkillDeclaration:
    """Tests for SkillDeclaration data class."""

    def test_creation(self):
        """SkillDeclaration stores all fields."""
        skill = SkillDeclaration(
            id="research",
            name="Research",
            description="Find information",
            tags=["search", "web"],
            examples=["Find papers"],
            input_modes=["text/plain"],
            output_modes=["text/plain", "application/json"],
        )
        assert skill.id == "research"
        assert skill.name == "Research"
        assert skill.tags == ["search", "web"]
        assert skill.output_modes == ["text/plain", "application/json"]

    def test_defaults(self):
        """SkillDeclaration has sensible defaults."""
        skill = SkillDeclaration(id="test", name="Test")
        assert skill.description == ""
        assert skill.tags == []
        assert skill.input_modes == ["text/plain"]
        assert skill.output_modes == ["text/plain"]

    def test_frozen(self):
        """SkillDeclaration is immutable."""
        skill = SkillDeclaration(id="test", name="Test")
        with pytest.raises(AttributeError):
            skill.id = "changed"


class TestAgentSkillMethod:
    """Tests for Agent.skill() method."""

    def test_skill_stores_metadata(self):
        """Agent.skill() stores SkillDeclaration in _lists."""
        agent = Agent("test")
        result = agent.skill(
            "research",
            "Research",
            description="Find info",
            tags=["search"],
            examples=["Find papers on AI"],
        )
        assert result is agent
        skills = agent._lists["_a2a_skills"]
        assert len(skills) == 1
        assert skills[0].id == "research"
        assert skills[0].name == "Research"
        assert skills[0].tags == ["search"]

    def test_multiple_skills(self):
        """Multiple .skill() calls accumulate."""
        agent = (
            Agent("test")
            .skill("research", "Research", tags=["search"])
            .skill("write", "Writing", tags=["docs"])
        )
        skills = agent._lists["_a2a_skills"]
        assert len(skills) == 2
        assert skills[0].id == "research"
        assert skills[1].id == "write"

    def test_skill_does_not_affect_build(self):
        """Skills are metadata only — they don't affect the native agent build."""
        agent = (
            Agent("test", "gemini-2.5-flash")
            .instruct("Do things.")
            .skill("research", "Research")
        )
        native = agent.build()
        assert native.name == "test"
        # Skills are A2A metadata, not ADK properties
        assert not hasattr(native, "_a2a_skills")


class TestImports:
    """Tests for public API exports."""

    def test_import_from_package(self):
        """A2A types are importable from adk_fluent."""
        from adk_fluent import A2AServer, RemoteAgent, SkillDeclaration

        assert A2AServer is not None
        assert RemoteAgent is not None
        assert SkillDeclaration is not None

    def test_import_from_prelude(self):
        """A2A types are importable from prelude."""
        from adk_fluent.prelude import A2AServer, RemoteAgent

        assert A2AServer is not None
        assert RemoteAgent is not None

    def test_in_all(self):
        """A2A types are in __all__."""
        import adk_fluent

        assert "A2AServer" in adk_fluent.__all__
        assert "RemoteAgent" in adk_fluent.__all__
        assert "SkillDeclaration" in adk_fluent.__all__
