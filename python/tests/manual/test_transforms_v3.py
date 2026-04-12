"""Tests for v3-corrected state transform semantics with scope awareness."""

from adk_fluent._transforms import S, StateDelta, StateReplacement

# --- Type discrimination ---


def test_pick_returns_state_replacement():
    fn = S.pick("a", "b")
    result = fn({"a": 1, "b": 2, "c": 3})
    assert isinstance(result, StateReplacement)
    assert result.new_state == {"a": 1, "b": 2}


def test_drop_returns_state_replacement():
    fn = S.drop("c")
    result = fn({"a": 1, "b": 2, "c": 3})
    assert isinstance(result, StateReplacement)
    assert result.new_state == {"a": 1, "b": 2}


def test_rename_returns_state_replacement():
    fn = S.rename(a="alpha")
    result = fn({"a": 1, "b": 2})
    assert isinstance(result, StateReplacement)
    assert result.new_state == {"alpha": 1, "b": 2}


def test_default_returns_state_delta():
    fn = S.default(x=10)
    result = fn({"a": 1})
    assert isinstance(result, StateDelta)
    assert result.updates == {"x": 10}


def test_merge_returns_state_delta():
    fn = S.merge("a", "b", into="combined")
    result = fn({"a": "hello", "b": "world"})
    assert isinstance(result, StateDelta)
    assert "combined" in result.updates


def test_transform_returns_state_delta():
    fn = S.transform("x", str.upper)
    result = fn({"x": "hello"})
    assert isinstance(result, StateDelta)
    assert result.updates == {"x": "HELLO"}


def test_compute_returns_state_delta():
    fn = S.compute(total=lambda s: s["a"] + s["b"])
    result = fn({"a": 1, "b": 2})
    assert isinstance(result, StateDelta)
    assert result.updates == {"total": 3}


def test_guard_returns_state_delta():
    fn = S.guard(lambda s: "key" in s, "Missing key")
    result = fn({"key": "val"})
    assert isinstance(result, StateDelta)
    assert result.updates == {}


def test_log_returns_state_delta():
    fn = S.log("a")
    result = fn({"a": 1})
    assert isinstance(result, StateDelta)
    assert result.updates == {}


def test_set_returns_state_delta():
    fn = S.set(x=10, y=20)
    result = fn({})
    assert isinstance(result, StateDelta)
    assert result.updates == {"x": 10, "y": 20}


# --- Scope awareness ---


def test_pick_preserves_prefixed_keys_in_input():
    fn = S.pick("a")
    result = fn({"a": 1, "b": 2, "app:setting": "x", "user:pref": "y", "temp:scratch": "z"})
    assert isinstance(result, StateReplacement)
    assert result.new_state == {"a": 1}


def test_drop_excludes_only_named_session_keys():
    fn = S.drop("b")
    result = fn({"a": 1, "b": 2, "app:setting": "x"})
    assert isinstance(result, StateReplacement)
    assert result.new_state == {"a": 1}


def test_rename_ignores_prefixed_keys():
    fn = S.rename(a="alpha")
    result = fn({"a": 1, "b": 2, "app:x": 3})
    assert isinstance(result, StateReplacement)
    assert result.new_state == {"alpha": 1, "b": 2}
    assert "app:x" not in result.new_state  # Prefixed keys handled by FnAgent, not transform


# --- Backward compat ---


def test_plain_dict_function_still_works():
    fn = lambda state: {"new_key": state["a"] + 1}
    result = fn({"a": 1})
    assert isinstance(result, dict)
    assert not isinstance(result, StateDelta | StateReplacement)
