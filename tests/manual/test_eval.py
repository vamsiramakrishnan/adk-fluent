"""Tests for E module — evaluation composition surface."""

from __future__ import annotations

import json
import os
import tempfile

import pytest

# ======================================================================
# ECriterion tests
# ======================================================================


class TestECriterion:
    def test_basic_criterion(self):
        from adk_fluent._eval import ECriterion

        c = ECriterion(metric_name="test_metric", threshold=0.9)
        assert c.metric_name == "test_metric"
        assert c.threshold == 0.9
        assert c.criterion_factory is None

    def test_criterion_is_frozen(self):
        from adk_fluent._eval import ECriterion

        c = ECriterion(metric_name="test_metric", threshold=0.9)
        with pytest.raises(AttributeError):
            c.metric_name = "other"  # type: ignore[misc]

    def test_to_adk_criterion_default(self):
        from adk_fluent._eval import ECriterion

        c = ECriterion(metric_name="test_metric", threshold=0.8)
        adk_criterion = c.to_adk_criterion()
        assert adk_criterion.threshold == 0.8

    def test_to_adk_criterion_with_factory(self):
        from google.adk.evaluation.eval_metrics import ToolTrajectoryCriterion

        from adk_fluent._eval import ECriterion

        def factory(threshold=1.0, **_kw):
            return ToolTrajectoryCriterion(threshold=threshold)

        c = ECriterion(
            metric_name="tool_trajectory_avg_score",
            threshold=0.9,
            criterion_factory=factory,
        )
        adk_criterion = c.to_adk_criterion()
        assert isinstance(adk_criterion, ToolTrajectoryCriterion)
        assert adk_criterion.threshold == 0.9

    def test_to_adk_entry(self):
        from adk_fluent._eval import ECriterion

        c = ECriterion(metric_name="response_match_score", threshold=0.8)
        name, criterion = c.to_adk_entry()
        assert name == "response_match_score"
        assert criterion.threshold == 0.8


# ======================================================================
# EComposite tests
# ======================================================================


class TestEComposite:
    def test_empty_composite(self):
        from adk_fluent._eval import EComposite

        comp = EComposite()
        assert len(comp) == 0
        assert comp.criteria == []

    def test_pipe_composition(self):
        from adk_fluent._eval import E

        comp = E.trajectory() | E.response_match()
        assert len(comp) == 2
        names = [c.metric_name for c in comp.criteria]
        assert "tool_trajectory_avg_score" in names
        assert "response_match_score" in names

    def test_triple_pipe(self):
        from adk_fluent._eval import E

        comp = E.trajectory() | E.response_match() | E.safety()
        assert len(comp) == 3

    def test_to_criteria_dict(self):
        from adk_fluent._eval import E

        comp = E.trajectory() | E.response_match(0.9)
        d = comp.to_criteria_dict()
        assert "tool_trajectory_avg_score" in d
        assert "response_match_score" in d

    def test_to_eval_config(self):
        from google.adk.evaluation.eval_config import EvalConfig

        from adk_fluent._eval import E

        comp = E.trajectory() | E.response_match()
        config = comp.to_eval_config()
        assert isinstance(config, EvalConfig)
        assert "tool_trajectory_avg_score" in config.criteria
        assert "response_match_score" in config.criteria

    def test_repr(self):
        from adk_fluent._eval import E

        comp = E.trajectory() | E.safety()
        r = repr(comp)
        assert "tool_trajectory_avg_score" in r
        assert "safety_v1" in r


# ======================================================================
# E criteria factory tests
# ======================================================================


class TestEFactories:
    def test_trajectory_default(self):
        from adk_fluent._eval import E

        comp = E.trajectory()
        assert len(comp) == 1
        c = comp.criteria[0]
        assert c.metric_name == "tool_trajectory_avg_score"
        assert c.threshold == 1.0

    def test_trajectory_custom_threshold(self):
        from adk_fluent._eval import E

        comp = E.trajectory(0.8)
        c = comp.criteria[0]
        assert c.threshold == 0.8

    def test_trajectory_match_types(self):
        from google.adk.evaluation.eval_metrics import ToolTrajectoryCriterion

        from adk_fluent._eval import E

        for match in ("exact", "in_order", "any_order"):
            comp = E.trajectory(match=match)
            criterion = comp.criteria[0].to_adk_criterion()
            assert isinstance(criterion, ToolTrajectoryCriterion)

    def test_response_match(self):
        from adk_fluent._eval import E

        comp = E.response_match()
        c = comp.criteria[0]
        assert c.metric_name == "response_match_score"
        assert c.threshold == 0.8

    def test_response_match_custom(self):
        from adk_fluent._eval import E

        comp = E.response_match(0.95)
        assert comp.criteria[0].threshold == 0.95

    def test_semantic_match(self):
        from google.adk.evaluation.eval_metrics import LlmAsAJudgeCriterion

        from adk_fluent._eval import E

        comp = E.semantic_match()
        c = comp.criteria[0]
        assert c.metric_name == "final_response_match_v2"
        criterion = c.to_adk_criterion()
        assert isinstance(criterion, LlmAsAJudgeCriterion)

    def test_semantic_match_custom_judge(self):
        from adk_fluent._eval import E

        comp = E.semantic_match(0.7, judge_model="gemini-2.5-pro")
        c = comp.criteria[0]
        assert c.threshold == 0.7
        criterion = c.to_adk_criterion()
        assert criterion.judge_model_options.judge_model == "gemini-2.5-pro"

    def test_hallucination(self):
        from google.adk.evaluation.eval_metrics import HallucinationsCriterion

        from adk_fluent._eval import E

        comp = E.hallucination()
        c = comp.criteria[0]
        assert c.metric_name == "hallucinations_v1"
        criterion = c.to_adk_criterion()
        assert isinstance(criterion, HallucinationsCriterion)
        assert criterion.evaluate_intermediate_nl_responses is False

    def test_hallucination_check_intermediate(self):
        from adk_fluent._eval import E

        comp = E.hallucination(check_intermediate=True)
        criterion = comp.criteria[0].to_adk_criterion()
        assert criterion.evaluate_intermediate_nl_responses is True

    def test_safety(self):
        from adk_fluent._eval import E

        comp = E.safety()
        c = comp.criteria[0]
        assert c.metric_name == "safety_v1"
        assert c.threshold == 1.0

    def test_rubric_single(self):
        from google.adk.evaluation.eval_metrics import RubricsBasedCriterion

        from adk_fluent._eval import E

        comp = E.rubric("Response must be concise")
        c = comp.criteria[0]
        assert c.metric_name == "rubric_based_final_response_quality_v1"
        criterion = c.to_adk_criterion()
        assert isinstance(criterion, RubricsBasedCriterion)
        assert len(criterion.rubrics) == 1

    def test_rubric_multiple(self):
        from adk_fluent._eval import E

        comp = E.rubric("Must cite sources", "Must be factual", threshold=0.7)
        criterion = comp.criteria[0].to_adk_criterion()
        assert len(criterion.rubrics) == 2
        assert comp.criteria[0].threshold == 0.7

    def test_tool_rubric(self):
        from adk_fluent._eval import E

        comp = E.tool_rubric("Must use search before answering")
        c = comp.criteria[0]
        assert c.metric_name == "rubric_based_tool_use_quality_v1"

    def test_custom_metric(self):
        from adk_fluent._eval import E

        def my_metric(invocation, expected):
            return 1.0

        comp = E.custom("keyword_check", my_metric, threshold=1.0)
        c = comp.criteria[0]
        assert c.metric_name == "keyword_check"
        assert c.threshold == 1.0


# ======================================================================
# ECase tests
# ======================================================================


class TestECase:
    def test_basic_case(self):
        from adk_fluent._eval import E

        case = E.case("What is 2+2?", expect="4")
        assert case.prompt == "What is 2+2?"
        assert case.expect == "4"
        assert case.eval_id  # auto-generated

    def test_case_with_tools(self):
        from adk_fluent._eval import E

        case = E.case(
            "Search for news",
            tools=[("google_search", {"query": "news"})],
        )
        assert case.tools is not None
        assert len(case.tools) == 1
        assert case.tools[0] == ("google_search", {"query": "news"})

    def test_case_with_rubrics(self):
        from adk_fluent._eval import E

        case = E.case(
            "Summarize this",
            rubrics=["Must be concise", "Must be factual"],
        )
        assert case.rubrics is not None
        assert len(case.rubrics) == 2

    def test_case_with_state(self):
        from adk_fluent._eval import E

        case = E.case("query", state={"key": "value"})
        assert case.state == {"key": "value"}

    def test_case_to_adk_eval_case(self):
        from google.adk.evaluation.eval_case import EvalCase

        from adk_fluent._eval import E

        case = E.case("What is 2+2?", expect="4")
        adk_case = case.to_adk_eval_case()
        assert isinstance(adk_case, EvalCase)
        assert len(adk_case.conversation) == 1
        inv = adk_case.conversation[0]
        assert inv.user_content.parts[0].text == "What is 2+2?"
        assert inv.final_response.parts[0].text == "4"

    def test_case_to_adk_with_tools(self):
        from adk_fluent._eval import E

        case = E.case(
            "Search",
            tools=[("search", {"q": "test"})],
        )
        adk_case = case.to_adk_eval_case()
        inv = adk_case.conversation[0]
        assert inv.intermediate_data is not None
        assert len(inv.intermediate_data.tool_uses) == 1
        assert inv.intermediate_data.tool_uses[0].name == "search"

    def test_case_to_adk_with_rubrics(self):
        from adk_fluent._eval import E

        case = E.case("query", rubrics=["Be concise"])
        adk_case = case.to_adk_eval_case()
        assert adk_case.rubrics is not None
        assert len(adk_case.rubrics) == 1

    def test_case_to_adk_with_state(self):
        from adk_fluent._eval import E

        case = E.case("query", state={"done": True})
        adk_case = case.to_adk_eval_case()
        assert adk_case.final_session_state == {"done": True}


# ======================================================================
# EvalSuite builder tests
# ======================================================================


class TestEvalSuite:
    def _make_agent(self):
        """Create a minimal agent builder for testing."""
        from adk_fluent import Agent

        return Agent("test_agent", "gemini-2.5-flash").instruct("You are a test agent.")

    def test_suite_creation(self):
        from adk_fluent._eval import E

        agent = self._make_agent()
        suite = E.suite(agent)
        assert repr(suite).startswith("EvalSuite(")

    def test_suite_add_cases(self):
        from adk_fluent._eval import E

        agent = self._make_agent()
        suite = E.suite(agent).case("What is 2+2?", expect="4").case("Hello", expect="Hi")
        assert len(suite._cases) == 2

    def test_suite_criteria(self):
        from adk_fluent._eval import E

        agent = self._make_agent()
        suite = E.suite(agent).case("query", expect="answer").criteria(E.trajectory() | E.response_match())
        assert len(suite._criteria) == 2

    def test_suite_threshold_override(self):
        from adk_fluent._eval import E

        agent = self._make_agent()
        suite = (
            E.suite(agent)
            .case("query", expect="answer")
            .criteria(E.response_match())
            .threshold("response_match_score", 0.95)
        )
        c = suite._criteria.criteria[0]
        assert c.threshold == 0.95

    def test_suite_threshold_adds_new(self):
        from adk_fluent._eval import E

        agent = self._make_agent()
        suite = E.suite(agent).case("query", expect="answer").criteria(E.response_match()).threshold("new_metric", 0.5)
        assert len(suite._criteria) == 2

    def test_suite_num_runs(self):
        from adk_fluent._eval import E

        agent = self._make_agent()
        suite = E.suite(agent).num_runs(5)
        assert suite._num_runs == 5

    def test_suite_name_and_description(self):
        from adk_fluent._eval import E

        agent = self._make_agent()
        suite = E.suite(agent).name("My Suite").description("Tests for my agent")
        assert suite._suite_name == "My Suite"
        assert suite._suite_description == "Tests for my agent"

    def test_suite_rubric_broadcast(self):
        from adk_fluent._eval import E

        agent = self._make_agent()
        suite = E.suite(agent).case("q1", expect="a1").case("q2", expect="a2").rubric("Must be concise")
        # Rubric should be added to both cases
        for c in suite._cases:
            assert c.rubrics == ["Must be concise"]

    def test_suite_to_eval_set(self):
        from google.adk.evaluation.eval_set import EvalSet

        from adk_fluent._eval import E

        agent = self._make_agent()
        suite = E.suite(agent).case("What is 2+2?", expect="4").case("Hello", expect="Hi")
        eval_set = suite.to_eval_set()
        assert isinstance(eval_set, EvalSet)
        assert len(eval_set.eval_cases) == 2

    def test_suite_to_eval_config(self):
        from google.adk.evaluation.eval_config import EvalConfig

        from adk_fluent._eval import E

        agent = self._make_agent()
        suite = E.suite(agent).criteria(E.trajectory() | E.safety())
        config = suite.to_eval_config()
        assert isinstance(config, EvalConfig)
        assert "tool_trajectory_avg_score" in config.criteria
        assert "safety_v1" in config.criteria

    def test_suite_to_file(self):
        from adk_fluent._eval import E

        agent = self._make_agent()
        suite = E.suite(agent).case("What is 2+2?", expect="4").case("Search", tools=[("search", {"q": "test"})])
        with tempfile.NamedTemporaryFile(suffix=".test.json", delete=False, mode="w") as f:
            path = f.name

        try:
            suite.to_file(path)
            with open(path) as f:
                data = json.load(f)
            assert "evalCases" in data or "eval_cases" in data
        finally:
            os.unlink(path)


# ======================================================================
# EvalReport tests
# ======================================================================


class TestEvalReport:
    def test_report_ok_all_passed(self):
        from adk_fluent._eval import EvalReport

        report = EvalReport(
            scores={"metric_a": 0.9, "metric_b": 0.95},
            thresholds={"metric_a": 0.8, "metric_b": 0.9},
            passed={"metric_a": True, "metric_b": True},
        )
        assert report.ok is True

    def test_report_ok_some_failed(self):
        from adk_fluent._eval import EvalReport

        report = EvalReport(
            scores={"metric_a": 0.5, "metric_b": 0.95},
            thresholds={"metric_a": 0.8, "metric_b": 0.9},
            passed={"metric_a": False, "metric_b": True},
        )
        assert report.ok is False

    def test_report_ok_empty(self):
        from adk_fluent._eval import EvalReport

        report = EvalReport()
        assert report.ok is False

    def test_report_summary(self):
        from adk_fluent._eval import EvalReport

        report = EvalReport(
            scores={"metric_a": 0.9},
            thresholds={"metric_a": 0.8},
            passed={"metric_a": True},
        )
        s = report.summary()
        assert "PASS" in s
        assert "metric_a" in s
        assert "0.900" in s

    def test_report_repr(self):
        from adk_fluent._eval import EvalReport

        report = EvalReport(
            scores={"m": 1.0},
            thresholds={"m": 0.8},
            passed={"m": True},
        )
        assert "PASSED" in repr(report)


# ======================================================================
# ComparisonReport tests
# ======================================================================


class TestComparisonReport:
    def test_winner(self):
        from adk_fluent._eval import ComparisonReport, EvalReport

        report = ComparisonReport(
            agent_reports={
                "fast": EvalReport(
                    scores={"m": 0.7},
                    thresholds={"m": 0.5},
                    passed={"m": True},
                ),
                "smart": EvalReport(
                    scores={"m": 0.95},
                    thresholds={"m": 0.5},
                    passed={"m": True},
                ),
            }
        )
        assert report.winner == "smart"

    def test_ranked(self):
        from adk_fluent._eval import ComparisonReport, EvalReport

        report = ComparisonReport(
            agent_reports={
                "a": EvalReport(scores={"m": 0.3}, thresholds={"m": 0.5}, passed={"m": False}),
                "b": EvalReport(scores={"m": 0.9}, thresholds={"m": 0.5}, passed={"m": True}),
                "c": EvalReport(scores={"m": 0.6}, thresholds={"m": 0.5}, passed={"m": True}),
            }
        )
        ranking = report.ranked()
        assert ranking[0][0] == "b"
        assert ranking[1][0] == "c"
        assert ranking[2][0] == "a"

    def test_summary(self):
        from adk_fluent._eval import ComparisonReport, EvalReport

        report = ComparisonReport(
            agent_reports={
                "fast": EvalReport(
                    scores={"m": 0.7},
                    thresholds={"m": 0.5},
                    passed={"m": True},
                ),
            }
        )
        s = report.summary()
        assert "fast" in s
        assert "Comparison Report" in s

    def test_repr(self):
        from adk_fluent._eval import ComparisonReport, EvalReport

        report = ComparisonReport(
            agent_reports={
                "a": EvalReport(scores={"m": 0.9}, thresholds={"m": 0.5}, passed={"m": True}),
            }
        )
        assert "winner" in repr(report)


# ======================================================================
# EPersona tests
# ======================================================================


class TestEPersona:
    def _has_personas(self):
        """Check if ADK version supports prebuilt personas (>= 1.26.0)."""
        try:
            from google.adk.evaluation.simulation.pre_built_personas import (  # noqa: F401
                get_default_persona_registry,
            )

            return True
        except (ImportError, ModuleNotFoundError):
            return False

    def test_expert_persona(self):
        from adk_fluent._eval import E

        if not self._has_personas():
            with pytest.raises(ImportError, match="google-adk >= 1.26.0"):
                E.persona.expert()
            return
        persona = E.persona.expert()
        assert persona.id == "EXPERT"

    def test_novice_persona(self):
        from adk_fluent._eval import E

        if not self._has_personas():
            with pytest.raises(ImportError, match="google-adk >= 1.26.0"):
                E.persona.novice()
            return
        persona = E.persona.novice()
        assert persona.id == "NOVICE"

    def test_evaluator_persona(self):
        from adk_fluent._eval import E

        if not self._has_personas():
            with pytest.raises(ImportError, match="google-adk >= 1.26.0"):
                E.persona.evaluator()
            return
        persona = E.persona.evaluator()
        assert persona.id == "EVALUATOR"

    def test_custom_persona(self):
        from adk_fluent._eval import E

        if not self._has_personas():
            with pytest.raises(ImportError, match="google-adk >= 1.26.0"):
                E.persona.custom("TESTER", "A tester")
            return
        persona = E.persona.custom(
            "TESTER",
            "A tester who tries to break things",
            behaviors=["Aggressive testing"],
        )
        assert persona.id == "TESTER"
        assert "break" in persona.description


# ======================================================================
# E.scenario tests
# ======================================================================


class TestEScenario:
    def test_basic_scenario(self):
        from google.adk.evaluation.conversation_scenarios import ConversationScenario

        from adk_fluent._eval import E

        scenario = E.scenario(
            start="Book a flight",
            plan="User wants SFO to JFK",
        )
        assert isinstance(scenario, ConversationScenario)
        assert scenario.starting_prompt == "Book a flight"
        assert scenario.conversation_plan == "User wants SFO to JFK"

    def test_scenario_with_persona(self):
        from adk_fluent._eval import E

        try:
            persona = E.persona.novice()
        except ImportError:
            pytest.skip("Prebuilt personas require google-adk >= 1.26.0")
            return
        scenario = E.scenario(
            start="Help me debug",
            plan="User has a Python error",
            persona=persona,
        )
        assert scenario.user_persona is not None
        assert scenario.user_persona.id == "NOVICE"


# ======================================================================
# E.gate tests
# ======================================================================


class TestEGate:
    def test_gate_returns_stransform(self):
        from adk_fluent._eval import E
        from adk_fluent._transforms import STransform

        gate = E.gate(E.hallucination())
        assert isinstance(gate, STransform)


# ======================================================================
# E.from_file / E.from_dir tests
# ======================================================================


class TestEFileOps:
    def test_round_trip_to_file_and_from_file(self):
        from adk_fluent import Agent
        from adk_fluent._eval import E

        agent = Agent("test", "gemini-2.5-flash").instruct("Test agent")
        suite = E.suite(agent).case("What is 2+2?", expect="4").case("Hello", expect="Hi there")
        with tempfile.NamedTemporaryFile(suffix=".test.json", delete=False, mode="w") as f:
            path = f.name

        try:
            suite.to_file(path)
            loaded = E.from_file(path)
            assert len(loaded.eval_cases) == 2
        finally:
            os.unlink(path)

    def test_from_dir(self):
        from adk_fluent import Agent
        from adk_fluent._eval import E

        agent = Agent("test", "gemini-2.5-flash").instruct("Test agent")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write two eval set files
            for i in range(2):
                suite = E.suite(agent).case(f"prompt_{i}", expect=f"answer_{i}")
                suite.to_file(os.path.join(tmpdir, f"eval_{i}.test.json"))

            eval_sets = E.from_dir(tmpdir)
            assert len(eval_sets) == 2


# ======================================================================
# Builder integration tests
# ======================================================================


class TestBuilderIntegration:
    def test_agent_eval_method(self):
        from adk_fluent import Agent
        from adk_fluent._eval import EvalSuite

        agent = Agent("test", "gemini-2.5-flash").instruct("Test")
        suite = agent.eval("What is 2+2?", expect="4")
        assert isinstance(suite, EvalSuite)
        assert len(suite._cases) == 1
        assert suite._cases[0].prompt == "What is 2+2?"
        assert suite._cases[0].expect == "4"

    def test_agent_eval_with_criteria(self):
        from adk_fluent import Agent
        from adk_fluent._eval import E

        agent = Agent("test", "gemini-2.5-flash").instruct("Test")
        suite = agent.eval("query", criteria=E.semantic_match())
        assert len(suite._criteria) == 1
        assert suite._criteria.criteria[0].metric_name == "final_response_match_v2"

    def test_agent_eval_auto_criteria(self):
        from adk_fluent import Agent

        agent = Agent("test", "gemini-2.5-flash").instruct("Test")
        suite = agent.eval("query", expect="answer")
        # Should auto-add response_match when expect is provided
        assert len(suite._criteria) == 1
        assert suite._criteria.criteria[0].metric_name == "response_match_score"

    def test_agent_eval_suite_method(self):
        from adk_fluent import Agent
        from adk_fluent._eval import EvalSuite

        agent = Agent("test", "gemini-2.5-flash").instruct("Test")
        suite = agent.eval_suite()
        assert isinstance(suite, EvalSuite)


# ======================================================================
# Import path tests
# ======================================================================


class TestImports:
    def test_import_from_top_level(self):
        from adk_fluent import E, ECase, EComposite, ECriterion, EvalReport, EvalSuite

        assert E is not None
        assert EComposite is not None
        assert ECriterion is not None
        assert ECase is not None
        assert EvalSuite is not None
        assert EvalReport is not None

    def test_import_from_prelude(self):
        from adk_fluent.prelude import E, EComposite, EvalSuite

        assert E is not None
        assert EComposite is not None
        assert EvalSuite is not None

    def test_import_from_testing(self):
        from adk_fluent.testing import E, EvalReport, EvalSuite

        assert E is not None
        assert EvalSuite is not None
        assert EvalReport is not None


# ======================================================================
# Composition integration with other namespaces
# ======================================================================


class TestNamespaceIntegration:
    def test_e_with_agent_builder(self):
        """E works with Agent builder."""
        from adk_fluent import Agent, E

        agent = Agent("qa", "gemini-2.5-flash").instruct("Answer questions")
        suite = E.suite(agent).case("What is Python?", expect="programming language").criteria(E.response_match())
        assert len(suite._cases) == 1

    def test_e_with_pipeline(self):
        """E.suite works with Pipeline builders."""
        from adk_fluent import Agent, E, Pipeline

        pipeline = (
            Pipeline("flow")
            .step(Agent("a", "gemini-2.5-flash").instruct("Step 1").writes("result"))
            .step(Agent("b", "gemini-2.5-flash").instruct("Step 2"))
        )
        suite = E.suite(pipeline).case("query", expect="answer")
        assert suite._agent is pipeline

    def test_e_gate_in_pipeline(self):
        """E.gate() composes with >> operator."""
        from adk_fluent import E
        from adk_fluent._transforms import STransform

        gate = E.gate(E.hallucination())
        assert isinstance(gate, STransform)

    def test_criteria_composition_is_immutable(self):
        """Composition creates new objects — originals unchanged."""
        from adk_fluent import E

        a = E.trajectory()
        b = E.safety()
        c = a | b
        assert len(a) == 1
        assert len(b) == 1
        assert len(c) == 2

    def test_full_criteria_chain(self):
        """Full criteria chain covering all metric types."""
        from adk_fluent import E

        criteria = (
            E.trajectory()
            | E.response_match()
            | E.semantic_match()
            | E.hallucination()
            | E.safety()
            | E.rubric("Be concise")
            | E.tool_rubric("Use search")
        )
        assert len(criteria) == 7
        names = {c.metric_name for c in criteria.criteria}
        assert names == {
            "tool_trajectory_avg_score",
            "response_match_score",
            "final_response_match_v2",
            "hallucinations_v1",
            "safety_v1",
            "rubric_based_final_response_quality_v1",
            "rubric_based_tool_use_quality_v1",
        }
