"""Tests for C — context engineering primitives and transforms."""

import pytest

from adk_fluent._context import (
    C,
    CBudget,
    CComposite,
    CExcludeAgents,
    CFromAgents,
    CFromState,
    CPipe,
    CPriority,
    CTemplate,
    CTransform,
    CUserOnly,
    CWindow,
    _compile_context_spec,
)


# ======================================================================
# Boundary primitives: C.none() and C.default()
# ======================================================================


class TestNone:
    def test_include_contents_is_none(self):
        t = C.none()
        assert t.include_contents == "none"

    def test_instruction_provider_is_none(self):
        t = C.none()
        assert t.instruction_provider is None

    def test_returns_ctransform(self):
        t = C.none()
        assert isinstance(t, CTransform)


class TestDefault:
    def test_include_contents_is_default(self):
        t = C.default()
        assert t.include_contents == "default"

    def test_instruction_provider_is_none(self):
        t = C.default()
        assert t.instruction_provider is None

    def test_returns_ctransform(self):
        t = C.default()
        assert isinstance(t, CTransform)


# ======================================================================
# CTransform protocol
# ======================================================================


class TestCTransformProtocol:
    def test_is_frozen(self):
        t = CTransform()
        with pytest.raises(AttributeError):
            t.include_contents = "none"

    def test_isinstance_check(self):
        assert isinstance(CTransform(), CTransform)
        assert isinstance(C.none(), CTransform)
        assert isinstance(C.default(), CTransform)

    def test_subclasses_are_ctransform(self):
        assert isinstance(CFromState(keys=("a",)), CTransform)
        assert isinstance(CWindow(n=3), CTransform)
        assert isinstance(CUserOnly(), CTransform)
        assert isinstance(CFromAgents(agents=("a",)), CTransform)
        assert isinstance(CExcludeAgents(agents=("a",)), CTransform)
        assert isinstance(CTemplate(template="hello"), CTransform)
        assert isinstance(CBudget(), CTransform)
        assert isinstance(CPriority(), CTransform)


# ======================================================================
# Composition operators
# ======================================================================


class TestComposition:
    def test_add_creates_composite(self):
        a = C.none()
        b = C.default()
        result = a + b
        assert isinstance(result, CComposite)

    def test_composite_has_both_blocks(self):
        a = C.none()
        b = C.default()
        result = a + b
        assert len(result.blocks) == 2
        assert result.blocks[0] is a
        assert result.blocks[1] is b

    def test_add_flattens_composites(self):
        a = C.none()
        b = C.default()
        c = C.user_only()
        result = (a + b) + c
        assert isinstance(result, CComposite)
        assert len(result.blocks) == 3

    def test_pipe_creates_cpipe(self):
        a = C.window(n=3)
        b = C.from_state("key")
        result = a | b
        assert isinstance(result, CPipe)

    def test_pipe_has_source_and_transform(self):
        a = C.window(n=3)
        b = C.from_state("key")
        result = a | b
        assert result.source is a
        assert result.transform is b


# ======================================================================
# C.from_state()
# ======================================================================


class TestFromState:
    def test_creates_transform(self):
        t = C.from_state("topic", "style")
        assert isinstance(t, CFromState)
        assert isinstance(t, CTransform)

    def test_include_contents_is_none(self):
        t = C.from_state("topic")
        assert t.include_contents == "none"

    def test_has_instruction_provider(self):
        t = C.from_state("topic")
        assert t.instruction_provider is not None
        assert callable(t.instruction_provider)

    def test_keys_stored(self):
        t = C.from_state("a", "b", "c")
        assert t.keys == ("a", "b", "c")

    def test_frozen(self):
        t = C.from_state("a")
        with pytest.raises(AttributeError):
            t.keys = ("b",)


# ======================================================================
# C.window()
# ======================================================================


class TestWindow:
    def test_creates_transform(self):
        t = C.window(n=3)
        assert isinstance(t, CWindow)
        assert isinstance(t, CTransform)

    def test_include_contents_is_none(self):
        t = C.window(n=3)
        assert t.include_contents == "none"

    def test_has_instruction_provider(self):
        t = C.window(n=3)
        assert t.instruction_provider is not None
        assert callable(t.instruction_provider)

    def test_n_stored(self):
        t = C.window(n=7)
        assert t.n == 7

    def test_last_n_turns_alias(self):
        t = C.last_n_turns(5)
        assert isinstance(t, CWindow)
        assert t.n == 5


# ======================================================================
# C.user_only()
# ======================================================================


class TestUserOnly:
    def test_creates_transform(self):
        t = C.user_only()
        assert isinstance(t, CUserOnly)
        assert isinstance(t, CTransform)

    def test_include_contents_is_none(self):
        t = C.user_only()
        assert t.include_contents == "none"

    def test_has_instruction_provider(self):
        t = C.user_only()
        assert t.instruction_provider is not None
        assert callable(t.instruction_provider)


# ======================================================================
# C.from_agents()
# ======================================================================


class TestFromAgents:
    def test_creates_transform(self):
        t = C.from_agents("writer", "reviewer")
        assert isinstance(t, CFromAgents)
        assert isinstance(t, CTransform)

    def test_include_contents_is_none(self):
        t = C.from_agents("writer")
        assert t.include_contents == "none"

    def test_has_instruction_provider(self):
        t = C.from_agents("writer")
        assert t.instruction_provider is not None
        assert callable(t.instruction_provider)

    def test_agents_stored(self):
        t = C.from_agents("a", "b")
        assert t.agents == ("a", "b")


# ======================================================================
# C.exclude_agents()
# ======================================================================


class TestExcludeAgents:
    def test_creates_transform(self):
        t = C.exclude_agents("debug_agent")
        assert isinstance(t, CExcludeAgents)
        assert isinstance(t, CTransform)

    def test_include_contents_is_none(self):
        t = C.exclude_agents("debug_agent")
        assert t.include_contents == "none"

    def test_has_instruction_provider(self):
        t = C.exclude_agents("debug_agent")
        assert t.instruction_provider is not None
        assert callable(t.instruction_provider)

    def test_agents_stored(self):
        t = C.exclude_agents("a", "b")
        assert t.agents == ("a", "b")


# ======================================================================
# C.template()
# ======================================================================


class TestTemplate:
    def test_creates_transform(self):
        t = C.template("Hello {name}")
        assert isinstance(t, CTemplate)
        assert isinstance(t, CTransform)

    def test_has_instruction_provider(self):
        t = C.template("Hello {name}")
        assert t.instruction_provider is not None
        assert callable(t.instruction_provider)

    def test_template_stored(self):
        t = C.template("Topic: {topic}")
        assert t.template == "Topic: {topic}"

    def test_include_contents_is_default(self):
        """CTemplate does NOT override include_contents (defaults to 'default')."""
        t = C.template("Hello {name}")
        assert t.include_contents == "default"


# ======================================================================
# C.capture()
# ======================================================================


class TestCapture:
    def test_returns_callable(self):
        fn = C.capture("user_input")
        assert callable(fn)

    def test_has_capture_key(self):
        fn = C.capture("user_input")
        assert fn._capture_key == "user_input"

    def test_delegates_to_s_capture(self):
        """C.capture() should produce the same result as S.capture()."""
        from adk_fluent._transforms import S

        c_fn = C.capture("query")
        s_fn = S.capture("query")
        assert c_fn._capture_key == s_fn._capture_key


# ======================================================================
# C.budget()
# ======================================================================


class TestBudget:
    def test_creates_transform(self):
        t = C.budget(max_tokens=4000)
        assert isinstance(t, CBudget)
        assert isinstance(t, CTransform)

    def test_defaults(self):
        t = C.budget()
        assert t.max_tokens == 8000
        assert t.overflow == "truncate_oldest"

    def test_custom_values(self):
        t = C.budget(max_tokens=2000, overflow="drop_oldest")
        assert t.max_tokens == 2000
        assert t.overflow == "drop_oldest"


# ======================================================================
# C.priority()
# ======================================================================


class TestPriority:
    def test_creates_transform(self):
        t = C.priority(tier=1)
        assert isinstance(t, CPriority)
        assert isinstance(t, CTransform)

    def test_default_tier(self):
        t = C.priority()
        assert t.tier == 2

    def test_custom_tier(self):
        t = C.priority(tier=0)
        assert t.tier == 0


# ======================================================================
# _compile_context_spec
# ======================================================================


class TestCompileContextSpec:
    def test_none_spec_passthrough(self):
        result = _compile_context_spec("Do something.", None)
        assert result["include_contents"] == "default"
        assert result["instruction"] == "Do something."

    def test_none_transform_sets_include_contents(self):
        result = _compile_context_spec("Do something.", C.none())
        assert result["include_contents"] == "none"
        assert result["instruction"] == "Do something."

    def test_default_transform_keeps_defaults(self):
        result = _compile_context_spec("Do something.", C.default())
        assert result["include_contents"] == "default"
        assert result["instruction"] == "Do something."

    def test_from_state_creates_provider(self):
        result = _compile_context_spec("Analyze {topic}.", C.from_state("topic"))
        assert result["include_contents"] == "none"
        assert callable(result["instruction"])

    def test_window_creates_provider(self):
        result = _compile_context_spec("Review.", C.window(n=3))
        assert result["include_contents"] == "none"
        assert callable(result["instruction"])
