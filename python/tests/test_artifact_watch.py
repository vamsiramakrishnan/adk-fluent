"""Tests for A.watch / A.watch_version / A.on_change — the subscribe/observe
dual of A.publish.

Mirrors the in-memory ctx test pattern from tests/manual/test_artifacts.py:
ATransform descriptors are inspected directly, and runtime behaviour is proven
by driving ArtifactAgent._run_async_impl against a mocked artifact service.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

# ----------------------------------------------------------------------
# Descriptor shape — A.watch mirrors A.snapshot (artifact -> state bridge)
# ----------------------------------------------------------------------


class TestWatchDescriptor:
    def test_watch_returns_atransform(self):
        from adk_fluent._artifacts import A, ATransform

        at = A.watch("report.md", into="text")
        assert isinstance(at, ATransform)

    def test_watch_uses_snapshot_runtime_op(self):
        """watch reuses the snapshot op so the existing runtime executes it."""
        from adk_fluent._artifacts import A

        at = A.watch("report.md", into="text")
        assert at._op == "snapshot"
        assert at._artifact_op == "snapshot"

    def test_watch_bridges_state_into_key(self):
        from adk_fluent._artifacts import A

        at = A.watch("report.md", into="text")
        assert at._bridges_state is True
        assert at._filename == "report.md"
        assert at._into_key == "text"
        assert at._consumes_artifact == frozenset({"report.md"})
        assert at._produces_state == frozenset({"text"})

    def test_watch_latest_version_by_default(self):
        from adk_fluent._artifacts import A

        at = A.watch("report.md", into="text")
        assert at._version is None

    def test_watch_pinned_version(self):
        from adk_fluent._artifacts import A

        at = A.watch("report.md", into="text", version=3)
        assert at._version == 3

    def test_watch_decode_flag(self):
        from adk_fluent._artifacts import A

        at = A.watch("data.bin", into="raw", decode=True)
        assert at._decode is True

    def test_watch_user_scope(self):
        from adk_fluent._artifacts import A

        at = A.watch("shared.json", into="data", scope="user")
        assert at._scope == "user"

    def test_watch_distinct_name_from_snapshot(self):
        from adk_fluent._artifacts import A

        assert A.watch("report.md", into="t")._name == "watch_report_md"
        assert A.snapshot("report.md", into_key="t")._name == "snapshot_report_md"


class TestWatchVersionDescriptor:
    def test_watch_version_returns_atransform(self):
        from adk_fluent._artifacts import A, ATransform

        at = A.watch_version("inbox.json", into="ver")
        assert isinstance(at, ATransform)

    def test_watch_version_uses_version_op(self):
        from adk_fluent._artifacts import A

        at = A.watch_version("inbox.json", into="ver")
        assert at._op == "version"
        assert at._into_key == "ver"
        assert at._consumes_artifact == frozenset({"inbox.json"})
        assert at._produces_state == frozenset({"ver"})

    def test_watch_version_user_scope(self):
        from adk_fluent._artifacts import A

        at = A.watch_version("inbox.json", into="ver", scope="user")
        assert at._scope == "user"


# ----------------------------------------------------------------------
# Runtime — drive ArtifactAgent against a mocked artifact service
# ----------------------------------------------------------------------


def _mock_ctx(state: dict) -> MagicMock:
    ctx = MagicMock()
    ctx.session.state = state
    ctx.session.id = "sess-1"
    ctx._invocation_context.app_name = "test_app"
    ctx._invocation_context.user_id = "user-1"
    ctx._event_actions.artifact_delta = {}
    return ctx


class TestWatchRuntime:
    @pytest.mark.asyncio
    async def test_watch_loads_content_into_state(self):
        """A.watch loads the latest artifact text into state[into]."""
        import google.genai.types as types

        from adk_fluent._artifacts import A
        from adk_fluent._primitives import ArtifactAgent

        at = A.watch("report.md", into="text")
        agent = ArtifactAgent(name="watch", atransform=at)

        ctx = _mock_ctx({})
        svc = AsyncMock()
        svc.load_artifact = AsyncMock(return_value=types.Part.from_text(text="latest body"))
        ctx._invocation_context.artifact_service = svc

        async for _ in agent._run_async_impl(ctx):
            pass

        assert ctx.session.state["text"] == "latest body"
        # latest version requested (version=None passed through)
        assert svc.load_artifact.call_args[1]["version"] is None
        assert svc.load_artifact.call_args[1]["filename"] == "report.md"

    @pytest.mark.asyncio
    async def test_watch_reflects_new_artifact_content_on_rerun(self):
        """Re-running watch after the artifact changes updates state[into]."""
        import google.genai.types as types

        from adk_fluent._artifacts import A
        from adk_fluent._primitives import ArtifactAgent

        at = A.watch("inbox.json", into="inbox")
        agent = ArtifactAgent(name="watch", atransform=at)
        ctx = _mock_ctx({})
        svc = AsyncMock()
        ctx._invocation_context.artifact_service = svc

        svc.load_artifact = AsyncMock(return_value=types.Part.from_text(text="v1"))
        async for _ in agent._run_async_impl(ctx):
            pass
        assert ctx.session.state["inbox"] == "v1"

        # Artifact gets rewritten; watch run again observes the change.
        svc.load_artifact = AsyncMock(return_value=types.Part.from_text(text="v2"))
        async for _ in agent._run_async_impl(ctx):
            pass
        assert ctx.session.state["inbox"] == "v2"

    @pytest.mark.asyncio
    async def test_watch_pinned_version_passed_through(self):
        import google.genai.types as types

        from adk_fluent._artifacts import A
        from adk_fluent._primitives import ArtifactAgent

        at = A.watch("report.md", into="text", version=2)
        agent = ArtifactAgent(name="watch", atransform=at)
        ctx = _mock_ctx({})
        svc = AsyncMock()
        svc.load_artifact = AsyncMock(return_value=types.Part.from_text(text="pinned"))
        ctx._invocation_context.artifact_service = svc

        async for _ in agent._run_async_impl(ctx):
            pass

        assert svc.load_artifact.call_args[1]["version"] == 2


class TestWatchVersionRuntime:
    @pytest.mark.asyncio
    async def test_watch_version_records_version_into_state(self):
        """A.watch_version records the version metadata dict into state."""
        from adk_fluent._artifacts import A
        from adk_fluent._primitives import ArtifactAgent

        at = A.watch_version("inbox.json", into="inbox_version")
        agent = ArtifactAgent(name="watch_version", atransform=at)
        ctx = _mock_ctx({})
        svc = AsyncMock()
        ver = MagicMock()
        ver.version = 0
        ver.mime_type = "application/json"
        ver.create_time = "t0"
        ver.canonical_uri = "uri0"
        svc.get_artifact_version = AsyncMock(return_value=ver)
        ctx._invocation_context.artifact_service = svc

        async for _ in agent._run_async_impl(ctx):
            pass

        assert ctx.session.state["inbox_version"]["version"] == 0

    @pytest.mark.asyncio
    async def test_watch_version_change_is_detectable(self):
        """A version bump between runs is observable in state — the R signal."""
        from adk_fluent._artifacts import A
        from adk_fluent._primitives import ArtifactAgent

        at = A.watch_version("inbox.json", into="inbox_version")
        agent = ArtifactAgent(name="watch_version", atransform=at)
        ctx = _mock_ctx({})
        svc = AsyncMock()
        ctx._invocation_context.artifact_service = svc

        v0 = MagicMock(version=0, mime_type="application/json", create_time="t0", canonical_uri="u0")
        svc.get_artifact_version = AsyncMock(return_value=v0)
        async for _ in agent._run_async_impl(ctx):
            pass
        before = ctx.session.state["inbox_version"]["version"]

        v1 = MagicMock(version=1, mime_type="application/json", create_time="t1", canonical_uri="u1")
        svc.get_artifact_version = AsyncMock(return_value=v1)
        async for _ in agent._run_async_impl(ctx):
            pass
        after = ctx.session.state["inbox_version"]["version"]

        assert before == 0
        assert after == 1
        assert before != after  # change is detectable by an R rule


# ----------------------------------------------------------------------
# A.on_change — composed subscribe steps
# ----------------------------------------------------------------------


class TestOnChange:
    def test_on_change_returns_three_steps(self):
        from adk_fluent._artifacts import A

        steps = A.on_change("inbox.json", lambda s: None, into="inbox")
        assert isinstance(steps, tuple)
        assert len(steps) == 3

    def test_on_change_step_order_and_ops(self):
        from adk_fluent._artifacts import A, ATransform

        handler = lambda s: None  # noqa: E731
        ver_step, watch_step, h = A.on_change("inbox.json", handler, into="inbox")
        assert isinstance(ver_step, ATransform)
        assert isinstance(watch_step, ATransform)
        assert ver_step._op == "version"  # version signal recorded first
        assert watch_step._op == "snapshot"  # then content loaded
        assert watch_step._into_key == "inbox"
        assert h is handler

    def test_on_change_default_version_key(self):
        from adk_fluent._artifacts import A

        ver_step, _watch, _h = A.on_change("inbox.json", lambda s: None, into="inbox")
        assert ver_step._into_key == "inbox_version"

    def test_on_change_explicit_version_key(self):
        from adk_fluent._artifacts import A

        ver_step, _watch, _h = A.on_change(
            "inbox.json", lambda s: None, into="inbox", version_key="iv"
        )
        assert ver_step._into_key == "iv"

    def test_on_change_composes_into_pipeline(self):
        """on_change returns steps (like publish_many); feed them to a Pipeline."""
        from adk_fluent import Agent
        from adk_fluent._artifacts import A
        from adk_fluent.workflow import Pipeline

        processor = Agent("processor").instruct("Handle inbox.")
        ver_step, watch_step, handler = A.on_change("inbox.json", processor, into="inbox")
        # Chain via >> (the operator auto-wraps ATransform steps via _fn_step).
        pipeline = (
            Agent("ingest").instruct("Ingest.")
            >> A.save("inbox.json", content="{}")
            >> ver_step
            >> watch_step
            >> handler
        )
        assert isinstance(pipeline, Pipeline)
        assert pipeline.build() is not None


# ----------------------------------------------------------------------
# Pipeline / IR integration — watch behaves like a first-class A step
# ----------------------------------------------------------------------


class TestWatchPipelineIntegration:
    def test_watch_in_pipeline_via_rshift(self):
        from adk_fluent import Agent
        from adk_fluent._artifacts import A
        from adk_fluent.workflow import Pipeline

        pipeline = (
            Agent("writer").instruct("Write.").writes("report")
            >> A.publish("report.md", from_key="report")
            >> A.watch("report.md", into="observed")
            >> Agent("reader").instruct("Read {observed}.")
        )
        assert isinstance(pipeline, Pipeline)

    def test_watch_fn_step_builds_artifact_builder(self):
        from adk_fluent._artifacts import A
        from adk_fluent._primitive_builders import _ArtifactBuilder, _fn_step

        builder = _fn_step(A.watch("report.md", into="text"))
        assert isinstance(builder, _ArtifactBuilder)

    def test_watch_to_ir_is_artifact_node(self):
        from adk_fluent._artifacts import A
        from adk_fluent._ir import ArtifactNode
        from adk_fluent._primitive_builders import _fn_step

        node = _fn_step(A.watch("report.md", into="text")).to_ir()
        assert isinstance(node, ArtifactNode)
        assert node.op == "snapshot"
        assert node.into_key == "text"

    def test_publish_then_watch_contract_clean(self):
        """watch after an upstream publish is contract-clean (like snapshot)."""
        from adk_fluent import Agent
        from adk_fluent._artifacts import A
        from adk_fluent.testing.contracts import check_contracts

        pipeline = (
            Agent("writer").instruct("Write.").writes("report")
            >> A.publish("report.md", from_key="report")
            >> A.watch("report.md", into="text")
        )
        issues = check_contracts(pipeline.to_ir())
        artifact_errors = [
            i
            for i in issues
            if isinstance(i, dict)
            and "artifact" in i.get("message", "").lower()
            and i["level"] == "error"
        ]
        assert artifact_errors == []


class TestWatchExports:
    def test_watch_on_a_namespace(self):
        from adk_fluent import A

        assert hasattr(A, "watch")
        assert hasattr(A, "watch_version")
        assert hasattr(A, "on_change")
