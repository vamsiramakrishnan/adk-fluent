"""Tests for A module — artifact composition."""

from __future__ import annotations


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


class TestWhen:
    def test_when_wraps_atransform(self):
        from adk_fluent._artifacts import A, ATransform

        inner = A.publish("report.md", from_key="report")
        at = A.when("has_report", inner)
        assert isinstance(at, ATransform)
        assert at._op == "publish"
        assert at._filename == "report.md"
