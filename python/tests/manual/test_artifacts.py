"""Tests for A module — artifact composition."""

from __future__ import annotations

import pytest


class TestMimeConstants:
    def test_text_constants(self):
        from adk_fluent._artifacts import A

        assert A.mime.text == "text/plain"
        assert A.mime.markdown == "text/markdown"
        assert A.mime.html == "text/html"
        assert A.mime.csv == "text/csv"
        assert A.mime.json == "application/json"
        assert A.mime.xml == "application/xml"
        assert A.mime.yaml == "application/yaml"

    def test_media_constants(self):
        from adk_fluent._artifacts import A

        assert A.mime.pdf == "application/pdf"
        assert A.mime.png == "image/png"
        assert A.mime.jpeg == "image/jpeg"
        assert A.mime.gif == "image/gif"
        assert A.mime.webp == "image/webp"
        assert A.mime.svg == "image/svg+xml"
        assert A.mime.mp3 == "audio/mpeg"
        assert A.mime.wav == "audio/wav"
        assert A.mime.mp4 == "video/mp4"
        assert A.mime.binary == "application/octet-stream"

    def test_detect_from_filename(self):
        from adk_fluent._artifacts import A

        assert A.mime.detect("report.md") == "text/markdown"
        assert A.mime.detect("data.json") == "application/json"
        assert A.mime.detect("chart.png") == "image/png"
        assert A.mime.detect("unknown.zzz123") == "application/octet-stream"
        assert A.mime.detect("report.pdf") == "application/pdf"

    def test_is_llm_inline(self):
        from adk_fluent._artifacts import A

        assert A.mime.is_llm_inline("image/png") is True
        assert A.mime.is_llm_inline("audio/wav") is True
        assert A.mime.is_llm_inline("video/mp4") is True
        assert A.mime.is_llm_inline("application/pdf") is True
        assert A.mime.is_llm_inline("text/plain") is False
        assert A.mime.is_llm_inline("application/json") is False

    def test_is_text_like(self):
        from adk_fluent._artifacts import A

        assert A.mime.is_text_like("text/plain") is True
        assert A.mime.is_text_like("text/markdown") is True
        assert A.mime.is_text_like("application/json") is True
        assert A.mime.is_text_like("application/csv") is True
        assert A.mime.is_text_like("application/xml") is True
        assert A.mime.is_text_like("image/png") is False
        assert A.mime.is_text_like("application/octet-stream") is False


class TestATransform:
    def test_atransform_is_callable(self):
        from adk_fluent._artifacts import ATransform

        at = ATransform(
            _fn=lambda state: None,
            _op="publish",
            _bridges_state=True,
            _filename="report.md",
            _from_key="report",
            _into_key=None,
            _mime="text/markdown",
            _scope="session",
            _version=None,
            _metadata=None,
            _content=None,
            _decode=False,
            _produces_artifact=frozenset({"report.md"}),
            _consumes_artifact=frozenset(),
            _produces_state=frozenset(),
            _consumes_state=frozenset({"report"}),
            _name="publish_report",
        )
        assert callable(at)
        assert at({"report": "text"}) is None

    def test_atransform_has_artifact_op_attr(self):
        from adk_fluent._artifacts import ATransform

        at = ATransform(
            _fn=lambda state: None,
            _op="snapshot",
            _bridges_state=True,
            _filename="report.md",
            _from_key=None,
            _into_key="text",
            _mime=None,
            _scope="session",
            _version=None,
            _metadata=None,
            _content=None,
            _decode=False,
            _produces_artifact=frozenset(),
            _consumes_artifact=frozenset({"report.md"}),
            _produces_state=frozenset({"text"}),
            _consumes_state=frozenset(),
            _name="snapshot_report",
        )
        assert at._artifact_op == "snapshot"

    def test_atransform_bridges_state_flag(self):
        from adk_fluent._artifacts import ATransform

        bridge = ATransform(
            _fn=lambda s: None,
            _op="publish",
            _bridges_state=True,
            _filename="f",
            _from_key="k",
            _into_key=None,
            _mime=None,
            _scope="session",
            _version=None,
            _metadata=None,
            _content=None,
            _decode=False,
            _produces_artifact=frozenset({"f"}),
            _consumes_artifact=frozenset(),
            _produces_state=frozenset(),
            _consumes_state=frozenset({"k"}),
            _name="t",
        )
        direct = ATransform(
            _fn=lambda s: None,
            _op="save",
            _bridges_state=False,
            _filename="f",
            _from_key=None,
            _into_key=None,
            _mime=None,
            _scope="session",
            _version=None,
            _metadata=None,
            _content=None,
            _decode=False,
            _produces_artifact=frozenset({"f"}),
            _consumes_artifact=frozenset(),
            _produces_state=frozenset(),
            _consumes_state=frozenset(),
            _name="t",
        )
        assert bridge._bridges_state is True
        assert direct._bridges_state is False


class TestPublish:
    def test_publish_from_state_key(self):
        from adk_fluent._artifacts import A, ATransform

        at = A.publish("report.md", from_key="report")
        assert isinstance(at, ATransform)
        assert at._op == "publish"
        assert at._bridges_state is True
        assert at._filename == "report.md"
        assert at._from_key == "report"
        assert at._consumes_state == frozenset({"report"})
        assert at._produces_artifact == frozenset({"report.md"})

    def test_publish_auto_detects_mime(self):
        from adk_fluent._artifacts import A

        at = A.publish("report.md", from_key="report")
        assert at._mime == "text/markdown"

    def test_publish_explicit_mime(self):
        from adk_fluent._artifacts import A

        at = A.publish("chart.png", from_key="data", mime=A.mime.png)
        assert at._mime == "image/png"

    def test_publish_with_metadata(self):
        from adk_fluent._artifacts import A

        at = A.publish("report.md", from_key="report", metadata={"author": "bot"})
        assert at._metadata == {"author": "bot"}

    def test_publish_user_scope(self):
        from adk_fluent._artifacts import A

        at = A.publish("shared.md", from_key="report", scope="user")
        assert at._scope == "user"


class TestSnapshot:
    def test_snapshot_into_state_key(self):
        from adk_fluent._artifacts import A, ATransform

        at = A.snapshot("report.md", into_key="text")
        assert isinstance(at, ATransform)
        assert at._op == "snapshot"
        assert at._bridges_state is True
        assert at._filename == "report.md"
        assert at._into_key == "text"
        assert at._consumes_artifact == frozenset({"report.md"})
        assert at._produces_state == frozenset({"text"})

    def test_snapshot_specific_version(self):
        from adk_fluent._artifacts import A

        at = A.snapshot("report.md", into_key="text", version=2)
        assert at._version == 2

    def test_snapshot_decode_flag(self):
        from adk_fluent._artifacts import A

        at = A.snapshot("data.csv", into_key="rows", decode=True)
        assert at._decode is True


class TestSave:
    def test_save_literal_content(self):
        from adk_fluent._artifacts import A, ATransform

        at = A.save("report.md", content="# Hello")
        assert isinstance(at, ATransform)
        assert at._op == "save"
        assert at._bridges_state is False
        assert at._content == "# Hello"
        assert at._consumes_state == frozenset()
        assert at._produces_artifact == frozenset({"report.md"})

    def test_save_no_from_key(self):
        from adk_fluent._artifacts import A

        at = A.save("report.md", content="text")
        assert at._from_key is None


class TestLoad:
    def test_load_returns_atransform(self):
        from adk_fluent._artifacts import A, ATransform

        at = A.load("report.md")
        assert isinstance(at, ATransform)
        assert at._op == "load"
        assert at._bridges_state is False
        assert at._into_key is None
        assert at._produces_state == frozenset()


class TestListVersionDelete:
    def test_list_into_key(self):
        from adk_fluent._artifacts import A

        at = A.list(into_key="artifacts")
        assert at._op == "list"
        assert at._into_key == "artifacts"
        assert at._produces_state == frozenset({"artifacts"})

    def test_version_into_key(self):
        from adk_fluent._artifacts import A

        at = A.version("report.md", into_key="meta")
        assert at._op == "version"
        assert at._filename == "report.md"
        assert at._into_key == "meta"

    def test_delete(self):
        from adk_fluent._artifacts import A

        at = A.delete("report.md")
        assert at._op == "delete"
        assert at._filename == "report.md"
        assert at._produces_state == frozenset()
        assert at._consumes_state == frozenset()


class TestArtifactNode:
    def test_artifact_node_creation(self):
        from adk_fluent._ir import ArtifactNode

        node = ArtifactNode(
            name="publish_report",
            op="publish",
            bridges_state=True,
            filename="report.md",
            from_key="report",
            into_key=None,
            mime="text/markdown",
            scope="session",
            version=None,
            produces_artifact=frozenset({"report.md"}),
            consumes_artifact=frozenset(),
            produces_state=frozenset(),
            consumes_state=frozenset({"report"}),
        )
        assert node.name == "publish_report"
        assert node.bridges_state is True


class TestFnStepDetection:
    def test_fn_step_detects_artifact_op(self):
        from adk_fluent._artifacts import A
        from adk_fluent._primitive_builders import _ArtifactBuilder, _fn_step

        at = A.publish("report.md", from_key="report")
        builder = _fn_step(at)
        assert isinstance(builder, _ArtifactBuilder)

    def test_fn_step_artifact_builder_to_ir(self):
        from adk_fluent._artifacts import A
        from adk_fluent._ir import ArtifactNode
        from adk_fluent._primitive_builders import _fn_step

        at = A.publish("report.md", from_key="report")
        builder = _fn_step(at)
        ir_node = builder.to_ir()
        assert isinstance(ir_node, ArtifactNode)
        assert ir_node.op == "publish"
        assert ir_node.filename == "report.md"
        assert ir_node.produces_artifact == frozenset({"report.md"})


class TestWhen:
    def test_when_wraps_atransform(self):
        from adk_fluent._artifacts import A, ATransform

        inner = A.publish("report.md", from_key="report")
        at = A.when("has_report", inner)
        assert isinstance(at, ATransform)
        assert at._op == "publish"
        assert at._filename == "report.md"


class TestArtifactAgent:
    def test_agent_creation(self):
        from adk_fluent._artifacts import A
        from adk_fluent._primitives import ArtifactAgent

        at = A.publish("report.md", from_key="report")
        agent = ArtifactAgent(name="publish_report", atransform=at)
        assert agent.name == "publish_report"

    @pytest.mark.asyncio
    async def test_publish_saves_to_artifact_service(self):
        """Integration test: publish reads state, saves artifact."""
        from unittest.mock import AsyncMock, MagicMock

        from adk_fluent._artifacts import A
        from adk_fluent._primitives import ArtifactAgent

        at = A.publish("report.md", from_key="report")
        agent = ArtifactAgent(name="test", atransform=at)

        # Mock context
        ctx = MagicMock()
        ctx.session.state = {"report": "# My Report"}
        ctx.session.id = "sess-1"
        mock_svc = AsyncMock()
        mock_svc.save_artifact = AsyncMock(return_value=0)
        ctx._invocation_context.artifact_service = mock_svc
        ctx._invocation_context.app_name = "test_app"
        ctx._invocation_context.user_id = "user-1"
        ctx._event_actions.artifact_delta = {}

        async for _ in agent._run_async_impl(ctx):
            pass

        mock_svc.save_artifact.assert_called_once()
        call_kwargs = mock_svc.save_artifact.call_args[1]
        assert call_kwargs["filename"] == "report.md"
        assert ctx._event_actions.artifact_delta["report.md"] == 0

    @pytest.mark.asyncio
    async def test_snapshot_loads_text_into_state(self):
        """Integration test: snapshot loads artifact, writes to state."""
        from unittest.mock import AsyncMock, MagicMock

        import google.genai.types as types

        from adk_fluent._artifacts import A
        from adk_fluent._primitives import ArtifactAgent

        at = A.snapshot("report.md", into_key="text")
        agent = ArtifactAgent(name="test", atransform=at)

        ctx = MagicMock()
        ctx.session.state = {}
        ctx.session.id = "sess-1"
        mock_svc = AsyncMock()
        mock_svc.load_artifact = AsyncMock(return_value=types.Part.from_text(text="# Report Content"))
        ctx._invocation_context.artifact_service = mock_svc
        ctx._invocation_context.app_name = "test_app"
        ctx._invocation_context.user_id = "user-1"

        async for _ in agent._run_async_impl(ctx):
            pass

        assert ctx.session.state["text"] == "# Report Content"


class TestPipelineIntegration:
    def test_agent_rshift_atransform(self):
        from adk_fluent import Agent
        from adk_fluent._artifacts import A
        from adk_fluent.workflow import Pipeline

        pipeline = Agent("writer").instruct("Write.") >> A.publish("report.md", from_key="output")
        assert isinstance(pipeline, Pipeline)

    def test_atransform_in_multi_step_pipeline(self):
        from adk_fluent import Agent
        from adk_fluent._artifacts import A
        from adk_fluent.workflow import Pipeline

        pipeline = (
            Agent("researcher").instruct("Research.")
            >> A.publish("findings.md", from_key="findings")
            >> A.snapshot("findings.md", into_key="source")
            >> Agent("writer").instruct("Write from {source}.")
        )
        assert isinstance(pipeline, Pipeline)

    def test_pipeline_to_ir_includes_artifact_nodes(self):
        from adk_fluent import Agent
        from adk_fluent._artifacts import A
        from adk_fluent._ir import ArtifactNode

        pipeline = Agent("writer").instruct("Write.") >> A.publish("report.md", from_key="output")
        ir = pipeline.to_ir()
        # IR should contain an ArtifactNode in SequenceNode's children
        children = ir.children if hasattr(ir, "children") else []
        artifact_nodes = [c for c in children if isinstance(c, ArtifactNode)]
        assert len(artifact_nodes) == 1
        assert artifact_nodes[0].op == "publish"


class TestExports:
    def test_import_from_adk_fluent(self):
        from adk_fluent import A, ATransform

        assert hasattr(A, "publish")
        assert hasattr(A, "mime")
        assert ATransform is not None

    def test_import_from_prelude(self):
        from adk_fluent.prelude import A

        assert hasattr(A, "publish")


class TestContentTransformsPost:
    """A.as_json, A.as_csv, A.as_text — post-snapshot transforms."""

    def test_as_json_parses_string(self):
        from adk_fluent import A
        from adk_fluent._transforms import STransform

        t = A.as_json("data")
        assert isinstance(t, STransform)
        result = t({"data": '{"x": 1}'})
        assert result == {"data": {"x": 1}}

    def test_as_json_reads_writes_keys(self):
        from adk_fluent import A

        t = A.as_json("data")
        assert t._reads_keys == frozenset({"data"})
        assert t._writes_keys == frozenset({"data"})

    def test_as_csv_parses_string(self):
        from adk_fluent import A
        from adk_fluent._transforms import STransform

        csv_text = "name,score\nAlice,90\nBob,85"
        t = A.as_csv("rows")
        assert isinstance(t, STransform)
        result = t({"rows": csv_text})
        rows = result["rows"]
        assert len(rows) == 2
        assert rows[0]["name"] == "Alice"
        assert rows[0]["score"] == "90"

    def test_as_csv_with_columns(self):
        from adk_fluent import A

        csv_text = "name,score,grade\nAlice,90,A\nBob,85,B"
        t = A.as_csv("rows", columns=["name", "score"])
        result = t({"rows": csv_text})
        rows = result["rows"]
        assert set(rows[0].keys()) == {"name", "score"}

    def test_as_text_identity(self):
        from adk_fluent import A
        from adk_fluent._transforms import STransform

        t = A.as_text("content")
        assert isinstance(t, STransform)
        result = t({"content": "hello world"})
        assert result == {"content": "hello world"}

    def test_as_text_decode_bytes(self):
        from adk_fluent import A

        t = A.as_text("content")
        result = t({"content": b"hello bytes"})
        assert result == {"content": "hello bytes"}

    def test_as_text_custom_encoding(self):
        from adk_fluent import A

        t = A.as_text("content", encoding="latin-1")
        result = t({"content": "café".encode("latin-1")})
        assert result["content"] == "café"


class TestContentTransformsPre:
    """A.from_json, A.from_csv, A.from_markdown — pre-publish transforms."""

    def test_from_json_serializes(self):
        from adk_fluent import A
        from adk_fluent._transforms import STransform

        t = A.from_json("config")
        assert isinstance(t, STransform)
        result = t({"config": {"x": 1, "y": [2, 3]}})
        import json

        assert json.loads(result["config"]) == {"x": 1, "y": [2, 3]}

    def test_from_json_indent(self):
        from adk_fluent import A

        t = A.from_json("config", indent=2)
        result = t({"config": {"x": 1}})
        assert "\n" in result["config"]  # indented output has newlines

    def test_from_csv_serializes(self):
        from adk_fluent import A
        from adk_fluent._transforms import STransform

        rows = [{"name": "Alice", "score": "90"}, {"name": "Bob", "score": "85"}]
        t = A.from_csv("rows")
        assert isinstance(t, STransform)
        result = t({"rows": rows})
        assert "Alice" in result["rows"]
        assert "Bob" in result["rows"]
        assert "name,score" in result["rows"] or "score,name" in result["rows"]

    def test_from_markdown_converts_to_html(self):
        from adk_fluent import A
        from adk_fluent._transforms import STransform

        t = A.from_markdown("report")
        assert isinstance(t, STransform)
        result = t({"report": "# Hello\n\nWorld"})
        assert "<h1>" in result["report"] or "<h1" in result["report"] or "<pre>" in result["report"]
        assert "Hello" in result["report"]

    def test_from_json_reads_writes_keys(self):
        from adk_fluent import A

        t = A.from_json("data")
        assert t._reads_keys == frozenset({"data"})
        assert t._writes_keys == frozenset({"data"})


class TestBuilderMethod:
    def test_artifacts_builder_method(self):
        from adk_fluent import Agent
        from adk_fluent._artifacts import A

        agent = (
            Agent("writer")
            .instruct("Write.")
            .writes("report")
            .artifacts(
                A.publish("report.md", from_key="report"),
            )
        )
        # Should not raise
        assert agent is not None

    def test_artifacts_multiple_transforms(self):
        from adk_fluent import Agent
        from adk_fluent._artifacts import A

        agent = (
            Agent("writer")
            .instruct("Write.")
            .writes("report")
            .artifacts(
                A.publish("report.md", from_key="report"),
                A.save("backup.txt", content="static"),
            )
        )
        assert agent is not None
        assert len(agent._lists.get("_artifact_transforms", [])) == 2


class TestMultiArtifactOps:
    """A.publish_many, A.snapshot_many — batch operations."""

    def test_publish_many_returns_tuple(self):
        from adk_fluent import A

        result = A.publish_many(
            ("report.md", "report"),
            ("data.json", "raw_data"),
        )
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_publish_many_each_is_atransform(self):
        from adk_fluent import A
        from adk_fluent._artifacts import ATransform

        result = A.publish_many(
            ("report.md", "report"),
            ("data.json", "raw_data"),
        )
        for t in result:
            assert isinstance(t, ATransform)
            assert t._op == "publish"

    def test_publish_many_correct_keys(self):
        from adk_fluent import A

        r, d = A.publish_many(
            ("report.md", "report"),
            ("data.json", "raw_data"),
        )
        assert r._filename == "report.md"
        assert r._from_key == "report"
        assert d._filename == "data.json"
        assert d._from_key == "raw_data"

    def test_snapshot_many_returns_tuple(self):
        from adk_fluent import A

        result = A.snapshot_many(
            ("report.md", "report_text"),
            ("data.json", "raw_data"),
        )
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_snapshot_many_each_is_atransform(self):
        from adk_fluent import A
        from adk_fluent._artifacts import ATransform

        result = A.snapshot_many(
            ("report.md", "report_text"),
            ("data.json", "raw_data"),
        )
        for t in result:
            assert isinstance(t, ATransform)
            assert t._op == "snapshot"

    def test_snapshot_many_correct_keys(self):
        from adk_fluent import A

        r, d = A.snapshot_many(
            ("report.md", "report_text"),
            ("data.json", "raw_data"),
        )
        assert r._filename == "report.md"
        assert r._into_key == "report_text"
        assert d._filename == "data.json"
        assert d._into_key == "raw_data"

    def test_publish_many_with_artifacts_builder(self):
        """publish_many result works with .artifacts() via unpacking."""
        from adk_fluent import A, Agent

        transforms = A.publish_many(
            ("report.md", "report"),
            ("data.json", "raw_data"),
        )
        agent = Agent("writer").artifacts(*transforms)
        assert len(agent._lists.get("_artifact_transforms", [])) == 2


class TestEndToEnd:
    def test_full_pipeline_builds(self):
        """End-to-end: pipeline with A operations builds without error."""
        from adk_fluent import Agent
        from adk_fluent._artifacts import A

        pipeline = (
            Agent("researcher").model("gemini-2.5-flash").instruct("Research the topic.").writes("findings")
            >> A.publish("findings.md", from_key="findings")
            >> A.snapshot("findings.md", into_key="source")
            >> Agent("writer").model("gemini-2.5-flash").instruct("Write report from {source}.").writes("report")
            >> A.publish("report.md", from_key="report")
        )
        app = pipeline.build()
        assert app is not None

    def test_full_pipeline_contract_check(self):
        """Contract checker validates artifact flow correctly."""
        from adk_fluent import Agent
        from adk_fluent._artifacts import A
        from adk_fluent.testing.contracts import check_contracts

        pipeline = (
            Agent("researcher").instruct("Research.").writes("findings")
            >> A.publish("findings.md", from_key="findings")
            >> A.snapshot("findings.md", into_key="source")
            >> Agent("writer").instruct("Write.")
        )
        ir = pipeline.to_ir()
        issues = check_contracts(ir)
        artifact_errors = [
            i
            for i in issues
            if isinstance(i, dict) and "artifact" in i.get("message", "").lower() and i["level"] == "error"
        ]
        assert len(artifact_errors) == 0


class TestForLlm:
    """A.for_llm — CTransform-compatible artifact context injection."""

    def test_for_llm_returns_ctransform(self):
        from adk_fluent import A
        from adk_fluent._context import CTransform

        result = A.for_llm("report.md")
        assert isinstance(result, CTransform)

    def test_for_llm_include_contents_none(self):
        from adk_fluent import A

        result = A.for_llm("report.md")
        assert result.include_contents == "none"

    def test_for_llm_has_instruction_provider(self):
        from adk_fluent import A

        result = A.for_llm("report.md")
        assert result.instruction_provider is not None
        assert callable(result.instruction_provider)

    def test_for_llm_filename_stored(self):
        from adk_fluent import A

        result = A.for_llm("report.md")
        assert result._filename == "report.md"

    def test_for_llm_scope_default(self):
        from adk_fluent import A

        result = A.for_llm("report.md")
        assert result._scope == "session"

    def test_for_llm_scope_user(self):
        from adk_fluent import A

        result = A.for_llm("report.md", scope="user")
        assert result._scope == "user"

    def test_for_llm_composes_with_c_union(self):
        """A.for_llm() can be combined with C blocks via |."""
        from adk_fluent import A, C
        from adk_fluent._context import CTransform

        combined = C.from_state("topic") | A.for_llm("report.md")
        assert isinstance(combined, CTransform)


class TestToolFactories:
    """A.tool.save, A.tool.load, A.tool.list, A.tool.version — FunctionTool generation."""

    def test_tool_save_creates_function_tool(self):
        from google.adk.tools import FunctionTool

        from adk_fluent import A

        tool = A.tool.save("save_report", mime=A.mime.markdown)
        assert isinstance(tool, FunctionTool)

    def test_tool_save_name(self):
        from adk_fluent import A

        tool = A.tool.save("save_report")
        assert tool.name == "save_report"

    def test_tool_save_with_allowed(self):
        from adk_fluent import A

        tool = A.tool.save("save_file", allowed=["report.md", "summary.txt"])
        assert tool.name == "save_file"

    def test_tool_load_creates_function_tool(self):
        from google.adk.tools import FunctionTool

        from adk_fluent import A

        tool = A.tool.load("read_file")
        assert isinstance(tool, FunctionTool)

    def test_tool_list_creates_function_tool(self):
        from google.adk.tools import FunctionTool

        from adk_fluent import A

        tool = A.tool.list("list_files")
        assert isinstance(tool, FunctionTool)

    def test_tool_version_creates_function_tool(self):
        from google.adk.tools import FunctionTool

        from adk_fluent import A

        tool = A.tool.version("check_version")
        assert isinstance(tool, FunctionTool)


class TestContractChecking:
    def test_snapshot_without_upstream_publish_is_error(self):
        from adk_fluent import Agent
        from adk_fluent._artifacts import A

        pipeline = (
            Agent("writer").instruct("Write.") >> A.snapshot("report.md", into_key="text")  # no upstream publish!
        )
        ir = pipeline.to_ir()
        from adk_fluent.testing.contracts import check_contracts

        issues = check_contracts(ir)
        artifact_issues = [i for i in issues if isinstance(i, dict) and "artifact" in i.get("message", "").lower()]
        assert any(i["level"] == "error" for i in artifact_issues)

    def test_snapshot_with_upstream_publish_is_clean(self):
        from adk_fluent import Agent
        from adk_fluent._artifacts import A

        pipeline = (
            Agent("writer").instruct("Write.").writes("report")
            >> A.publish("report.md", from_key="report")
            >> A.snapshot("report.md", into_key="text")
        )
        ir = pipeline.to_ir()
        from adk_fluent.testing.contracts import check_contracts

        issues = check_contracts(ir)
        artifact_errors = [
            i
            for i in issues
            if isinstance(i, dict) and "artifact" in i.get("message", "").lower() and i["level"] == "error"
        ]
        assert len(artifact_errors) == 0

    def test_publish_without_upstream_state_key_is_error(self):
        from adk_fluent import Agent
        from adk_fluent._artifacts import A

        pipeline = (
            Agent("writer").instruct("Write.")
            >> A.publish("report.md", from_key="report")  # writer has no save_as("report")!
        )
        ir = pipeline.to_ir()
        from adk_fluent.testing.contracts import check_contracts

        issues = check_contracts(ir)
        state_issues = [
            i
            for i in issues
            if isinstance(i, dict) and "state key" in i.get("message", "").lower() and i["level"] == "error"
        ]
        assert len(state_issues) > 0


class TestArtifactSchema:
    """ArtifactSchema with Produces/Consumes annotations."""

    def test_produces_annotation(self):
        from adk_fluent._artifact_schema import Produces

        p = Produces("report.md", mime="text/markdown")
        assert p.filename == "report.md"
        assert p.mime == "text/markdown"
        assert p.scope == "session"

    def test_consumes_annotation(self):
        from adk_fluent._artifact_schema import Consumes

        c = Consumes("data.csv", mime="text/csv")
        assert c.filename == "data.csv"
        assert c.mime == "text/csv"

    def test_schema_definition(self):
        from adk_fluent._artifact_schema import ArtifactSchema, Consumes, Produces

        class ResearchArtifacts(ArtifactSchema):
            findings: str = Produces("findings.json", mime="application/json")
            report: str = Produces("report.md", mime="text/markdown")
            source: str = Consumes("raw_data.csv", mime="text/csv")

        assert len(ResearchArtifacts._field_list) == 3

    def test_schema_produces_fields(self):
        from adk_fluent._artifact_schema import ArtifactSchema, Consumes, Produces

        class Artifacts(ArtifactSchema):
            report: str = Produces("report.md")
            source: str = Consumes("data.csv")

        produces = Artifacts.produces_fields()
        assert len(produces) == 1
        assert produces[0].filename == "report.md"

    def test_schema_consumes_fields(self):
        from adk_fluent._artifact_schema import ArtifactSchema, Consumes, Produces

        class Artifacts(ArtifactSchema):
            report: str = Produces("report.md")
            source: str = Consumes("data.csv")

        consumes = Artifacts.consumes_fields()
        assert len(consumes) == 1
        assert consumes[0].filename == "data.csv"

    def test_schema_produced_filenames(self):
        from adk_fluent._artifact_schema import ArtifactSchema, Produces

        class Artifacts(ArtifactSchema):
            report: str = Produces("report.md")
            config: str = Produces("config.json")

        assert Artifacts.produced_filenames() == frozenset({"report.md", "config.json"})

    def test_schema_consumed_filenames(self):
        from adk_fluent._artifact_schema import ArtifactSchema, Consumes

        class Artifacts(ArtifactSchema):
            source: str = Consumes("data.csv")

        assert Artifacts.consumed_filenames() == frozenset({"data.csv"})


class TestPass16:
    """Pass 16: ArtifactSchema contract validation."""

    def test_schema_consumes_without_producer_is_error(self):
        from adk_fluent import Agent
        from adk_fluent._artifact_schema import ArtifactSchema, Consumes
        from adk_fluent.testing.contracts import check_contracts

        class NeedsData(ArtifactSchema):
            source: str = Consumes("data.csv")

        pipeline = Agent("reader").artifact_schema(NeedsData) >> Agent("writer")
        ir = pipeline.to_ir()
        issues = check_contracts(ir)
        errors = [i for i in issues if i["level"] == "error" and "data.csv" in i["message"]]
        assert len(errors) >= 1

    def test_schema_consumes_with_producer_is_clean(self):
        from adk_fluent import A, Agent
        from adk_fluent._artifact_schema import ArtifactSchema, Consumes
        from adk_fluent.testing.contracts import check_contracts

        class NeedsData(ArtifactSchema):
            source: str = Consumes("data.csv")

        pipeline = Agent("writer") >> A.save("data.csv", content="a,b") >> Agent("reader").artifact_schema(NeedsData)
        ir = pipeline.to_ir()
        issues = check_contracts(ir)
        schema_errors = [i for i in issues if i["level"] == "error" and "data.csv" in i["message"]]
        assert len(schema_errors) == 0

    def test_schema_produces_promotes_artifacts(self):
        from adk_fluent import Agent
        from adk_fluent._artifact_schema import ArtifactSchema, Consumes, Produces
        from adk_fluent.testing.contracts import check_contracts

        class ProducerSchema(ArtifactSchema):
            report: str = Produces("report.md")

        class ConsumerSchema(ArtifactSchema):
            source: str = Consumes("report.md")

        pipeline = Agent("writer").artifact_schema(ProducerSchema) >> Agent("reader").artifact_schema(ConsumerSchema)
        ir = pipeline.to_ir()
        issues = check_contracts(ir)
        schema_errors = [i for i in issues if i["level"] == "error" and "report.md" in i["message"]]
        assert len(schema_errors) == 0

    def test_schema_mime_mismatch_is_warning(self):
        from adk_fluent import Agent
        from adk_fluent._artifact_schema import ArtifactSchema, Consumes, Produces
        from adk_fluent.testing.contracts import check_contracts

        class ProducerSchema(ArtifactSchema):
            report: str = Produces("report.md", mime="text/markdown")

        class ConsumerSchema(ArtifactSchema):
            source: str = Consumes("report.md", mime="application/json")

        pipeline = Agent("writer").artifact_schema(ProducerSchema) >> Agent("reader").artifact_schema(ConsumerSchema)
        ir = pipeline.to_ir()
        issues = check_contracts(ir)
        warnings = [i for i in issues if i["level"] == "warning" and "MIME" in i["message"]]
        assert len(warnings) >= 1


class TestVisualization:
    """Artifact edges in Mermaid visualization."""

    def test_artifact_node_rendered(self):
        from adk_fluent import A, Agent
        from adk_fluent.viz import ir_to_mermaid

        pipeline = Agent("writer") >> A.publish("report.md", from_key="output") >> Agent("reader")
        ir = pipeline.to_ir()
        mermaid = ir_to_mermaid(ir)
        assert "publish" in mermaid.lower() or "report" in mermaid.lower()

    def test_artifact_node_shape(self):
        """ArtifactNode should have a distinct shape (hexagon)."""
        from adk_fluent import A, Agent
        from adk_fluent.viz import ir_to_mermaid

        pipeline = Agent("writer") >> A.publish("report.md", from_key="output")
        ir = pipeline.to_ir()
        mermaid = ir_to_mermaid(ir)
        # Hexagon shape uses {{...}} syntax in Mermaid
        assert "artifact" in mermaid.lower()

    def test_artifact_data_flow_edges(self):
        """Artifact produces/consumes should generate data flow edges."""
        from adk_fluent import A, Agent
        from adk_fluent.viz import ir_to_mermaid

        pipeline = (
            Agent("writer").writes("output")
            >> A.publish("report.md", from_key="output")
            >> A.snapshot("report.md", into_key="text")
            >> Agent("reader")
        )
        ir = pipeline.to_ir()
        mermaid = ir_to_mermaid(ir, show_data_flow=True)
        # Should show artifact flow edges
        assert "report.md" in mermaid


class TestPhase2Exports:
    """Phase 2+3 exports are importable."""

    def test_artifact_schema_importable(self):
        from adk_fluent.prelude import ArtifactSchema

        assert ArtifactSchema is not None

    def test_produces_importable(self):
        from adk_fluent.prelude import Produces

        assert Produces is not None

    def test_consumes_importable(self):
        from adk_fluent.prelude import Consumes

        assert Consumes is not None

    def test_for_llm_on_a(self):
        from adk_fluent import A

        assert hasattr(A, "for_llm")

    def test_tool_on_a(self):
        from adk_fluent import A

        assert hasattr(A, "tool")

    def test_content_transforms_on_a(self):
        from adk_fluent import A

        assert hasattr(A, "as_json")
        assert hasattr(A, "as_csv")
        assert hasattr(A, "as_text")
        assert hasattr(A, "from_json")
        assert hasattr(A, "from_csv")
        assert hasattr(A, "from_markdown")

    def test_batch_ops_on_a(self):
        from adk_fluent import A

        assert hasattr(A, "publish_many")
        assert hasattr(A, "snapshot_many")


class TestPhase2E2E:
    """End-to-end integration tests for Phase 2+3."""

    def test_snapshot_then_as_json_pipeline(self):
        """A.snapshot >> A.as_json composes in a pipeline."""
        from adk_fluent import A, Agent

        pipeline = (
            Agent("writer") >> A.snapshot("data.json", into_key="data") >> A.as_json("data") >> Agent("processor")
        )
        ir = pipeline.to_ir()
        from adk_fluent._ir_generated import SequenceNode

        assert isinstance(ir, SequenceNode)

    def test_from_json_then_publish_pipeline(self):
        """A.from_json >> A.publish composes in a pipeline."""
        from adk_fluent import A, Agent

        pipeline = Agent("processor") >> A.from_json("config") >> A.publish("config.json", from_key="config")
        ir = pipeline.to_ir()
        from adk_fluent._ir_generated import SequenceNode

        assert isinstance(ir, SequenceNode)

    def test_full_roundtrip_pipeline(self):
        """Full pipeline: agent >> snapshot >> transform >> agent >> serialize >> publish."""
        from adk_fluent import A, Agent

        pipeline = (
            Agent("loader")
            >> A.snapshot("data.csv", into_key="rows")
            >> A.as_csv("rows")
            >> Agent("processor")
            >> A.from_json("result")
            >> A.publish("result.json", from_key="result")
        )
        ir = pipeline.to_ir()
        assert ir is not None

    def test_schema_with_tools_and_transforms(self):
        """Agent with artifact_schema, tools, and pipeline transforms all compose."""
        from adk_fluent import A, Agent
        from adk_fluent._artifact_schema import ArtifactSchema, Consumes, Produces

        class WorkerArtifacts(ArtifactSchema):
            result: str = Produces("result.json", mime="application/json")
            source: str = Consumes("input.csv", mime="text/csv")

        pipeline = Agent("loader").artifacts(A.save("input.csv", content="a,b\n1,2")) >> Agent(
            "worker"
        ).artifact_schema(WorkerArtifacts).tool(A.tool.load("read_input")).tool(
            A.tool.save("save_result", allowed=["result.json"])
        )
        ir = pipeline.to_ir()
        from adk_fluent._ir_generated import SequenceNode

        assert isinstance(ir, SequenceNode)
        # Worker agent should have artifact_schema set on its IR node
        from adk_fluent._ir_generated import AgentNode

        agent_nodes = [c for c in ir.children if isinstance(c, AgentNode)]
        worker_node = [n for n in agent_nodes if n.name == "worker"][0]
        assert worker_node.artifact_schema is WorkerArtifacts

    def test_contract_checking_full_pipeline(self):
        """Contract checker validates both Pass 15 and Pass 16 in same pipeline."""
        from adk_fluent import A, Agent
        from adk_fluent._artifact_schema import ArtifactSchema, Consumes, Produces
        from adk_fluent.testing.contracts import check_contracts

        class ProducerSchema(ArtifactSchema):
            report: str = Produces("report.md")

        class ConsumerSchema(ArtifactSchema):
            source: str = Consumes("report.md")

        pipeline = (
            Agent("writer").artifact_schema(ProducerSchema)
            >> A.publish("report.md", from_key="output")
            >> Agent("reader").artifact_schema(ConsumerSchema)
            >> A.snapshot("report.md", into_key="text")
            >> Agent("final")
        )
        ir = pipeline.to_ir()
        issues = check_contracts(ir)
        # No artifact-related errors (Pass 15 handles A.publish/snapshot, Pass 16 handles schemas)
        artifact_errors = [i for i in issues if i["level"] == "error" and "artifact" in i["message"].lower()]
        assert len(artifact_errors) == 0
