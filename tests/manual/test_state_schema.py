"""Tests for Phase E — StateSchema, CapturedBy, Scoped, typed contract checking.

Tests the StateSchema base class, field introspection, scope prefixes,
CapturedBy provenance, typed contract checking, and IDE autocomplete support.
"""

from __future__ import annotations

from typing import Annotated

import pytest

from adk_fluent._state_schema import (
    CapturedBy,
    Scoped,
    StateSchema,
    check_state_schema_contracts,
)

# ======================================================================
# Test schemas
# ======================================================================


class BillingState(StateSchema):
    intent: str
    confidence: float
    user_message: Annotated[str, CapturedBy("C.capture")]
    ticket_id: str | None = None
    user_tier: Annotated[str, Scoped("user")]


class SimpleState(StateSchema):
    name: str
    count: int = 0


class EmptyState(StateSchema):
    pass


class TempState(StateSchema):
    scratch: Annotated[str, Scoped("temp")]
    cache: Annotated[int, Scoped("temp")] = 0


class InheritedState(BillingState):
    extra_field: str = "default"


# ======================================================================
# CapturedBy annotation
# ======================================================================


class TestCapturedBy:
    """CapturedBy annotation stores provenance metadata."""

    def test_create(self):
        cb = CapturedBy("C.capture")
        assert cb.source == "C.capture"

    def test_repr(self):
        cb = CapturedBy("S.capture")
        assert "S.capture" in repr(cb)

    def test_frozen(self):
        cb = CapturedBy("C.capture")
        with pytest.raises(AttributeError):
            cb.source = "other"


# ======================================================================
# Scoped annotation
# ======================================================================


class TestScoped:
    """Scoped annotation declares state scope."""

    def test_valid_scopes(self):
        for scope in ("session", "app", "user", "temp"):
            s = Scoped(scope)
            assert s.scope == scope

    def test_invalid_scope(self):
        with pytest.raises(ValueError, match="Invalid scope"):
            Scoped("global")

    def test_repr(self):
        s = Scoped("user")
        assert "user" in repr(s)

    def test_frozen(self):
        s = Scoped("app")
        with pytest.raises(AttributeError):
            s.scope = "user"


# ======================================================================
# StateSchema — field introspection
# ======================================================================


class TestStateSchemaFields:
    """StateSchema introspects type hints into structured field metadata."""

    def test_billing_field_count(self):
        assert len(BillingState._fields) == 5

    def test_simple_field_count(self):
        assert len(SimpleState._fields) == 2

    def test_empty_schema(self):
        assert len(EmptyState._fields) == 0

    def test_field_names(self):
        names = set(BillingState._fields.keys())
        assert names == {"intent", "confidence", "user_message", "ticket_id", "user_tier"}

    def test_field_scope_default(self):
        f = BillingState._fields["intent"]
        assert f.scope == "session"
        assert f.full_key == "intent"

    def test_field_scope_user(self):
        f = BillingState._fields["user_tier"]
        assert f.scope == "user"
        assert f.full_key == "user:user_tier"

    def test_field_captured_by(self):
        f = BillingState._fields["user_message"]
        assert f.captured_by == "C.capture"

    def test_field_no_captured_by(self):
        f = BillingState._fields["intent"]
        assert f.captured_by is None

    def test_field_required(self):
        f = BillingState._fields["intent"]
        assert f.required is True

    def test_field_optional(self):
        f = BillingState._fields["ticket_id"]
        assert f.required is False

    def test_field_default_value(self):
        f = SimpleState._fields["count"]
        assert f.default == 0

    def test_temp_scope(self):
        f = TempState._fields["scratch"]
        assert f.scope == "temp"
        assert f.full_key == "temp:scratch"


# ======================================================================
# StateSchema — class methods
# ======================================================================


class TestStateSchemaClassMethods:
    """StateSchema class methods for key management."""

    def test_keys(self):
        keys = BillingState.keys()
        assert "intent" in keys
        assert "confidence" in keys
        assert "user:user_tier" in keys
        assert "ticket_id" in keys

    def test_required_keys(self):
        req = BillingState.required_keys()
        assert "intent" in req
        assert "confidence" in req
        # user_tier is required (no default)
        assert "user:user_tier" in req
        # ticket_id is NOT required (has default None)
        assert "ticket_id" not in req

    def test_scoped_keys(self):
        scoped = BillingState.scoped_keys()
        assert "session" in scoped
        assert "user" in scoped
        assert "user:user_tier" in scoped["user"]

    def test_field_types(self):
        types = BillingState.field_types()
        assert types["intent"] is str
        assert types["confidence"] is float

    def test_captured_by_map(self):
        cmap = BillingState.captured_by_map()
        assert "user_message" in cmap
        assert cmap["user_message"] == "C.capture"

    def test_model_fields_compat(self):
        fields = BillingState.model_fields()
        assert "intent" in fields
        assert hasattr(fields["intent"], "name")


# ======================================================================
# StateSchema — IDE autocomplete support
# ======================================================================


class TestStateSchemaAutocomplete:
    """StateSchema provides IDE-friendly discovery."""

    def test_state_keys(self):
        keys = BillingState.state_keys()
        assert "intent" in keys
        assert "user_tier" in keys
        # Each value is a StateKey
        sk = keys["intent"]
        assert sk.key == "intent"
        assert sk.scope == "session"

    def test_state_keys_scoped(self):
        keys = BillingState.state_keys()
        sk = keys["user_tier"]
        assert sk.key == "user:user_tier"
        assert sk.scope == "user"

    def test_template_vars(self):
        tv = BillingState.template_vars()
        assert "{intent}" in tv
        assert "{confidence}" in tv
        assert "{user_tier}" in tv

    def test_dir_includes_fields(self):
        d = dir(BillingState)
        assert "intent" in d
        assert "confidence" in d
        assert "user_tier" in d

    def test_repr(self):
        r = repr(BillingState())
        assert "BillingState" in r
        assert "intent" in r


# ======================================================================
# StateSchema — inheritance
# ======================================================================


class TestStateSchemaInheritance:
    """StateSchema supports inheritance for extending schemas."""

    def test_inherited_fields(self):
        # Note: with metaclass, inherited fields depend on __annotations__
        assert "extra_field" in InheritedState._fields


# ======================================================================
# Typed contract checking
# ======================================================================


class TestTypedContractChecking:
    """check_state_schema_contracts validates state usage across a pipeline."""

    def _make_agent_node(self, name, produces=None, consumes=None, output_key=None):
        """Helper: create a minimal AgentNode-like object."""
        return type(
            "FakeAgent",
            (),
            {
                "name": name,
                "produces_type": produces,
                "consumes_type": consumes,
                "output_key": output_key,
                "instruction": "",
                "include_contents": "default",
            },
        )()

    def _make_sequence(self, children):
        """Helper: create a minimal SequenceNode-like object."""
        from adk_fluent._ir_generated import SequenceNode

        return SequenceNode(name="test_seq", children=tuple(children))

    def test_no_issues_when_produces_covers_consumes(self):
        class ProducerState(StateSchema):
            intent: str
            confidence: float

        class ConsumerState(StateSchema):
            intent: str

        seq = self._make_sequence(
            [
                self._make_agent_node("producer", produces=ProducerState, output_key="intent"),
                self._make_agent_node("consumer", consumes=ConsumerState),
            ]
        )
        issues = check_state_schema_contracts(seq)
        errors = [i for i in issues if i["level"] == "error"]
        assert len(errors) == 0

    def test_missing_required_field(self):
        class ConsumerState(StateSchema):
            intent: str
            missing_field: str

        seq = self._make_sequence(
            [
                self._make_agent_node("producer"),
                self._make_agent_node("consumer", consumes=ConsumerState),
            ]
        )
        issues = check_state_schema_contracts(seq)
        errors = [i for i in issues if i["level"] == "error"]
        assert len(errors) >= 1
        assert any("missing_field" in e["message"] for e in errors)

    def test_captured_by_provenance_warning(self):
        class WithCapture(StateSchema):
            user_msg: Annotated[str, CapturedBy("C.capture")]

        seq = self._make_sequence(
            [
                self._make_agent_node("agent", produces=WithCapture),
            ]
        )
        issues = check_state_schema_contracts(seq)
        # Should warn about missing S.capture()
        info = [i for i in issues if i["level"] == "info"]
        assert any("CapturedBy" in i["message"] for i in info)

    def test_scope_mismatch_info(self):
        class ScopedState(StateSchema):
            user_pref: Annotated[str, Scoped("user")]

        seq = self._make_sequence(
            [
                self._make_agent_node("agent", produces=ScopedState, output_key="user_pref"),
            ]
        )
        issues = check_state_schema_contracts(seq)
        info = [i for i in issues if i["level"] == "info"]
        assert any("scope" in i["message"].lower() for i in info)

    def test_empty_sequence(self):
        from adk_fluent._ir_generated import SequenceNode

        seq = SequenceNode(name="empty", children=())
        issues = check_state_schema_contracts(seq)
        assert issues == []

    def test_non_sequence_returns_empty(self):
        from adk_fluent._ir_generated import ParallelNode

        par = ParallelNode(name="par", children=())
        issues = check_state_schema_contracts(par)
        assert issues == []
