"""Tests for NamespaceSpec protocol conformance across all six namespace types.

Validates that STransform, CTransform, PTransform, ATransform, MComposite,
and TComposite all satisfy the NamespaceSpec runtime-checkable protocol,
and that merge_keysets() and fingerprint_spec() work correctly.
"""

import pytest

from adk_fluent._artifacts import A
from adk_fluent._context import C, CComposite, CTransform
from adk_fluent._middleware import M, MComposite
from adk_fluent._namespace_protocol import (
    NamespaceSpec,
    fingerprint_spec,
    merge_keysets,
)
from adk_fluent._prompt import P, PComposite, PTransform
from adk_fluent._tools import T
from adk_fluent._transforms import S

# ── Fixtures: one spec per namespace ───────────────────────────────────


@pytest.fixture
def s_spec():
    return S.pick("x", "y")


@pytest.fixture
def c_spec():
    return C.window(n=5)


@pytest.fixture
def p_spec():
    return P.role("helper")


@pytest.fixture
def a_spec():
    return A.publish("report.md", from_key="text")


@pytest.fixture
def m_spec():
    return M.retry(3)


@pytest.fixture
def t_spec():
    return T.google_search()


ALL_FIXTURES = ["s_spec", "c_spec", "p_spec", "a_spec", "m_spec", "t_spec"]

# Leaf types return (self,) from _as_list(). MComposite/TComposite are composites
# that wrap a list of items, so their _as_list() returns the items, not (self,).
LEAF_FIXTURES = ["s_spec", "c_spec", "p_spec", "a_spec"]
COMPOSITE_FIXTURES = ["m_spec", "t_spec"]


# ── Protocol conformance: isinstance checks ────────────────────────────


@pytest.mark.parametrize("fixture_name", ALL_FIXTURES)
def test_isinstance_namespace_spec(fixture_name, request):
    """Every namespace type should pass isinstance(obj, NamespaceSpec)."""
    spec = request.getfixturevalue(fixture_name)
    assert isinstance(spec, NamespaceSpec), f"{type(spec).__name__} does not satisfy NamespaceSpec protocol"


# ── Protocol property: _kind ───────────────────────────────────────────


@pytest.mark.parametrize("fixture_name", ALL_FIXTURES)
def test_kind_is_nonempty_string(fixture_name, request):
    """_kind should return a non-empty string."""
    spec = request.getfixturevalue(fixture_name)
    kind = spec._kind
    assert isinstance(kind, str)
    assert len(kind) > 0


def test_kind_discriminates_types(s_spec, p_spec, a_spec):
    """Different namespace types should produce different _kind tags."""
    kinds = {s_spec._kind, p_spec._kind, a_spec._kind}
    assert len(kinds) == 3


# ── Protocol method: _as_list() ────────────────────────────────────────


@pytest.mark.parametrize("fixture_name", ALL_FIXTURES)
def test_as_list_returns_tuple(fixture_name, request):
    """_as_list() should return a tuple."""
    spec = request.getfixturevalue(fixture_name)
    result = spec._as_list()
    assert isinstance(result, tuple)


@pytest.mark.parametrize("fixture_name", LEAF_FIXTURES)
def test_as_list_leaf_contains_self(fixture_name, request):
    """For leaf specs (S, C, P, A), _as_list() should return (self,)."""
    spec = request.getfixturevalue(fixture_name)
    result = spec._as_list()
    assert len(result) == 1
    assert result[0] is spec


@pytest.mark.parametrize("fixture_name", COMPOSITE_FIXTURES)
def test_as_list_composite_returns_items(fixture_name, request):
    """For composite specs (M, T), _as_list() returns contained items."""
    spec = request.getfixturevalue(fixture_name)
    result = spec._as_list()
    assert isinstance(result, tuple)
    assert len(result) >= 1


# ── Protocol properties: _reads_keys / _writes_keys ───────────────────


@pytest.mark.parametrize("fixture_name", ALL_FIXTURES)
def test_reads_keys_type(fixture_name, request):
    """_reads_keys should be frozenset[str] or None."""
    spec = request.getfixturevalue(fixture_name)
    rk = spec._reads_keys
    assert rk is None or isinstance(rk, frozenset)


@pytest.mark.parametrize("fixture_name", ALL_FIXTURES)
def test_writes_keys_type(fixture_name, request):
    """_writes_keys should be frozenset[str] or None."""
    spec = request.getfixturevalue(fixture_name)
    wk = spec._writes_keys
    assert wk is None or isinstance(wk, frozenset)


# ── ATransform-specific: protocol alignment with legacy fields ─────────


def test_atransform_kind_matches_op():
    """ATransform._kind should equal its _op field."""
    pub = A.publish("f.md", from_key="k")
    assert pub._kind == "publish"

    snap = A.snapshot("f.md", into_key="k")
    assert snap._kind == "snapshot"


def test_atransform_reads_keys_matches_consumes_state():
    """ATransform._reads_keys should equal _consumes_state."""
    pub = A.publish("f.md", from_key="text")
    assert pub._reads_keys == frozenset({"text"})
    assert pub._reads_keys == pub._consumes_state


def test_atransform_writes_keys_matches_produces_state():
    """ATransform._writes_keys should equal _produces_state."""
    snap = A.snapshot("f.md", into_key="data")
    assert snap._writes_keys == frozenset({"data"})
    assert snap._writes_keys == snap._produces_state


def test_atransform_as_list_returns_self():
    """ATransform._as_list() should return (self,)."""
    spec = A.publish("f.md", from_key="k")
    result = spec._as_list()
    assert result == (spec,)


# ── Specific key metadata semantics ────────────────────────────────────


def test_s_pick_writes_keys():
    """S.pick should declare which keys it writes."""
    spec = S.pick("a", "b")
    assert spec._writes_keys == frozenset({"a", "b"})


def test_s_set_writes_keys():
    """S.set should declare writes."""
    spec = S.set(x=1, y=2)
    assert spec._writes_keys == frozenset({"x", "y"})


def test_p_role_reads_nothing():
    """Static prompt blocks should read no state keys."""
    spec = P.role("helper")
    assert spec._reads_keys == frozenset()


def test_p_from_state_reads_keys():
    """PFromState should declare which state keys it reads."""
    spec = P.from_state("topic", "style")
    assert spec._reads_keys == frozenset({"topic", "style"})


def test_c_from_state_reads_keys():
    """CFromState should declare which state keys it reads."""
    spec = C.from_state("summary")
    rk = spec._reads_keys
    assert rk is not None
    assert "summary" in rk


def test_m_composite_opaque():
    """MComposite should be opaque (None) for reads and writes."""
    spec = M.retry(3)
    assert spec._reads_keys is None
    assert spec._writes_keys is None


def test_t_composite_opaque():
    """TComposite should be opaque (None) for reads and writes."""
    spec = T.google_search()
    assert spec._reads_keys is None
    assert spec._writes_keys is None


# ── Composite types: _as_list flattening ───────────────────────────────


def test_p_composite_flattens():
    """PComposite should flatten its children via _as_list()."""
    spec = P.role("helper") + P.task("do things")
    assert isinstance(spec, PComposite)
    items = spec._as_list()
    assert len(items) == 2
    assert all(isinstance(i, PTransform) for i in items)


def test_c_composite_flattens():
    """CComposite should flatten its children via _as_list()."""
    spec = C.window(n=5) + C.from_state("topic")
    assert isinstance(spec, CComposite)
    items = spec._as_list()
    assert len(items) == 2
    assert all(isinstance(i, CTransform) for i in items)


def test_m_composite_pipe_flattens():
    """MComposite | MComposite should flatten items."""
    spec = M.retry(3) | M.log()
    assert isinstance(spec, MComposite)
    items = spec._as_list()
    assert len(items) == 2


# ── merge_keysets() ────────────────────────────────────────────────────


def test_merge_keysets_both_concrete():
    """Union of two concrete keysets."""
    assert merge_keysets(frozenset({"a"}), frozenset({"b"})) == frozenset({"a", "b"})


def test_merge_keysets_left_none():
    """None (opaque) contaminates the result."""
    assert merge_keysets(None, frozenset({"b"})) is None


def test_merge_keysets_right_none():
    """None (opaque) contaminates the result."""
    assert merge_keysets(frozenset({"a"}), None) is None


def test_merge_keysets_both_none():
    """Both opaque -> opaque."""
    assert merge_keysets(None, None) is None


def test_merge_keysets_both_empty():
    """Empty sets merge to empty set."""
    assert merge_keysets(frozenset(), frozenset()) == frozenset()


# ── fingerprint_spec() ────────────────────────────────────────────────


def test_fingerprint_returns_hex_string():
    """fingerprint_spec should return a 16-char hex digest."""
    spec = P.role("helper")
    fp = fingerprint_spec(spec)
    assert isinstance(fp, str)
    assert len(fp) == 16
    int(fp, 16)  # valid hex


def test_fingerprint_deterministic():
    """Same spec should produce same fingerprint."""
    a = fingerprint_spec(P.role("helper"))
    b = fingerprint_spec(P.role("helper"))
    assert a == b


def test_fingerprint_structurally_different():
    """Structurally different specs should produce different fingerprints."""
    # Role vs Task — different _kind discriminators
    a = fingerprint_spec(P.role("helper"))
    b = fingerprint_spec(P.task("do things"))
    assert a != b


def test_fingerprint_works_across_namespaces():
    """fingerprint_spec should work on all namespace types without error."""
    specs = [
        S.pick("x"),
        C.window(n=5),
        P.role("helper"),
        A.publish("f.md", from_key="k"),
        M.retry(3),
        T.google_search(),
    ]
    fps = [fingerprint_spec(s) for s in specs]
    for fp in fps:
        assert len(fp) == 16
        int(fp, 16)


def test_fingerprint_composite_differs_from_leaf():
    """Composites should fingerprint differently from their leaves."""
    leaf = P.role("helper")
    composite = P.role("helper") + P.task("do things")
    assert fingerprint_spec(leaf) != fingerprint_spec(composite)


def test_fingerprint_atransform_different_ops():
    """Different ATransform ops should fingerprint differently."""
    pub = A.publish("f.md", from_key="text")
    snap = A.snapshot("f.md", into_key="data")
    assert fingerprint_spec(pub) != fingerprint_spec(snap)
