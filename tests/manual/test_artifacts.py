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
