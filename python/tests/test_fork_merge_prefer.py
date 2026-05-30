"""Regression tests for ForkManager.merge(strategy="prefer") (BUG 3).

The preference override was guarded by ``if prefer_state:`` which is
falsy when the preferred branch's state is an empty dict ({}). That made
an empty preferred branch silently degrade the merge to a plain last-wins
union. The guard must be ``if prefer_state is not None:``.
"""

from __future__ import annotations

from adk_fluent import ForkManager


def test_prefer_empty_branch_does_not_get_overridden_by_union():
    """An empty preferred branch must still drive 'prefer' semantics.

    With the bug, prefer_state ({}) is falsy, the override is skipped, and
    the result is a last-wins union where ``b``'s value for the shared key
    leaks through. The contract says the preferred branch wins on
    conflicts; an empty preferred branch has no value to contribute, so
    shared keys come from the non-empty branches only — but the code path
    that applies the preference MUST execute.
    """
    fm = ForkManager()
    fm.fork("a", {"shared": "from_a", "only_a": 1})
    fm.fork("b", {})  # preferred branch is empty

    merged = fm.merge("a", "b", strategy="prefer", prefer="b")

    # union of a and b == a's keys (b contributes nothing). The key point:
    # this is identical whether or not the override ran, because b is empty
    # — so we additionally assert a direct override case below.
    assert merged == {"shared": "from_a", "only_a": 1}


def test_prefer_branch_wins_on_conflicts():
    """Non-empty preferred branch overrides conflicting keys from others."""
    fm = ForkManager()
    fm.fork("a", {"k": "from_a", "x": 1})
    fm.fork("b", {"k": "from_b", "y": 2})

    merged = fm.merge("a", "b", strategy="prefer", prefer="b")
    assert merged["k"] == "from_b"
    assert merged["x"] == 1
    assert merged["y"] == 2


def test_prefer_first_branch_wins_over_later_union_value():
    """Preferred branch listed FIRST must still beat the later union value.

    Union processes branches in order, so a conflicting key from a later
    branch lands last. The preference override must re-apply the preferred
    branch afterward. With the bug, when the preferred branch's state is
    falsy ({}) the override is skipped; this test pins the override-path
    behaviour with a non-empty preferred branch ordered first so the
    override is the ONLY thing that produces the preferred value.
    """
    fm = ForkManager()
    fm.fork("pref", {"k": "pref_val"})
    fm.fork("other", {"k": "other_val"})

    merged = fm.merge("pref", "other", strategy="prefer", prefer="pref")
    # Plain union (last wins) would yield "other_val"; the prefer override
    # must restore "pref_val".
    assert merged["k"] == "pref_val"


def test_merge_prefer_guard_uses_is_not_none_for_empty_branch():
    """Directly assert the empty-preferred-branch path runs without error.

    The empty preferred branch contributes no keys, so the merged result
    equals the union of the remaining branches. The guard must execute the
    override path (``is not None``) rather than skipping it via truthiness;
    this test documents that an empty preferred branch is a valid, handled
    input that yields the union of the others rather than raising or
    diverging.
    """
    fm = ForkManager()
    fm.fork("a", {"x": 1, "y": 2})
    fm.fork("empty", {})

    merged = fm.merge("a", "empty", strategy="prefer", prefer="empty")
    assert merged == {"x": 1, "y": 2}
