"""End-to-end integration tests for the full v5.1 feature set working together.

Covers:
- Classifier >> Route >> Handler pattern
- Context engineering with pipelines (C.none, C.user_only, C.from_state, C.from_agents)
- S.capture / C.capture integration
- Draft-Review-Edit multi-agent pattern
- Memory integration
- IR-first build path (unchecked, advisory, strict)
- Pipeline-level visibility policies
"""

from adk_fluent import Agent, S
from adk_fluent._context import C
from adk_fluent._routing import Route
from adk_fluent._visibility import infer_visibility
from adk_fluent.testing import check_contracts


# ======================================================================
# 1. Classifier >> Route >> Handler
# ======================================================================


class TestClassifierRouterPattern:
    """The canonical pattern: classifier >> Route >> handler."""

    def test_builds_successfully(self):
        pipeline = (
            S.capture("user_message")
            >> Agent("classifier")
            .model("gemini-2.5-flash")
            .instruct("Classify the user's intent.")
            .outputs("intent")
            >> Route("intent")
            .eq(
                "booking",
                Agent("booker")
                .model("gemini-2.5-flash")
                .instruct("Help book. User said: {user_message}. Intent: {intent}")
                .context(C.from_state("user_message", "intent")),
            )
            .eq(
                "info",
                Agent("info")
                .model("gemini-2.5-flash")
                .instruct("Provide info. User said: {user_message}")
                .context(C.from_state("user_message")),
            )
        )
        built = pipeline.build()
        assert built is not None

    def test_contract_check_passes(self):
        pipeline = (
            S.capture("user_message")
            >> Agent("classifier")
            .model("gemini-2.5-flash")
            .instruct("Classify.")
            .outputs("intent")
            >> Route("intent")
            .eq(
                "booking",
                Agent("booker")
                .model("gemini-2.5-flash")
                .instruct("Book: {intent}")
                .context(C.from_state("intent")),
            )
        )
        issues = check_contracts(pipeline.to_ir())
        errors = [i for i in issues if isinstance(i, dict) and i.get("level") == "error"]
        assert len(errors) == 0

    def test_visibility_inferred(self):
        pipeline = (
            Agent("classifier")
            .model("gemini-2.5-flash")
            .instruct("Classify.")
            .outputs("intent")
            >> Agent("handler").model("gemini-2.5-flash").instruct("Handle: {intent}")
        )
        ir = pipeline.to_ir()
        vis = infer_visibility(ir)
        assert vis["classifier"] == "internal"
        assert vis["handler"] == "user"


# ======================================================================
# 2. Context engineering with pipelines
# ======================================================================


class TestContextWithPipeline:
    """C transforms compile correctly in isolation and within pipelines."""

    def test_context_none_compiles(self):
        a = Agent("a").model("gemini-2.5-flash").instruct("Process.").context(C.none())
        built = a.build()
        assert built.include_contents == "none"

    def test_context_user_only_compiles(self):
        a = Agent("a").model("gemini-2.5-flash").instruct("Review.").context(C.user_only())
        built = a.build()
        assert built.include_contents == "none"
        assert callable(built.instruction)

    def test_context_from_state_in_pipeline(self):
        pipeline = (
            Agent("researcher").model("gemini-2.5-flash").instruct("Research.").outputs("findings")
            >> Agent("writer").model("gemini-2.5-flash").instruct("Write a report.").context(C.from_state("findings"))
        )
        built = pipeline.build()
        writer = built.sub_agents[1]
        assert writer.include_contents == "none"
        assert callable(writer.instruction)


# ======================================================================
# 3. Capture integration
# ======================================================================


class TestCaptureIntegration:
    """S.capture and C.capture work identically and build CaptureAgent."""

    def test_s_capture_builds_capture_agent(self):
        pipeline = S.capture("user_message") >> Agent("a").model("gemini-2.5-flash")
        built = pipeline.build()
        from adk_fluent._base import CaptureAgent

        assert isinstance(built.sub_agents[0], CaptureAgent)

    def test_c_capture_same_as_s_capture(self):
        fn_s = S.capture("msg")
        fn_c = C.capture("msg")
        assert fn_s.__name__ == fn_c.__name__
        assert hasattr(fn_s, "_capture_key")
        assert hasattr(fn_c, "_capture_key")


# ======================================================================
# 4. Draft-Review-Edit multi-agent pattern
# ======================================================================


class TestDraftReviewEditPattern:
    """Multi-agent composition with selective context."""

    def test_draft_review_edit_builds(self):
        pipeline = (
            Agent("drafter").model("gemini-2.5-flash").instruct("Write initial draft.")
            >> Agent("reviewer")
            .model("gemini-2.5-flash")
            .instruct("Review the draft.")
            .context(C.user_only())
            >> Agent("editor")
            .model("gemini-2.5-flash")
            .instruct("Edit based on review.")
            .context(C.from_agents("drafter", "reviewer"))
        )
        built = pipeline.build()
        assert len(built.sub_agents) == 3

        reviewer = built.sub_agents[1]
        assert reviewer.include_contents == "none"
        assert callable(reviewer.instruction)

        editor = built.sub_agents[2]
        assert editor.include_contents == "none"
        assert callable(editor.instruction)

    def test_visibility_for_draft_review_edit(self):
        pipeline = (
            Agent("drafter").model("m").instruct("Draft.")
            >> Agent("reviewer").model("m").instruct("Review.")
            >> Agent("editor").model("m").instruct("Edit.")
        )
        ir = pipeline.to_ir()
        vis = infer_visibility(ir)
        assert vis["drafter"] == "internal"
        assert vis["reviewer"] == "internal"
        assert vis["editor"] == "user"


# ======================================================================
# 5. Memory integration
# ======================================================================


class TestMemoryIntegration:
    """memory('preload') adds tools to agents."""

    def test_memory_preload_builds(self):
        a = Agent("a").model("gemini-2.5-flash").memory("preload")
        built = a.build()
        assert len(built.tools) >= 1

    def test_memory_in_pipeline(self):
        pipeline = (
            Agent("a").model("gemini-2.5-flash").instruct("Answer questions.").memory("preload")
            >> Agent("b").model("gemini-2.5-flash").instruct("Summarize.")
        )
        built = pipeline.build()
        assert len(built.sub_agents[0].tools) >= 1


# ======================================================================
# 6. IR-first build path
# ======================================================================


class TestIRFirstBuildIntegration:
    """build() runs contracts by default; unchecked().build() skips them."""

    def test_pipeline_build_runs_contracts(self):
        pipeline = (
            Agent("a").model("m").instruct("Classify.").outputs("intent")
            >> Agent("b").model("m").instruct("Handle: {intent}")
        )
        built = pipeline.build()  # Should succeed with advisory diagnostics
        assert built is not None

    def test_pipeline_unchecked_skips_contracts(self):
        pipeline = (
            Agent("a").model("m").instruct("Do.")
            >> Agent("b").model("m").instruct("Use: {missing_key}")
        )
        built = pipeline.unchecked().build()
        assert built is not None


# ======================================================================
# 7. Pipeline-level visibility policies
# ======================================================================


class TestPipelinePolicies:
    """Pipeline has transparent/filtered/annotated policy methods."""

    def test_transparent_policy(self):
        pipeline = (
            Agent("a").model("m").instruct("Classify.").outputs("intent")
            >> Agent("b").model("m").instruct("Handle.")
        )
        assert hasattr(pipeline, "transparent")

    def test_filtered_policy(self):
        pipeline = (
            Agent("a").model("m").instruct("Classify.")
            >> Agent("b").model("m").instruct("Handle.")
        )
        assert hasattr(pipeline, "filtered")
