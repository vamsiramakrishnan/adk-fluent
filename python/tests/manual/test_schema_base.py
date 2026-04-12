"""Tests for the shared DeclarativeMetaclass and annotation types."""

from __future__ import annotations

from typing import Annotated

import pytest

from adk_fluent._schema_base import (
    Confirms,
    DeclarativeSchema,
    Param,
    Reads,
    Timeout,
    Writes,
)

# ── Annotation tests ──────────────────────────────────────────────


class TestAnnotations:
    def test_reads_defaults(self):
        r = Reads()
        assert r.scope == "session"

    def test_reads_custom_scope(self):
        r = Reads(scope="user")
        assert r.scope == "user"

    def test_writes_defaults(self):
        w = Writes()
        assert w.scope == "session"

    def test_param_defaults(self):
        p = Param()
        assert p.required is True

    def test_confirms_defaults(self):
        c = Confirms()
        assert c.message == ""

    def test_timeout_defaults(self):
        t = Timeout()
        assert t.seconds == 30.0

    def test_annotations_are_frozen(self):
        r = Reads()
        with pytest.raises(AttributeError):
            r.scope = "app"


# ── DeclarativeSchema tests ───────────────────────────────────────


class TestDeclarativeSchema:
    def test_empty_schema(self):
        class Empty(DeclarativeSchema):
            pass

        assert Empty._fields == {}
        assert Empty._field_list == ()

    def test_plain_fields(self):
        class Plain(DeclarativeSchema):
            name: str
            age: int

        assert len(Plain._fields) == 2
        assert "name" in Plain._fields
        assert Plain._fields["name"].type is str

    def test_annotated_reads(self):
        class S(DeclarativeSchema):
            query: Annotated[str, Reads()]

        f = S._fields["query"]
        assert f.type is str
        assert f.get_annotation(Reads) == Reads()
        assert f.get_annotation(Writes) is None

    def test_annotated_writes_with_scope(self):
        class S(DeclarativeSchema):
            count: Annotated[int, Writes(scope="temp")]

        f = S._fields["count"]
        w = f.get_annotation(Writes)
        assert w is not None
        assert w.scope == "temp"

    def test_multiple_annotations(self):
        class S(DeclarativeSchema):
            x: Annotated[str, Reads(), Timeout(10)]

        f = S._fields["x"]
        assert f.get_annotation(Reads) is not None
        assert f.get_annotation(Timeout) == Timeout(10)

    def test_default_values(self):
        class S(DeclarativeSchema):
            required: str
            optional: str = "fallback"

        assert S._fields["required"].required is True
        assert S._fields["optional"].required is False
        assert S._fields["optional"].default == "fallback"

    def test_private_fields_skipped(self):
        class S(DeclarativeSchema):
            _internal: str = "hidden"
            public: str

        assert "_internal" not in S._fields
        assert "public" in S._fields

    def test_dir_includes_field_names(self):
        class S(DeclarativeSchema):
            alpha: str
            beta: int

        d = dir(S)
        assert "alpha" in d
        assert "beta" in d

    def test_inheritance(self):
        class Base(DeclarativeSchema):
            a: str

        class Child(Base):
            b: int

        assert "a" in Child._fields
        assert "b" in Child._fields
