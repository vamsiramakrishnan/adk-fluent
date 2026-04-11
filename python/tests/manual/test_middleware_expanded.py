"""Tests for M namespace expansion."""

from __future__ import annotations

from adk_fluent._middleware import M, MComposite


class TestCircuitBreaker:
    def test_creates_composite(self):
        mc = M.circuit_breaker(threshold=3, reset_after=30)
        assert isinstance(mc, MComposite)
        assert len(mc) == 1

    def test_composes(self):
        mc = M.circuit_breaker() | M.log()
        assert len(mc) == 2

    def test_defaults(self):
        mc = M.circuit_breaker()
        mw = mc.to_stack()[0]
        assert mw._threshold == 5
        assert mw._reset_after == 60


class TestTimeoutMiddleware:
    def test_creates_composite(self):
        mc = M.timeout(seconds=15)
        assert isinstance(mc, MComposite)
        assert len(mc) == 1

    def test_default(self):
        mc = M.timeout()
        mw = mc.to_stack()[0]
        assert mw._seconds == 30


class TestModelCache:
    def test_creates_composite(self):
        mc = M.cache(ttl=120)
        assert isinstance(mc, MComposite)
        assert len(mc) == 1

    def test_default_ttl(self):
        mc = M.cache()
        mw = mc.to_stack()[0]
        assert mw._ttl == 300


class TestFallbackModel:
    def test_creates_composite(self):
        mc = M.fallback_model(model="gemini-2.0-flash")
        assert isinstance(mc, MComposite)
        assert len(mc) == 1


class TestDedup:
    def test_creates_composite(self):
        mc = M.dedup(window=5)
        assert isinstance(mc, MComposite)
        assert len(mc) == 1


class TestSample:
    def test_wraps_middleware(self):
        mc = M.sample(0.1, M.log())
        assert isinstance(mc, MComposite)
        assert len(mc) == 1


class TestTrace:
    def test_creates_composite(self):
        mc = M.trace()
        assert isinstance(mc, MComposite)
        assert len(mc) == 1


class TestMetrics:
    def test_creates_composite(self):
        mc = M.metrics()
        assert isinstance(mc, MComposite)
        assert len(mc) == 1
