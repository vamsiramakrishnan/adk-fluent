"""Tests for data flow contracts — cross-channel coherence analysis.

Tests the new features:
- Pass 17: topology-aware output_key inference in contract checker
- infer_data_flow(): topology-aware suggestions
- DataFlowContract: three-channel coherence view
- C.pipeline_aware(): topology-aware context mode
- Pipeline.wired(): automatic data flow wiring
- Pipeline.auto_wire(): explicit auto-wiring
"""

from pydantic import BaseModel

from adk_fluent import Agent, Pipeline
from adk_fluent._context import C, CPipelineAware
from adk_fluent._routing import Route
from adk_fluent.testing import DataFlowSuggestion, check_contracts, infer_data_flow

# ======================================================================
# Schemas for testing
# ======================================================================


class Intent(BaseModel):
    category: str
    confidence: float


class Resolution(BaseModel):
    ticket_id: str
    status: str


# ======================================================================
# Pass 17: Cross-channel coherence analysis
# ======================================================================


class TestPass17CrossChannelCoherence:
    """Test the new Pass 17 contract checks."""

    def test_missing_writes_with_template_successor(self):
        """Agent without .writes() before a successor using template vars."""
        pipeline = Agent("classifier").model("m").instruct("Classify.") >> Agent("handler").model("m").instruct(
            "Handle {intent}"
        )
        issues = check_contracts(pipeline.to_ir())
        warnings = [i for i in issues if isinstance(i, dict) and i.get("level") == "warning"]
        assert any("classifier" in str(i) and "writes" in str(i).lower() for i in warnings)

    def test_missing_writes_with_route_successor(self):
        """Agent without .writes() before a Route that reads state."""
        pipeline = Agent("classifier").model("m").instruct("Classify.") >> Route("intent").eq(
            "booking", Agent("booker").model("m").instruct("Book.")
        )
        issues = check_contracts(pipeline.to_ir())
        warnings = [i for i in issues if isinstance(i, dict) and i.get("level") == "warning"]
        assert any("classifier" in str(i) and "intent" in str(i) for i in warnings)

    def test_no_warning_when_writes_present(self):
        """No warning when predecessor has .writes() matching successor's needs."""
        pipeline = Agent("classifier").model("m").instruct("Classify.").writes("intent") >> Agent("handler").model(
            "m"
        ).instruct("Handle {intent}")
        issues = check_contracts(pipeline.to_ir())
        warnings = [i for i in issues if isinstance(i, dict) and i.get("level") == "warning"]
        # Should not have the "missing writes" warning for classifier
        missing_writes_warnings = [
            w for w in warnings if "classifier" in str(w) and "no .writes()" in str(w).get("message", "")
        ]
        assert len(missing_writes_warnings) == 0

    def test_no_warning_when_key_produced_upstream(self):
        """No warning when the needed key is produced by an earlier agent."""
        pipeline = (
            Agent("setup").model("m").instruct("Setup.").writes("intent")
            >> Agent("classifier").model("m").instruct("Classify.")
            >> Agent("handler").model("m").instruct("Handle {intent}")
        )
        issues = check_contracts(pipeline.to_ir())
        warnings = [i for i in issues if isinstance(i, dict) and i.get("level") == "warning"]
        # classifier should not get "missing writes" warning since setup already produces intent
        missing_for_classifier = [
            w
            for w in warnings
            if isinstance(w, dict) and w.get("agent") == "classifier" and "no .writes()" in w.get("message", "")
        ]
        assert len(missing_for_classifier) == 0

    def test_unused_writes_detected(self):
        """Detect when output_key is set but successor doesn't read it."""
        pipeline = Agent("a").model("m").instruct("Do.").writes("result") >> Agent("b").model("m").instruct(
            "Something else entirely."
        )
        issues = check_contracts(pipeline.to_ir())
        info = [i for i in issues if isinstance(i, dict) and i.get("level") == "info"]
        assert any("result" in str(i) and "doesn't read" in i.get("message", "") for i in info)


# ======================================================================
# infer_data_flow()
# ======================================================================


class TestInferDataFlow:
    """Test topology-aware data flow inference."""

    def test_infer_missing_writes_for_route(self):
        """Infer that classifier needs .writes('intent') before Route('intent')."""
        pipeline = Agent("classifier").model("m").instruct("Classify.") >> Route("intent").eq(
            "booking", Agent("booker").model("m").instruct("Book.")
        )
        suggestions = infer_data_flow(pipeline.to_ir())
        assert len(suggestions) >= 1
        add_writes = [s for s in suggestions if s.action == "add_writes"]
        assert len(add_writes) >= 1
        assert add_writes[0].agent == "classifier"
        assert add_writes[0].key == "intent"

    def test_infer_missing_writes_for_template(self):
        """Infer that agent needs .writes() when successor uses template vars."""
        pipeline = Agent("researcher").model("m").instruct("Research.") >> Agent("writer").model("m").instruct(
            "Write about {findings}"
        )
        suggestions = infer_data_flow(pipeline.to_ir())
        add_writes = [s for s in suggestions if s.action == "add_writes"]
        assert len(add_writes) >= 1
        assert add_writes[0].agent == "researcher"

    def test_infer_unused_writes(self):
        """Detect when a .writes() has no downstream consumer."""
        pipeline = Agent("a").model("m").instruct("Do.").writes("unused_key") >> Agent("b").model("m").instruct(
            "Something."
        )
        suggestions = infer_data_flow(pipeline.to_ir())
        remove_writes = [s for s in suggestions if s.action == "remove_writes"]
        assert len(remove_writes) >= 1
        assert remove_writes[0].key == "unused_key"

    def test_infer_context_duplication(self):
        """Detect channel duplication when output_key + default history."""
        pipeline = Agent("a").model("m").instruct("Do.").writes("result") >> Agent("b").model("m").instruct(
            "Use {result}."
        )
        suggestions = infer_data_flow(pipeline.to_ir())
        context_suggestions = [s for s in suggestions if s.action == "set_context"]
        assert len(context_suggestions) >= 1

    def test_no_suggestions_for_well_wired_pipeline(self):
        """No suggestions when pipeline is properly wired."""
        pipeline = Agent("a").model("m").instruct("Do.").writes("result") >> Agent("b").model("m").reads(
            "result"
        ).instruct("Use it.")
        suggestions = infer_data_flow(pipeline.to_ir())
        # Should have no add_writes or remove_writes (result is consumed via reads)
        critical = [s for s in suggestions if s.action in ("add_writes",)]
        assert len(critical) == 0

    def test_returns_empty_for_non_sequence(self):
        """Returns empty list for non-SequenceNode."""
        agent = Agent("solo").model("m").instruct("Hello.")
        suggestions = infer_data_flow(agent.to_ir())
        assert suggestions == []

    def test_suggestion_dataclass_fields(self):
        """DataFlowSuggestion has all expected fields."""
        s = DataFlowSuggestion(
            agent="test",
            action="add_writes",
            key="result",
            reason="needed",
            successor="next",
            channel="state",
        )
        assert s.agent == "test"
        assert s.action == "add_writes"
        assert s.key == "result"
        assert s.reason == "needed"
        assert s.successor == "next"
        assert s.channel == "state"


# ======================================================================
# DataFlowContract (three-channel view)
# ======================================================================


class TestDataFlowContract:
    """Test cross-channel coherence analysis."""

    def test_basic_pipeline_contracts(self):
        """Analyze a basic pipeline's three-channel coherence."""
        from adk_fluent._interop import check_data_flow_contract

        pipeline = Agent("a").model("m").instruct("Classify.").writes("intent") >> Agent("b").model("m").instruct(
            "Handle {intent}"
        )
        contracts = check_data_flow_contract(pipeline.to_ir())
        assert len(contracts) == 2

        # Agent a: writes to state
        assert contracts[0].agent == "a"
        assert contracts[0].state_writes == "intent"

        # Agent b: reads via template
        assert contracts[1].agent == "b"
        assert "intent" in contracts[1].instruction_vars

    def test_channel_issues_detected(self):
        """Detect cross-channel issues in a pipeline."""
        from adk_fluent._interop import check_data_flow_contract

        pipeline = Agent("a").model("m").instruct("Do.") >> Agent("b").model("m").instruct("Use {missing_key}")
        contracts = check_data_flow_contract(pipeline.to_ir())
        b_contract = [c for c in contracts if c.agent == "b"][0]
        assert len(b_contract.channel_issues) >= 1
        assert any("missing_key" in issue for issue in b_contract.channel_issues)

    def test_str_representation(self):
        """DataFlowContract has readable __str__."""
        from adk_fluent._interop import check_data_flow_contract

        pipeline = Agent("a").model("m").instruct("Do.").writes("result") >> Agent("b").model("m").instruct(
            "Use {result}"
        )
        contracts = check_data_flow_contract(pipeline.to_ir())
        text = str(contracts[0])
        assert "DataFlowContract" in text
        assert "result" in text

    def test_returns_empty_for_non_sequence(self):
        """Returns empty list for non-SequenceNode."""
        from adk_fluent._interop import check_data_flow_contract

        agent = Agent("solo").model("m").instruct("Hello.")
        contracts = check_data_flow_contract(agent.to_ir())
        assert contracts == []

    def test_builder_method(self):
        """data_flow_contract() method on builder works."""
        pipeline = Agent("a").model("m").instruct("Do.").writes("result") >> Agent("b").model("m").instruct(
            "Use {result}"
        )
        contracts = pipeline.data_flow_contract()
        assert len(contracts) >= 1

    def test_builder_infer_data_flow_method(self):
        """infer_data_flow() method on builder works."""
        pipeline = Agent("a").model("m").instruct("Do.") >> Agent("b").model("m").instruct("Use {result}")
        suggestions = pipeline.infer_data_flow()
        assert len(suggestions) >= 1


# ======================================================================
# C.pipeline_aware()
# ======================================================================


class TestCPipelineAware:
    """Test the topology-aware context mode."""

    def test_creates_pipeline_aware_spec(self):
        """C.pipeline_aware() creates a CPipelineAware instance."""
        spec = C.pipeline_aware("intent", "entities")
        assert isinstance(spec, CPipelineAware)
        assert spec.keys == ("intent", "entities")
        assert spec.include_contents == "none"
        assert spec._kind == "pipeline_aware"

    def test_pipeline_aware_no_keys(self):
        """C.pipeline_aware() with no keys still works (user only)."""
        spec = C.pipeline_aware()
        assert isinstance(spec, CPipelineAware)
        assert spec.keys == ()
        assert spec.include_contents == "none"

    def test_pipeline_aware_reads_keys(self):
        """CPipelineAware reports its reads keys."""
        spec = C.pipeline_aware("intent", "entities")
        assert spec._reads_keys == frozenset({"intent", "entities"})

    def test_pipeline_aware_on_agent(self):
        """C.pipeline_aware() works with .context()."""
        agent = Agent("handler").context(C.pipeline_aware("intent"))
        config = agent._config
        assert config.get("_context_spec") is not None
        spec = config["_context_spec"]
        assert spec._kind == "pipeline_aware"

    def test_pipeline_aware_builds(self):
        """Agent with C.pipeline_aware() builds successfully."""
        agent = Agent("handler", "gemini-2.5-flash").instruct("Handle the intent.").context(C.pipeline_aware("intent"))
        result = agent.build()
        assert result is not None
        # include_contents should be "none" since pipeline_aware suppresses history
        assert result.include_contents == "none"

    def test_contract_checker_recognizes_pipeline_aware(self):
        """Contract checker properly handles C.pipeline_aware()."""
        from adk_fluent.testing.contracts import _context_description

        spec = C.pipeline_aware("intent", "entities")
        desc = _context_description(spec)
        assert "pipeline_aware" in desc
        assert "intent" in desc


# ======================================================================
# Pipeline.wired() and auto_wire()
# ======================================================================


class TestPipelineAutoWire:
    """Test automatic data flow wiring."""

    def test_auto_wire_adds_missing_writes(self):
        """auto_wire() adds .writes() where downstream needs it."""
        classifier = Agent("classifier").model("m").instruct("Classify intent.")
        handler = Agent("handler").model("m").instruct("Handle {intent}")
        pipeline = classifier >> handler
        pipeline.auto_wire()

        # Check that classifier now has output_key
        sub_agents = pipeline._lists.get("sub_agents", [])
        classifier_builder = sub_agents[0]
        assert classifier_builder._config.get("output_key") == "intent"

    def test_auto_wire_for_route(self):
        """auto_wire() adds .writes() when Route needs a key."""
        classifier = Agent("classifier").model("m").instruct("Classify.")
        route = Route("intent").eq("booking", Agent("booker").model("m").instruct("Book."))
        pipeline = classifier >> route
        pipeline.auto_wire()

        sub_agents = pipeline._lists.get("sub_agents", [])
        classifier_builder = sub_agents[0]
        assert classifier_builder._config.get("output_key") == "intent"

    def test_auto_wire_preserves_existing_writes(self):
        """auto_wire() doesn't override existing .writes()."""
        classifier = Agent("classifier").model("m").instruct("Classify.").writes("my_intent")
        handler = Agent("handler").model("m").instruct("Handle {intent}")
        pipeline = classifier >> handler
        pipeline.auto_wire()

        sub_agents = pipeline._lists.get("sub_agents", [])
        classifier_builder = sub_agents[0]
        # Should keep existing "my_intent", not override with "intent"
        assert classifier_builder._config.get("output_key") == "my_intent"

    def test_wired_flag_on_pipeline(self):
        """Pipeline.wired() sets the auto-wire flag."""
        pipeline = (
            Pipeline("test")
            .step(Agent("a").model("m").instruct("Do."))
            .step(Agent("b").model("m").instruct("Use {result}"))
            .wired()
        )
        assert pipeline._config.get("_auto_wire") is True

    def test_auto_wire_no_effect_when_well_wired(self):
        """auto_wire() does nothing when pipeline is already well wired."""
        pipeline = Agent("a").model("m").instruct("Do.").writes("result") >> Agent("b").model("m").instruct(
            "Use {result}"
        )
        # Save original state
        sub_agents = pipeline._lists.get("sub_agents", [])
        original_key = sub_agents[0]._config.get("output_key")
        assert original_key == "result"

        pipeline.auto_wire()
        assert sub_agents[0]._config.get("output_key") == "result"

    def test_auto_wire_returns_self(self):
        """auto_wire() returns self for chaining."""
        pipeline = Agent("a").model("m") >> Agent("b").model("m")
        result = pipeline.auto_wire()
        assert result is pipeline


# ======================================================================
# Integration tests
# ======================================================================


class TestDataFlowIntegration:
    """End-to-end tests combining multiple features."""

    def test_full_pipeline_with_route(self):
        """Full pipeline: classify → route → handle, with auto-wiring."""
        classifier = Agent("classifier", "gemini-2.5-flash").instruct("Classify the user's intent.")
        booker = Agent("booker", "gemini-2.5-flash").instruct("Book a flight for the user.")
        faq = Agent("faq", "gemini-2.5-flash").instruct("Answer the FAQ.")

        pipeline = classifier >> Route("intent").eq("booking", booker).eq("faq", faq).otherwise(
            Agent("general", "gemini-2.5-flash").instruct("General help.")
        )

        # Before auto_wire: contract checker should warn about missing writes
        issues = check_contracts(pipeline.to_ir())
        has_route_warning = any(
            isinstance(i, dict) and i.get("level") in ("error", "warning") and "intent" in str(i) for i in issues
        )
        assert has_route_warning

        # After auto_wire: classifier gets .writes("intent")
        pipeline.auto_wire()
        sub_agents = pipeline._lists.get("sub_agents", [])
        assert sub_agents[0]._config.get("output_key") == "intent"

    def test_pipeline_with_reads_and_writes(self):
        """Pipeline using .reads() and .writes() for structured data flow."""
        pipeline = (
            Agent("researcher", "gemini-2.5-flash").instruct("Research the topic.").writes("findings")
            >> Agent("writer", "gemini-2.5-flash").instruct("Write a report.").reads("findings").writes("draft")
            >> Agent("reviewer", "gemini-2.5-flash").instruct("Review the draft.").reads("draft")
        )

        # Should have no critical issues
        issues = check_contracts(pipeline.to_ir())
        errors = [i for i in issues if isinstance(i, dict) and i.get("level") == "error"]
        assert len(errors) == 0

    def test_pipeline_aware_context_in_pipeline(self):
        """C.pipeline_aware() in a real pipeline."""
        pipeline = Agent("classifier", "gemini-2.5-flash").instruct("Classify.").writes("intent") >> Agent(
            "handler", "gemini-2.5-flash"
        ).instruct("Handle the request.").context(C.pipeline_aware("intent"))

        issues = check_contracts(pipeline.to_ir())
        errors = [i for i in issues if isinstance(i, dict) and i.get("level") == "error"]
        assert len(errors) == 0

    def test_data_flow_contract_and_infer_complement(self):
        """data_flow_contract() and infer_data_flow() give complementary views."""
        pipeline = Agent("a", "gemini-2.5-flash").instruct("Do.") >> Agent("b", "gemini-2.5-flash").instruct(
            "Use {result}"
        )

        # Contract view shows the issues
        contracts = pipeline.data_flow_contract()
        assert len(contracts) >= 1
        b_contract = [c for c in contracts if c.agent == "b"]
        assert len(b_contract) == 1
        assert any("result" in issue for issue in b_contract[0].channel_issues)

        # Inference view suggests fixes
        suggestions = pipeline.infer_data_flow()
        add_writes = [s for s in suggestions if s.action == "add_writes"]
        assert len(add_writes) >= 1
