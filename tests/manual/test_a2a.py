"""Tests for A2A (Agent-to-Agent) protocol support.

Tests builder construction, chaining, operator composition, and pattern helpers.
Build/runtime tests that require google-adk[a2a] are skipped when unavailable.
"""

from __future__ import annotations

import pytest

from adk_fluent import Agent

# ---------------------------------------------------------------------------
# Imports -- builders work without google-adk[a2a]; only .build() requires it
# ---------------------------------------------------------------------------

from adk_fluent.a2a import A2AServer, RemoteAgent


# ===========================================================================
# RemoteAgent builder tests
# ===========================================================================



class TestRemoteAgentBuilder:
    """RemoteAgent fluent builder API."""

    def test_constructor_name_only(self):
        r = RemoteAgent("helper")
        assert r._config["name"] == "helper"
        assert "agent_card" not in r._config

    def test_constructor_name_and_url(self):
        r = RemoteAgent("helper", "http://remote:8001")
        assert r._config["name"] == "helper"
        assert r._config["agent_card"] == "http://remote:8001"

    def test_card_method(self):
        r = RemoteAgent("helper").card("http://remote:8001")
        assert r._config["agent_card"] == "http://remote:8001"

    def test_describe(self):
        r = RemoteAgent("helper", "http://r:8001").describe("A helper agent")
        assert r._config["description"] == "A helper agent"

    def test_timeout(self):
        r = RemoteAgent("helper", "http://r:8001").timeout(300)
        assert r._config["timeout"] == 300

    def test_full_history(self):
        r = RemoteAgent("helper", "http://r:8001").full_history(True)
        assert r._config["full_history_when_stateless"] is True

    def test_full_history_default(self):
        r = RemoteAgent("helper", "http://r:8001").full_history()
        assert r._config["full_history_when_stateless"] is True

    def test_chaining(self):
        """All methods are chainable."""
        r = RemoteAgent("helper", "http://remote:8001").describe("A helper").timeout(300).full_history(True)
        assert r._config["name"] == "helper"
        assert r._config["description"] == "A helper"
        assert r._config["timeout"] == 300
        assert r._config["full_history_when_stateless"] is True

    def test_auth_bearer(self):
        r = RemoteAgent("helper", "http://r:8001").auth(bearer="token123")
        assert r._config["_auth_config"]["bearer"] == "token123"

    def test_auth_api_key(self):
        r = RemoteAgent("helper", "http://r:8001").auth(api_key="key", header="X-Key")
        assert r._config["_auth_config"]["api_key"] == "key"
        assert r._config["_auth_config"]["api_key_header"] == "X-Key"

    def test_auth_kwargs(self):
        r = RemoteAgent("helper", "http://r:8001").auth(custom="value")
        assert r._config["_auth_config"]["custom"] == "value"


# ===========================================================================
# RemoteAgent operator tests
# ===========================================================================



class TestRemoteAgentOperators:
    """RemoteAgent works with all expression operators."""

    def test_rshift_creates_pipeline(self):
        """RemoteAgent >> Agent creates a Pipeline."""
        r = RemoteAgent("remote", "http://r:8001")
        a = Agent("local", "gemini-2.5-flash")
        p = r >> a
        assert len(p._lists.get("sub_agents", [])) == 2

    def test_agent_rshift_remote(self):
        """Agent >> RemoteAgent creates a Pipeline."""
        a = Agent("local", "gemini-2.5-flash")
        r = RemoteAgent("remote", "http://r:8001")
        p = a >> r
        assert len(p._lists.get("sub_agents", [])) == 2

    def test_or_creates_fanout(self):
        """RemoteAgent | Agent creates a FanOut."""
        r = RemoteAgent("remote", "http://r:8001")
        a = Agent("local", "gemini-2.5-flash")
        f = r | a
        assert len(f._lists.get("sub_agents", [])) == 2

    def test_floordiv_creates_fallback(self):
        """RemoteAgent // Agent creates a fallback chain."""
        r = RemoteAgent("remote", "http://r:8001")
        a = Agent("local", "gemini-2.5-flash")
        f = r // a
        # _FallbackBuilder stores children in _children
        assert hasattr(f, "_children") or hasattr(f, "_lists")

    def test_mul_creates_loop(self):
        """RemoteAgent * 3 creates a Loop."""
        r = RemoteAgent("remote", "http://r:8001")
        loop = r * 3
        assert loop._config.get("max_iterations") == 3

    def test_three_way_pipeline(self):
        """Agent >> RemoteAgent >> Agent chains correctly."""
        a = Agent("first", "gemini-2.5-flash")
        r = RemoteAgent("remote", "http://r:8001")
        b = Agent("last", "gemini-2.5-flash")
        p = a >> r >> b
        assert len(p._lists.get("sub_agents", [])) == 3

    def test_three_way_fanout(self):
        """RemoteAgent | RemoteAgent | Agent fans out correctly."""
        r1 = RemoteAgent("r1", "http://r1:8001")
        r2 = RemoteAgent("r2", "http://r2:8002")
        a = Agent("local", "gemini-2.5-flash")
        f = r1 | r2 | a
        assert len(f._lists.get("sub_agents", [])) == 3

    def test_operator_immutability(self):
        """Operators don't mutate the original RemoteAgent."""
        r = RemoteAgent("remote", "http://r:8001")
        original_config = dict(r._config)
        _ = r >> Agent("a")
        _ = r | Agent("b")
        _ = r // Agent("c")
        # r should be unchanged
        assert r._config == original_config
        assert "sub_agents" not in r._lists or len(r._lists["sub_agents"]) == 0


# ===========================================================================
# Agent integration tests
# ===========================================================================



class TestAgentIntegration:
    """Agent methods that interact with A2A."""

    def test_sub_agent_accepts_remote(self):
        """Agent.sub_agent() accepts RemoteAgent."""
        a = Agent("coordinator", "gemini-2.5-flash").sub_agent(RemoteAgent("helper", "http://r:8001"))
        assert len(a._lists["sub_agents"]) == 1

    def test_multiple_remote_sub_agents(self):
        """Multiple RemoteAgent sub-agents accumulate."""
        a = (
            Agent("coordinator", "gemini-2.5-flash")
            .sub_agent(RemoteAgent("r1", "http://r1:8001"))
            .sub_agent(RemoteAgent("r2", "http://r2:8002"))
        )
        assert len(a._lists["sub_agents"]) == 2

    def test_agent_remote_static(self):
        """Agent.remote() creates a RemoteAgent."""
        r = Agent.remote("helper", "http://r:8001")
        assert isinstance(r, RemoteAgent)
        assert r._config["name"] == "helper"
        assert r._config["agent_card"] == "http://r:8001"

    def test_agent_remote_with_kwargs(self):
        """Agent.remote() passes kwargs to builder methods."""
        r = Agent.remote("helper", "http://r:8001", timeout=300)
        assert r._config["timeout"] == 300

    def test_skill_single(self):
        """Agent.skill() stores A2A skill metadata."""
        a = Agent("helper").skill("search", "Web Search", tags=["web"])
        assert len(a._config["_a2a_skills"]) == 1
        skill = a._config["_a2a_skills"][0]
        assert skill["id"] == "search"
        assert skill["name"] == "Web Search"
        assert skill["tags"] == ["web"]

    def test_skill_accumulates(self):
        """Multiple .skill() calls accumulate."""
        a = Agent("helper").skill("search", "Web Search", tags=["web"]).skill("email", "Email Drafting", tags=["email"])
        assert len(a._config["_a2a_skills"]) == 2

    def test_skill_with_examples(self):
        a = Agent("helper").skill(
            "search",
            "Web Search",
            description="Search the web",
            examples=["Find news about AI"],
        )
        skill = a._config["_a2a_skills"][0]
        assert skill["description"] == "Search the web"
        assert skill["examples"] == ["Find news about AI"]


# ===========================================================================
# A2AServer builder tests
# ===========================================================================



class TestA2AServerBuilder:
    """A2AServer fluent builder API."""

    def test_constructor(self):
        server = A2AServer(Agent("test"))
        assert server._port == 8000
        assert server._host == "0.0.0.0"
        assert server._version == "1.0.0"

    def test_port(self):
        server = A2AServer(Agent("test")).port(8001)
        assert server._port == 8001

    def test_host(self):
        server = A2AServer(Agent("test")).host("127.0.0.1")
        assert server._host == "127.0.0.1"

    def test_version(self):
        server = A2AServer(Agent("test")).version("2.0.0")
        assert server._version == "2.0.0"

    def test_provider(self):
        server = A2AServer(Agent("test")).provider("Acme Corp", "https://acme.com")
        assert server._provider_org == "Acme Corp"
        assert server._provider_url == "https://acme.com"

    def test_streaming(self):
        server = A2AServer(Agent("test")).streaming(True)
        assert server._streaming is True

    def test_push_notifications(self):
        server = A2AServer(Agent("test")).push_notifications(True)
        assert server._push_notifications is True

    def test_docs(self):
        server = A2AServer(Agent("test")).docs("https://docs.acme.com")
        assert server._doc_url == "https://docs.acme.com"

    def test_chaining(self):
        """All methods are chainable."""
        server = (
            A2AServer(Agent("test"))
            .port(8001)
            .host("127.0.0.1")
            .version("2.0.0")
            .provider("Acme", "https://acme.com")
            .streaming(True)
            .push_notifications(True)
            .docs("https://docs.acme.com")
        )
        assert server._port == 8001
        assert server._host == "127.0.0.1"
        assert server._version == "2.0.0"
        assert server._provider_org == "Acme"
        assert server._streaming is True
        assert server._push_notifications is True

    def test_skill(self):
        server = A2AServer(Agent("test")).skill("search", "Web Search", tags=["web"], examples=["Search for AI"])
        assert len(server._skills) == 1
        assert server._skills[0]["id"] == "search"

    def test_auth_scheme(self):
        server = A2AServer(Agent("test")).auth_scheme("bearer", {"type": "http"})
        assert "bearer" in server._security_schemes

    def test_has_custom_card_config(self):
        """_has_custom_card_config detects non-default config."""
        server = A2AServer(Agent("test"))
        assert not server._has_custom_card_config()

        server = server.provider("Acme")
        assert server._has_custom_card_config()


# ===========================================================================
# Route integration tests
# ===========================================================================



class TestRouteIntegration:
    """RemoteAgent works with deterministic routing."""

    def test_route_eq_remote(self):
        """Route.eq() accepts RemoteAgent."""
        from adk_fluent import Route

        route = Route("type").eq("research", RemoteAgent("r", "http://r:8001"))
        assert len(route._rules) == 1

    def test_route_otherwise_remote(self):
        """Route.otherwise() accepts RemoteAgent."""
        from adk_fluent import Route

        route = Route("type").eq("local", Agent("a")).otherwise(RemoteAgent("r", "http://r:8001"))
        assert route._default is not None

    def test_pipeline_with_route_and_remote(self):
        """Agent >> Route with RemoteAgent composes correctly."""
        from adk_fluent import Route

        pipeline = Agent("classifier", "gemini-2.5-flash").instruct("Classify.").writes("type") >> Route("type").eq(
            "research", RemoteAgent("r", "http://r:8001")
        ).otherwise(Agent("general", "gemini-2.5-flash"))
        assert len(pipeline._lists.get("sub_agents", [])) == 2


# ===========================================================================
# A2A pattern tests
# ===========================================================================



class TestA2APatterns:
    """A2A composition patterns."""

    def test_a2a_cascade_creates_fallback(self):
        from adk_fluent.patterns import a2a_cascade

        result = a2a_cascade("http://a:8001", "http://b:8002")
        # Should be a fallback builder
        assert hasattr(result, "_children") or hasattr(result, "_lists")

    def test_a2a_cascade_requires_two(self):
        from adk_fluent.patterns import a2a_cascade

        with pytest.raises(ValueError, match="at least 2"):
            a2a_cascade("http://a:8001")

    def test_a2a_cascade_custom_names(self):
        from adk_fluent.patterns import a2a_cascade

        result = a2a_cascade(
            "http://a:8001",
            "http://b:8002",
            names=["fast", "accurate"],
        )
        assert result is not None

    def test_a2a_fanout_creates_fanout(self):
        from adk_fluent.patterns import a2a_fanout

        result = a2a_fanout("http://a:8001", "http://b:8002")
        assert len(result._lists.get("sub_agents", [])) == 2

    def test_a2a_fanout_requires_two(self):
        from adk_fluent.patterns import a2a_fanout

        with pytest.raises(ValueError, match="at least 2"):
            a2a_fanout("http://a:8001")

    def test_a2a_fanout_three_endpoints(self):
        from adk_fluent.patterns import a2a_fanout

        result = a2a_fanout("http://a:8001", "http://b:8002", "http://c:8003")
        assert len(result._lists.get("sub_agents", [])) == 3

    def test_a2a_delegate(self):
        from adk_fluent.patterns import a2a_delegate

        coord = Agent("coord", "gemini-2.5-flash")
        result = a2a_delegate(coord, research="http://r:8001", writing="http://w:8002")
        assert len(result._lists["sub_agents"]) == 2

    def test_a2a_delegate_single_remote(self):
        from adk_fluent.patterns import a2a_delegate

        coord = Agent("coord", "gemini-2.5-flash")
        result = a2a_delegate(coord, helper="http://h:8001")
        assert len(result._lists["sub_agents"]) == 1


# ===========================================================================
# Copy-on-write / immutability tests
# ===========================================================================



class TestCopyOnWrite:
    """RemoteAgent respects copy-on-write semantics."""

    def test_frozen_after_operator(self):
        """RemoteAgent is frozen after being used in an operator."""
        r = RemoteAgent("remote", "http://r:8001")
        _ = r >> Agent("a")
        assert r._frozen is True

    def test_mutation_after_freeze_forks(self):
        """Mutating a frozen RemoteAgent creates a new instance."""
        r = RemoteAgent("remote", "http://r:8001")
        _ = r >> Agent("a")  # freezes r
        r2 = r.timeout(300)
        assert r2 is not r
        assert r2._config.get("timeout") == 300
        assert "timeout" not in r._config

    def test_clone_independence(self):
        """Cloned RemoteAgent is independent of original after freeze."""
        r = RemoteAgent("remote", "http://r:8001").timeout(600)
        _ = r >> Agent("a")  # freeze r
        r2 = r.timeout(300)  # fork because frozen
        assert r._config.get("timeout") == 600
        assert r2._config.get("timeout") == 300
        assert r2 is not r


# ===========================================================================
# Hybrid composition tests
# ===========================================================================



class TestHybridComposition:
    """Mixing RemoteAgent with local agents in complex topologies."""

    def test_hybrid_pipeline_with_fallback(self):
        """Remote agent with local fallback in a pipeline."""
        remote = RemoteAgent("fast", "http://fast:8001").timeout(10)
        local = Agent("local", "gemini-2.5-flash")
        hybrid = remote // local
        assert hybrid is not None

    def test_review_loop_with_remote_reviewer(self):
        """review_loop works with RemoteAgent as reviewer."""
        from adk_fluent.patterns import review_loop

        loop = review_loop(
            worker=Agent("writer", "gemini-2.5-flash").instruct("Write.").writes("draft"),
            reviewer=RemoteAgent("expert", "http://expert:8001"),
            quality_key="quality",
            target="good",
            max_rounds=3,
        )
        assert loop._config.get("max_iterations") == 3

    def test_mixed_fanout(self):
        """FanOut with both local and remote agents."""
        f = (
            RemoteAgent("r1", "http://r1:8001")
            | Agent("local", "gemini-2.5-flash")
            | RemoteAgent("r2", "http://r2:8002")
        )
        assert len(f._lists.get("sub_agents", [])) == 3
