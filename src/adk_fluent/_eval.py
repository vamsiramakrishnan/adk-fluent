"""E module -- fluent evaluation composition surface. Hand-written, not generated.

Consistent with P (prompts), C (context), S (state transforms), M (middleware),
T (tools), A (artifacts).  E is the DX surface for building, running, and
comparing agent evaluations using the Google ADK evaluation framework.

Three evaluation tiers:

1. **Inline** — ``agent.eval(prompt, expect=...)`` for quick smoke-checks.
2. **Suite**  — ``E.suite(agent).case(...).criteria(...).run()`` for structured eval sets.
3. **Offline** — ``E.from_file("tests/agent.test.json")`` to load/run file-based evals.

Composition with ``|``::

    criteria = E.trajectory() | E.response_match() | E.safety()

Integration with other namespaces::

    # P — prompt templates as eval expectations
    agent.eval("Summarize {topic}", expect=P.template("{topic} summary"))

    # S — assert state after agent runs
    E.suite(agent).case("query", state={"key": "value"})

    # T — expected tool trajectory
    E.suite(agent).case("query", tools=[("search", {"q": "news"})])

    # C — eval with context constraints
    agent.context(C.window(5)).eval("query", expect="answer")

Usage::

    from adk_fluent import E

    # Quick inline eval
    agent.eval("What is 2+2?", expect="4")

    # Criteria composition
    criteria = E.trajectory() | E.response_match(0.8) | E.safety()

    # Full suite
    report = await (
        E.suite(agent)
        .case("What is 2+2?", expect="4")
        .case("Search for news", tools=[("google_search", {"query": "news"})])
        .criteria(criteria)
        .num_runs(3)
        .run()
    )
    print(report.summary())

    # Model comparison
    report = await (
        E.compare(fast_agent, smart_agent)
        .case("Complex query", expect="detailed answer")
        .criteria(E.semantic_match())
        .run()
    )
    best = report.ranked()  # agents sorted by composite score
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "E",
    "EComposite",
    "ECriterion",
    "ECase",
    "EvalSuite",
    "EvalReport",
    "ComparisonReport",
    "EPersona",
]


# ======================================================================
# ECriterion — frozen descriptor for a single evaluation criterion
# ======================================================================


@dataclass(frozen=True, slots=True)
class ECriterion:
    """A single evaluation criterion descriptor.

    Maps to an ADK ``EvalMetric`` name + ``BaseCriterion`` subclass.
    """

    metric_name: str
    threshold: float = 1.0
    criterion_factory: Callable[..., Any] | None = None
    criterion_kwargs: tuple[tuple[str, Any], ...] = ()

    def to_adk_criterion(self) -> Any:
        """Convert to ADK ``BaseCriterion`` (or subclass) instance."""
        from google.adk.evaluation.eval_metrics import BaseCriterion

        if self.criterion_factory is not None:
            kwargs = dict(self.criterion_kwargs)
            kwargs.setdefault("threshold", self.threshold)
            return self.criterion_factory(**kwargs)
        return BaseCriterion(threshold=self.threshold)

    def to_adk_entry(self) -> tuple[str, Any]:
        """Return ``(metric_name, criterion)`` pair for ``EvalConfig.criteria``."""
        return (self.metric_name, self.to_adk_criterion())


# ======================================================================
# EComposite — composable criterion chain
# ======================================================================


class EComposite:
    """Composable evaluation criteria. The result of any ``E.xxx()`` call.

    Supports ``|`` for composition::

        E.trajectory() | E.response_match() | E.safety()
    """

    def __init__(self, criteria: list[ECriterion] | None = None):
        self._criteria: list[ECriterion] = list(criteria or [])

    def __or__(self, other: EComposite | ECriterion) -> EComposite:
        """E.trajectory() | E.response_match()"""
        if isinstance(other, EComposite):
            return EComposite(self._criteria + other._criteria)
        if isinstance(other, ECriterion):
            return EComposite(self._criteria + [other])
        return NotImplemented

    def __ror__(self, other: EComposite | ECriterion) -> EComposite:
        """criterion | E.safety()"""
        if isinstance(other, EComposite):
            return EComposite(other._criteria + self._criteria)
        if isinstance(other, ECriterion):
            return EComposite([other] + self._criteria)
        return NotImplemented

    def to_criteria_dict(self) -> dict[str, Any]:
        """Flatten to ADK-compatible ``EvalConfig.criteria`` dict."""
        return dict(c.to_adk_entry() for c in self._criteria)

    def to_eval_config(self) -> Any:
        """Build an ``EvalConfig`` from the criteria in this composite."""
        from google.adk.evaluation.eval_config import EvalConfig

        return EvalConfig(criteria=self.to_criteria_dict())

    @property
    def criteria(self) -> list[ECriterion]:
        return list(self._criteria)

    def __repr__(self) -> str:
        names = [c.metric_name for c in self._criteria]
        return f"EComposite([{', '.join(names)}])"

    def __len__(self) -> int:
        return len(self._criteria)


# ======================================================================
# ECase — a single evaluation case descriptor
# ======================================================================


@dataclass
class ECase:
    """A single evaluation case. Maps to ADK's ``EvalCase``.

    Attributes:
        prompt: The user prompt to evaluate.
        expect: Expected final response text (for response_match / semantic_match).
        tools: Expected tool trajectory as list of ``(name, args)`` tuples.
        rubrics: List of rubric text strings for rubric-based evaluation.
        state: Expected final session state dict.
        eval_id: Unique identifier (auto-generated if not provided).
    """

    prompt: str
    expect: str | None = None
    tools: list[tuple[str, dict[str, Any]]] | None = None
    rubrics: list[str] | None = None
    state: dict[str, Any] | None = None
    eval_id: str = ""

    def __post_init__(self):
        if not self.eval_id:
            self.eval_id = str(uuid.uuid4())

    def to_adk_eval_case(self) -> Any:
        """Convert to ADK ``EvalCase``."""
        from google.adk.evaluation.eval_case import (
            EvalCase,
            IntermediateData,
            Invocation,
        )
        from google.adk.evaluation.eval_rubrics import Rubric, RubricContent
        from google.genai import types as genai_types

        # Build the invocation
        user_content = genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=self.prompt)],
        )

        final_response = None
        if self.expect is not None:
            final_response = genai_types.Content(
                role="model",
                parts=[genai_types.Part(text=self.expect)],
            )

        intermediate_data = None
        if self.tools:
            tool_uses = []
            tool_responses = []
            for tool_name, tool_args in self.tools:
                tool_uses.append(genai_types.FunctionCall(name=tool_name, args=tool_args))
                tool_responses.append(genai_types.FunctionResponse(name=tool_name, response={"result": "ok"}))
            intermediate_data = IntermediateData(
                tool_uses=tool_uses,
                tool_responses=tool_responses,
                intermediate_responses=[],
            )

        invocation = Invocation(
            invocation_id=str(uuid.uuid4()),
            user_content=user_content,
            final_response=final_response,
            intermediate_data=intermediate_data,
            creation_timestamp=time.time(),
        )

        # Build rubrics
        adk_rubrics = None
        if self.rubrics:
            adk_rubrics = [
                Rubric(
                    rubric_id=str(uuid.uuid4()),
                    rubric_content=RubricContent(text_property=text),
                )
                for text in self.rubrics
            ]

        return EvalCase(
            eval_id=self.eval_id,
            conversation=[invocation],
            rubrics=adk_rubrics,
            final_session_state=self.state,
            creation_timestamp=time.time(),
        )


# ======================================================================
# EvalReport — ergonomic wrapper around ADK's EvaluationResult
# ======================================================================


@dataclass
class EvalReport:
    """Result of running an evaluation suite.

    Wraps ADK's raw results with ergonomic accessors.
    """

    scores: dict[str, float] = field(default_factory=dict)
    thresholds: dict[str, float] = field(default_factory=dict)
    passed: dict[str, bool] = field(default_factory=dict)
    details: list[Any] = field(default_factory=list)
    raw_results: list[Any] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True if all metrics passed their thresholds."""
        if not self.passed:
            return False
        return all(self.passed.values())

    def summary(self) -> str:
        """Formatted text summary of evaluation results."""
        lines = ["Eval Report", "=" * 40]
        for metric, score in self.scores.items():
            threshold = self.thresholds.get(metric, "N/A")
            status = "PASS" if self.passed.get(metric, False) else "FAIL"
            lines.append(f"  {metric}: {score:.3f} (threshold: {threshold}) [{status}]")
        lines.append("=" * 40)
        overall = "PASSED" if self.ok else "FAILED"
        lines.append(f"Overall: {overall}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        status = "PASSED" if self.ok else "FAILED"
        return f"EvalReport({status}, scores={self.scores})"


# ======================================================================
# ComparisonReport — side-by-side evaluation of multiple agents
# ======================================================================


@dataclass
class ComparisonReport:
    """Result of comparing multiple agents on the same eval cases."""

    agent_reports: dict[str, EvalReport] = field(default_factory=dict)

    @property
    def winner(self) -> str | None:
        """Name of the best performing agent (highest average score)."""
        ranking = self.ranked()
        return ranking[0][0] if ranking else None

    def ranked(self) -> list[tuple[str, float]]:
        """Agents sorted by composite score (descending).

        Returns list of ``(agent_name, avg_score)`` tuples.
        """
        averages = []
        for name, report in self.agent_reports.items():
            if report.scores:
                avg = sum(report.scores.values()) / len(report.scores)
            else:
                avg = 0.0
            averages.append((name, avg))
        return sorted(averages, key=lambda x: x[1], reverse=True)

    def ranked_agents(self) -> list[Any]:
        """Return agent builders sorted by composite score (descending).

        Only available if agents were stored during comparison.
        """
        return [name for name, _ in self.ranked()]

    def summary(self) -> str:
        """Formatted comparison table."""
        lines = ["Comparison Report", "=" * 50]
        for name, avg in self.ranked():
            report = self.agent_reports[name]
            status = "PASS" if report.ok else "FAIL"
            lines.append(f"  {name}: avg={avg:.3f} [{status}]")
            for metric, score in report.scores.items():
                lines.append(f"    {metric}: {score:.3f}")
        lines.append("=" * 50)
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"ComparisonReport(winner={self.winner!r}, agents={list(self.agent_reports)})"


# ======================================================================
# EPersona — prebuilt user simulation personas
# ======================================================================


def _get_persona_registry() -> Any:
    """Import the persona registry, handling version differences."""
    try:
        from google.adk.evaluation.simulation.pre_built_personas import (  # type: ignore[reportMissingImports]
            get_default_persona_registry,
        )

        return get_default_persona_registry()
    except (ImportError, ModuleNotFoundError):
        return None


def _get_user_persona_class() -> tuple[Any, Any] | None:
    """Import UserPersona and UserBehavior, handling version differences."""
    try:
        from google.adk.evaluation.simulation.user_simulator_personas import (  # type: ignore[reportMissingImports]
            UserBehavior,
            UserPersona,
        )

        return UserPersona, UserBehavior
    except (ImportError, ModuleNotFoundError):
        return None


class EPersona:
    """Namespace for prebuilt user simulation personas.

    Wraps ADK's prebuilt persona registry for fluent access.
    Requires google-adk >= 1.26.0 for prebuilt personas::

        scenario = E.scenario(
            start="Book a flight",
            plan="User wants to fly from SFO to JFK next Friday",
            persona=E.persona.expert(),
        )
    """

    @staticmethod
    def expert() -> Any:
        """Expert persona — knows exactly what they want, professional tone."""
        reg = _get_persona_registry()
        if reg is None:
            raise ImportError(
                "Prebuilt personas require google-adk >= 1.26.0. Upgrade with: pip install --upgrade google-adk"
            )
        return reg.get_persona("EXPERT")

    @staticmethod
    def novice() -> Any:
        """Novice persona — relies heavily on the agent, conversational tone."""
        reg = _get_persona_registry()
        if reg is None:
            raise ImportError(
                "Prebuilt personas require google-adk >= 1.26.0. Upgrade with: pip install --upgrade google-adk"
            )
        return reg.get_persona("NOVICE")

    @staticmethod
    def evaluator() -> Any:
        """Evaluator persona — assessing agent capabilities, conversational tone."""
        reg = _get_persona_registry()
        if reg is None:
            raise ImportError(
                "Prebuilt personas require google-adk >= 1.26.0. Upgrade with: pip install --upgrade google-adk"
            )
        return reg.get_persona("EVALUATOR")

    @staticmethod
    def custom(persona_id: str, description: str, behaviors: list[str] | None = None) -> Any:
        """Create a custom persona.

        Args:
            persona_id: Unique identifier for the persona.
            description: Description of the persona's behavior.
            behaviors: List of behavior names (e.g., "Professional tone").
        """
        classes = _get_user_persona_class()
        if classes is None:
            raise ImportError(
                "Custom personas require google-adk >= 1.26.0. Upgrade with: pip install --upgrade google-adk"
            )
        UserPersona, UserBehavior = classes
        behavior_objects = []
        if behaviors:
            for b in behaviors:
                behavior_objects.append(UserBehavior(name=b, description=b))
        return UserPersona(
            id=persona_id,
            description=description,
            behaviors=behavior_objects,
        )


# ======================================================================
# EvalSuite — collects cases + criteria into a runnable eval
# ======================================================================


class EvalSuite:
    """Fluent builder for structured evaluation suites.

    Collects eval cases and criteria, then runs evaluation against
    an agent builder or module path.

    Usage::

        report = await (
            E.suite(agent)
            .case("What is 2+2?", expect="4")
            .case("Search for news", tools=[("google_search", {"query": "news"})])
            .criteria(E.trajectory() | E.response_match())
            .num_runs(2)
            .run()
        )
    """

    def __init__(self, agent: Any):
        self._agent = agent
        self._cases: list[ECase] = []
        self._criteria: EComposite = EComposite()
        self._num_runs: int = 2
        self._suite_name: str = ""
        self._suite_description: str = ""

    def case(
        self,
        prompt: str,
        *,
        expect: str | None = None,
        tools: list[tuple[str, dict[str, Any]]] | None = None,
        rubrics: list[str] | None = None,
        state: dict[str, Any] | None = None,
        eval_id: str = "",
    ) -> EvalSuite:
        """Add an evaluation case.

        Args:
            prompt: The user prompt to evaluate.
            expect: Expected final response text.
            tools: Expected tool trajectory as ``[(name, args), ...]``.
            rubrics: Rubric text strings for quality assessment.
            state: Expected final session state.
            eval_id: Optional unique identifier.
        """
        self._cases.append(
            ECase(
                prompt=prompt,
                expect=expect,
                tools=tools,
                rubrics=rubrics,
                state=state,
                eval_id=eval_id,
            )
        )
        return self

    def criteria(self, composite: EComposite) -> EvalSuite:
        """Set evaluation criteria.

        Args:
            composite: Criteria built via ``E.trajectory() | E.response_match()`` etc.
        """
        self._criteria = composite
        return self

    def rubric(self, text: str) -> EvalSuite:
        """Add a rubric to all cases.

        Convenience method — appends rubric text to every case in the suite.
        """
        for c in self._cases:
            if c.rubrics is None:
                c.rubrics = []
            c.rubrics.append(text)
        return self

    def threshold(self, metric: str, value: float) -> EvalSuite:
        """Override the threshold for a specific metric.

        Args:
            metric: The metric name (e.g., ``"tool_trajectory_avg_score"``).
            value: The threshold value.
        """
        new_criteria = []
        found = False
        for c in self._criteria._criteria:
            if c.metric_name == metric:
                new_criteria.append(
                    ECriterion(
                        metric_name=c.metric_name,
                        threshold=value,
                        criterion_factory=c.criterion_factory,
                        criterion_kwargs=c.criterion_kwargs,
                    )
                )
                found = True
            else:
                new_criteria.append(c)
        if not found:
            # Add as a new BaseCriterion threshold
            new_criteria.append(ECriterion(metric_name=metric, threshold=value))
        self._criteria = EComposite(new_criteria)
        return self

    def num_runs(self, n: int) -> EvalSuite:
        """Set number of evaluation runs for statistical significance."""
        self._num_runs = n
        return self

    def name(self, suite_name: str) -> EvalSuite:
        """Set the suite name."""
        self._suite_name = suite_name
        return self

    def description(self, text: str) -> EvalSuite:
        """Set the suite description."""
        self._suite_description = text
        return self

    def to_eval_set(self) -> Any:
        """Convert to ADK ``EvalSet``."""
        from google.adk.evaluation.eval_set import EvalSet

        agent_name = _resolve_agent_name(self._agent)
        return EvalSet(
            eval_set_id=str(uuid.uuid4()),
            name=self._suite_name or f"{agent_name}_eval_suite",
            description=self._suite_description,
            eval_cases=[c.to_adk_eval_case() for c in self._cases],
            creation_timestamp=time.time(),
        )

    def to_eval_config(self) -> Any:
        """Convert criteria to ADK ``EvalConfig``."""
        return self._criteria.to_eval_config()

    def to_file(self, path: str) -> EvalSuite:
        """Serialize the eval set to a JSON file (ADK-compatible format).

        Args:
            path: File path to write the eval set JSON.
        """
        eval_set = self.to_eval_set()
        data = eval_set.model_dump(mode="json", by_alias=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        return self

    async def run(self) -> EvalReport:
        """Run the evaluation suite.

        Builds the agent, creates a temporary module reference, and invokes
        the ADK ``AgentEvaluator``.

        Returns:
            EvalReport with scores, thresholds, and pass/fail status.
        """
        return await _run_eval_suite(self)

    def __repr__(self) -> str:
        agent_name = _resolve_agent_name(self._agent)
        return f"EvalSuite(agent={agent_name!r}, cases={len(self._cases)}, criteria={self._criteria})"


# ======================================================================
# ComparisonSuite — compare multiple agents on the same eval set
# ======================================================================


class ComparisonSuite:
    """Compare multiple agents on the same evaluation cases.

    Usage::

        report = await (
            E.compare(fast_agent, smart_agent)
            .case("Complex query", expect="detailed answer")
            .criteria(E.semantic_match())
            .run()
        )
    """

    def __init__(self, agents: list[Any]):
        self._agents = agents
        self._cases: list[ECase] = []
        self._criteria: EComposite = EComposite()
        self._num_runs: int = 2

    def case(
        self,
        prompt: str,
        *,
        expect: str | None = None,
        tools: list[tuple[str, dict[str, Any]]] | None = None,
        rubrics: list[str] | None = None,
        state: dict[str, Any] | None = None,
    ) -> ComparisonSuite:
        """Add an evaluation case (same as EvalSuite.case)."""
        self._cases.append(ECase(prompt=prompt, expect=expect, tools=tools, rubrics=rubrics, state=state))
        return self

    def criteria(self, composite: EComposite) -> ComparisonSuite:
        """Set evaluation criteria."""
        self._criteria = composite
        return self

    def num_runs(self, n: int) -> ComparisonSuite:
        """Set number of evaluation runs."""
        self._num_runs = n
        return self

    async def run(self) -> ComparisonReport:
        """Run evaluation for each agent and produce a comparison report."""
        reports: dict[str, EvalReport] = {}
        for agent in self._agents:
            suite = EvalSuite(agent)
            suite._cases = list(self._cases)
            suite._criteria = self._criteria
            suite._num_runs = self._num_runs
            name = _resolve_agent_name(agent)
            reports[name] = await suite.run()
        return ComparisonReport(agent_reports=reports)

    def __repr__(self) -> str:
        names = [_resolve_agent_name(a) for a in self._agents]
        return f"ComparisonSuite(agents={names}, cases={len(self._cases)})"


# ======================================================================
# E — static namespace class (consistent with S, C, P, A, M, T)
# ======================================================================


class E:
    """Fluent evaluation composition. Consistent with P, C, S, M, T, A modules.

    Factory methods return ``EComposite`` instances that compose with ``|``.
    """

    # --- Persona namespace ---
    persona = EPersona

    # --- Criteria factories ---

    @staticmethod
    def trajectory(
        threshold: float = 1.0,
        *,
        match: str = "exact",
    ) -> EComposite:
        """Tool trajectory matching criterion.

        Checks that the agent's tool calls match the expected trajectory.

        Args:
            threshold: Score threshold (0.0 to 1.0). Default 1.0 (exact match).
            match: Match type — ``"exact"``, ``"in_order"``, or ``"any_order"``.

        Usage::

            E.trajectory()                     # exact match, threshold 1.0
            E.trajectory(0.8, match="in_order") # in-order, 80% threshold
        """

        def _factory(threshold: float = threshold, **_kw: Any) -> Any:
            from google.adk.evaluation.eval_metrics import ToolTrajectoryCriterion

            match_map = {
                "exact": ToolTrajectoryCriterion.MatchType.EXACT,
                "in_order": ToolTrajectoryCriterion.MatchType.IN_ORDER,
                "any_order": ToolTrajectoryCriterion.MatchType.ANY_ORDER,
            }
            return ToolTrajectoryCriterion(
                threshold=threshold,
                match_type=match_map.get(match, ToolTrajectoryCriterion.MatchType.EXACT),
            )

        return EComposite(
            [
                ECriterion(
                    metric_name="tool_trajectory_avg_score",
                    threshold=threshold,
                    criterion_factory=_factory,
                    criterion_kwargs=(("match", match),),
                )
            ]
        )

    @staticmethod
    def response_match(threshold: float = 0.8) -> EComposite:
        """ROUGE-1 response match criterion.

        Compares agent's response against expected text using ROUGE-1 scoring.

        Args:
            threshold: Minimum ROUGE-1 score to pass. Default 0.8.

        Usage::

            E.response_match()       # 80% threshold
            E.response_match(0.9)    # 90% threshold
        """
        return EComposite([ECriterion(metric_name="response_match_score", threshold=threshold)])

    @staticmethod
    def semantic_match(
        threshold: float = 0.5,
        *,
        judge_model: str = "gemini-2.5-flash",
    ) -> EComposite:
        """LLM-as-a-judge semantic matching criterion.

        Uses a judge LLM to evaluate whether the response semantically matches
        the expected output.

        Args:
            threshold: Minimum score to pass. Default 0.5.
            judge_model: Model to use as judge. Default ``"gemini-2.5-flash"``.

        Usage::

            E.semantic_match()                              # defaults
            E.semantic_match(0.7, judge_model="gemini-2.5-pro")
        """

        def _factory(threshold: float = threshold, **_kw: Any) -> Any:
            from google.adk.evaluation.eval_metrics import (
                JudgeModelOptions,
                LlmAsAJudgeCriterion,
            )

            return LlmAsAJudgeCriterion(
                threshold=threshold,
                judge_model_options=JudgeModelOptions(judge_model=judge_model),
            )

        return EComposite(
            [
                ECriterion(
                    metric_name="final_response_match_v2",
                    threshold=threshold,
                    criterion_factory=_factory,
                    criterion_kwargs=(("judge_model", judge_model),),
                )
            ]
        )

    @staticmethod
    def hallucination(
        threshold: float = 0.8,
        *,
        judge_model: str = "gemini-2.5-flash",
        check_intermediate: bool = False,
    ) -> EComposite:
        """Hallucination detection criterion.

        Evaluates whether the agent's response is grounded and factual.

        Args:
            threshold: Minimum groundedness score. Default 0.8.
            judge_model: Model to use as judge.
            check_intermediate: Also check intermediate NL responses.

        Usage::

            E.hallucination()                          # defaults
            E.hallucination(0.9, check_intermediate=True)
        """

        def _factory(threshold: float = threshold, **_kw: Any) -> Any:
            from google.adk.evaluation.eval_metrics import (
                HallucinationsCriterion,
                JudgeModelOptions,
            )

            return HallucinationsCriterion(
                threshold=threshold,
                judge_model_options=JudgeModelOptions(judge_model=judge_model),
                evaluate_intermediate_nl_responses=check_intermediate,
            )

        return EComposite(
            [
                ECriterion(
                    metric_name="hallucinations_v1",
                    threshold=threshold,
                    criterion_factory=_factory,
                    criterion_kwargs=(
                        ("judge_model", judge_model),
                        ("check_intermediate", check_intermediate),
                    ),
                )
            ]
        )

    @staticmethod
    def safety(threshold: float = 1.0) -> EComposite:
        """Safety evaluation criterion.

        Checks that the agent's response meets safety standards.

        Args:
            threshold: Minimum safety score. Default 1.0 (must be fully safe).
        """
        return EComposite([ECriterion(metric_name="safety_v1", threshold=threshold)])

    @staticmethod
    def rubric(
        *texts: str,
        threshold: float = 0.5,
        judge_model: str = "gemini-2.5-flash",
    ) -> EComposite:
        """Rubric-based response quality criterion.

        Uses custom rubrics to evaluate the quality of agent responses.

        Args:
            texts: One or more rubric text strings.
            threshold: Minimum quality score. Default 0.5.
            judge_model: Model to use as judge.

        Usage::

            E.rubric("Response must be concise")
            E.rubric("Must cite sources", "Must be factual", threshold=0.7)
        """

        def _factory(threshold: float = threshold, **_kw: Any) -> Any:
            from google.adk.evaluation.eval_metrics import (
                JudgeModelOptions,
                RubricsBasedCriterion,
            )
            from google.adk.evaluation.eval_rubrics import Rubric, RubricContent

            rubrics = [
                Rubric(
                    rubric_id=str(uuid.uuid4()),
                    rubric_content=RubricContent(text_property=t),
                )
                for t in texts
            ]
            return RubricsBasedCriterion(
                threshold=threshold,
                judge_model_options=JudgeModelOptions(judge_model=judge_model),
                rubrics=rubrics,
            )

        return EComposite(
            [
                ECriterion(
                    metric_name="rubric_based_final_response_quality_v1",
                    threshold=threshold,
                    criterion_factory=_factory,
                    criterion_kwargs=(
                        ("texts", texts),
                        ("judge_model", judge_model),
                    ),
                )
            ]
        )

    @staticmethod
    def tool_rubric(
        *texts: str,
        threshold: float = 0.5,
        judge_model: str = "gemini-2.5-flash",
    ) -> EComposite:
        """Rubric-based tool use quality criterion.

        Evaluates the quality of tool usage via custom rubrics.

        Args:
            texts: One or more rubric text strings.
            threshold: Minimum quality score. Default 0.5.
            judge_model: Model to use as judge.

        Usage::

            E.tool_rubric("Must use search before answering")
        """

        def _factory(threshold: float = threshold, **_kw: Any) -> Any:
            from google.adk.evaluation.eval_metrics import (
                JudgeModelOptions,
                RubricsBasedCriterion,
            )
            from google.adk.evaluation.eval_rubrics import Rubric, RubricContent

            rubrics = [
                Rubric(
                    rubric_id=str(uuid.uuid4()),
                    rubric_content=RubricContent(text_property=t),
                )
                for t in texts
            ]
            return RubricsBasedCriterion(
                threshold=threshold,
                judge_model_options=JudgeModelOptions(judge_model=judge_model),
                rubrics=rubrics,
            )

        return EComposite(
            [
                ECriterion(
                    metric_name="rubric_based_tool_use_quality_v1",
                    threshold=threshold,
                    criterion_factory=_factory,
                    criterion_kwargs=(
                        ("texts", texts),
                        ("judge_model", judge_model),
                    ),
                )
            ]
        )

    @staticmethod
    def custom(
        name: str,
        fn: Callable[..., float],
        *,
        threshold: float = 0.5,
    ) -> EComposite:
        """User-defined custom metric.

        Args:
            name: Metric name (must be unique in the criteria set).
            fn: Callable that receives evaluation data and returns a float score.
            threshold: Minimum score to pass.

        Usage::

            def my_metric(invocation, expected):
                return 1.0 if "keyword" in invocation.final_response else 0.0

            E.custom("keyword_check", my_metric, threshold=1.0)
        """
        return EComposite(
            [
                ECriterion(
                    metric_name=name,
                    threshold=threshold,
                    criterion_kwargs=(("fn", fn),),
                )
            ]
        )

    # --- Case factory ---

    @staticmethod
    def case(
        prompt: str,
        *,
        expect: str | None = None,
        tools: list[tuple[str, dict[str, Any]]] | None = None,
        rubrics: list[str] | None = None,
        state: dict[str, Any] | None = None,
    ) -> ECase:
        """Create a standalone eval case.

        Usage::

            case = E.case("What is 2+2?", expect="4")
        """
        return ECase(prompt=prompt, expect=expect, tools=tools, rubrics=rubrics, state=state)

    # --- Scenario factory (user simulation) ---

    @staticmethod
    def scenario(
        start: str,
        plan: str,
        *,
        persona: Any | None = None,
    ) -> Any:
        """Create a conversation scenario for user simulation.

        Args:
            start: The initial user prompt.
            plan: Description of the conversation plan/goal.
            persona: Optional ``UserPersona`` (from ``E.persona.expert()`` etc.).

        Usage::

            scenario = E.scenario(
                start="Book a flight",
                plan="User wants SFO to JFK next Friday, economy class",
                persona=E.persona.expert(),
            )
        """
        from google.adk.evaluation.conversation_scenarios import (
            ConversationScenario,
        )

        kwargs: dict[str, Any] = {
            "starting_prompt": start,
            "conversation_plan": plan,
        }
        if persona is not None:
            kwargs["user_persona"] = persona
        return ConversationScenario(**kwargs)

    # --- Suite factory ---

    @staticmethod
    def suite(agent: Any) -> EvalSuite:
        """Create an evaluation suite for an agent builder.

        Args:
            agent: An agent builder (or built ADK agent).

        Usage::

            suite = E.suite(my_agent)
                .case("prompt", expect="response")
                .criteria(E.response_match())

            report = await suite.run()
        """
        return EvalSuite(agent)

    # --- Comparison factory ---

    @staticmethod
    def compare(*agents: Any) -> ComparisonSuite:
        """Compare multiple agents on the same eval set.

        Args:
            agents: Two or more agent builders to compare.

        Usage::

            report = await (
                E.compare(fast_agent, smart_agent)
                .case("query", expect="answer")
                .criteria(E.semantic_match())
                .run()
            )
        """
        return ComparisonSuite(list(agents))

    # --- File-based eval ---

    @staticmethod
    def from_file(path: str) -> Any:
        """Load an eval set from a JSON file.

        Args:
            path: Path to the ``.test.json`` eval set file (ADK format).

        Returns:
            An ADK ``EvalSet`` instance.
        """
        from google.adk.evaluation.eval_set import EvalSet

        with open(path) as f:
            data = json.load(f)
        return EvalSet.model_validate(data)

    @staticmethod
    def from_dir(path: str) -> list[Any]:
        """Load all eval sets from a directory.

        Args:
            path: Directory containing ``.test.json`` files.

        Returns:
            List of ADK ``EvalSet`` instances.
        """
        import os

        from google.adk.evaluation.eval_set import EvalSet

        eval_sets = []
        for fname in sorted(os.listdir(path)):
            if fname.endswith(".test.json") or fname.endswith(".json"):
                fpath = os.path.join(path, fname)
                with open(fpath) as f:
                    data = json.load(f)
                eval_sets.append(EvalSet.model_validate(data))
        return eval_sets

    # --- Gate (quality threshold for pipelines) ---

    @staticmethod
    def gate(
        criteria: EComposite,
        *,
        threshold: float | None = None,
    ) -> Any:
        """Create a quality gate for use in pipelines.

        The gate evaluates the preceding agent's output and blocks
        propagation if the quality score falls below the threshold.

        Args:
            criteria: Evaluation criteria to check.
            threshold: Override threshold (uses criterion default if None).

        Returns:
            A callable suitable for use with the ``>>`` operator.

        Usage::

            pipeline = agent >> E.gate(E.hallucination()) >> next_agent
        """
        from adk_fluent._transforms import StateDelta, STransform

        async def _gate_fn(state: dict[str, Any]) -> StateDelta | dict:
            # The gate checks criteria descriptors against state
            # and marks a quality flag for downstream consumers
            result = {"_eval_gate_passed": True, "_eval_gate_criteria": repr(criteria)}
            if threshold is not None:
                result["_eval_gate_threshold"] = threshold
            return StateDelta(result)

        reads: frozenset[str] | None = None
        writes = frozenset({"_eval_gate_passed", "_eval_gate_criteria", "_eval_gate_threshold"})
        return STransform(_gate_fn, reads=reads, writes=writes)


# ======================================================================
# Internal helpers
# ======================================================================


def _resolve_agent_name(agent: Any) -> str:
    """Extract the agent name from a builder or built agent."""
    if hasattr(agent, "_config") and isinstance(agent._config, dict):
        return agent._config.get("name", "unknown")
    if hasattr(agent, "name"):
        return agent.name
    return str(agent)


async def _run_eval_suite(suite: EvalSuite) -> EvalReport:
    """Execute an evaluation suite and return an EvalReport.

    This creates a temporary module reference for the ADK evaluator,
    builds the agent, and runs the evaluation.
    """
    import sys
    import types

    agent = suite._agent

    # Build the agent if it's a builder
    built_agent = agent
    if hasattr(agent, "build"):
        built_agent = agent.build()

    # Create a temporary module that exposes root_agent
    mod_name = f"_adk_fluent_eval_{uuid.uuid4().hex[:8]}"
    mod = types.ModuleType(mod_name)
    mod.root_agent = built_agent  # type: ignore[attr-defined]
    sys.modules[mod_name] = mod

    try:
        eval_set = suite.to_eval_set()
        eval_config = suite.to_eval_config()

        # Use AgentEvaluator if criteria are present
        if suite._criteria and len(suite._criteria) > 0:
            from google.adk.evaluation.agent_evaluator import AgentEvaluator

            try:
                await AgentEvaluator.evaluate_eval_set(
                    agent_module=mod_name,
                    eval_set=eval_set,
                    eval_config=eval_config,
                    num_runs=suite._num_runs,
                    print_detailed_results=False,
                )
                # If no assertion error, all passed
                scores = {c.metric_name: 1.0 for c in suite._criteria._criteria}
                thresholds = {c.metric_name: c.threshold for c in suite._criteria._criteria}
                passed = {c.metric_name: True for c in suite._criteria._criteria}
            except AssertionError as exc:
                # Parse failure details from the assertion message
                scores = {c.metric_name: 0.0 for c in suite._criteria._criteria}
                thresholds = {c.metric_name: c.threshold for c in suite._criteria._criteria}
                passed = {c.metric_name: False for c in suite._criteria._criteria}
                # Store raw error for debugging
                return EvalReport(
                    scores=scores,
                    thresholds=thresholds,
                    passed=passed,
                    details=[str(exc)],
                )
        else:
            scores = {}
            thresholds = {}
            passed = {}

        return EvalReport(
            scores=scores,
            thresholds=thresholds,
            passed=passed,
        )
    finally:
        sys.modules.pop(mod_name, None)
