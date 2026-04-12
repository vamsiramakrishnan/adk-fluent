"""Tests for ported A2A features: patterns, T.a2a(), exports."""

import warnings

import pytest

from adk_fluent import Agent, a2a_cascade, a2a_delegate, a2a_fanout

# ======================================================================
# 1. a2a_cascade
# ======================================================================


class TestA2ACascade:
    def test_creates_fallback_chain(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = a2a_cascade("http://a:8001", "http://b:8002")
        assert result is not None

    def test_three_endpoints(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = a2a_cascade("http://a:8001", "http://b:8002", "http://c:8003")
        assert result is not None

    def test_custom_names(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = a2a_cascade("http://a:8001", "http://b:8002", names=["fast", "slow"])
        assert result is not None

    def test_requires_two_endpoints(self):
        with pytest.raises(ValueError, match="at least 2"):
            a2a_cascade("http://a:8001")


# ======================================================================
# 2. a2a_fanout
# ======================================================================


class TestA2AFanout:
    def test_creates_parallel(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = a2a_fanout("http://a:8001", "http://b:8002")
        assert result is not None

    def test_custom_names(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = a2a_fanout("http://a:8001", "http://b:8002", names=["web", "papers"])
        assert result is not None

    def test_requires_two_endpoints(self):
        with pytest.raises(ValueError, match="at least 2"):
            a2a_fanout("http://a:8001")


# ======================================================================
# 3. a2a_delegate
# ======================================================================


class TestA2ADelegate:
    def test_attaches_remotes(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            coord = Agent("coord", "gemini-2.5-flash")
            result = a2a_delegate(coord, research="http://r:8001", code="http://c:8002")
        assert result is not None

    def test_single_remote(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = a2a_delegate(Agent("coord"), helper="http://h:8001")
        assert result is not None


# ======================================================================
# 4. T.a2a() - import only (build requires actual A2A SDK)
# ======================================================================


class TestTA2AImport:
    def test_t_has_a2a_method(self):
        from adk_fluent import T

        assert hasattr(T, "a2a")


# ======================================================================
# 5. Exports
# ======================================================================


class TestPortedExports:
    def test_import_from_package(self):
        from adk_fluent import a2a_cascade, a2a_delegate, a2a_fanout

        assert all([a2a_cascade, a2a_delegate, a2a_fanout])

    def test_import_from_prelude(self):
        from adk_fluent.prelude import a2a_cascade, a2a_delegate, a2a_fanout

        assert all([a2a_cascade, a2a_delegate, a2a_fanout])

    def test_import_from_patterns(self):
        from adk_fluent.patterns import a2a_cascade, a2a_delegate, a2a_fanout

        assert all([a2a_cascade, a2a_delegate, a2a_fanout])

    def test_in_patterns_all(self):
        import adk_fluent.patterns as patterns

        for name in ("a2a_cascade", "a2a_fanout", "a2a_delegate"):
            assert name in patterns.__all__

    def test_in_prelude_all(self):
        import adk_fluent.prelude as prelude

        for name in ("a2a_cascade", "a2a_fanout", "a2a_delegate"):
            assert name in prelude.__all__
