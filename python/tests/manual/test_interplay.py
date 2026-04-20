"""Cross-module composition tests — G+M, G+T, T+M, S+G, full pipeline."""

from __future__ import annotations

from adk_fluent._guards import G
from adk_fluent._middleware import M
from adk_fluent._tools import T, TComposite
from adk_fluent._transforms import S, STransform
from adk_fluent.agent import Agent


class TestGWithM:
    def test_guard_and_middleware_coexist(self):
        builder = Agent("test").guard(G.json() | G.budget(max_tokens=5000))
        # Both json and budget compile to after_model_callback
        assert len(builder._callbacks.get("after_model_callback", [])) >= 2

    def test_guard_does_not_interfere_with_middleware(self):
        mc = M.retry(3) | M.circuit_breaker()
        assert len(mc) == 2
        # G and M are independent composition chains
        gc = G.json() | G.length(max=500)
        assert len(gc) == 2


class TestTWrappers:
    def test_cache_and_timeout_compose(self):
        tc = T.cache(T.timeout(T.fn(lambda: "x"), seconds=5), ttl=60)
        assert isinstance(tc, TComposite)
        assert len(tc) == 1  # nested wrappers

    def test_mock_composes_with_real(self):
        tc = T.mock("search", returns="x") | T.fn(lambda: "y")
        assert len(tc) == 2

    def test_confirm_and_schema_compose(self):
        tc = T.confirm(T.fn(lambda: "x")) | T.schema(type)
        assert len(tc) == 2


class TestSExpansion:
    def test_accumulate_chains_with_require(self):
        pipeline = S.accumulate("item", into="items") >> S.require("items")
        assert isinstance(pipeline, STransform)

    def test_counter_chains_with_guard(self):
        pipeline = S.counter("n") >> S.guard(lambda s: s["n"] < 100)
        assert isinstance(pipeline, STransform)

    def test_validate_composes_with_pick(self):
        from dataclasses import dataclass

        @dataclass
        class Schema:
            name: str

        pipeline = S.pick("name") >> S.validate(Schema)
        assert isinstance(pipeline, STransform)


class TestFullPipeline:
    def test_all_namespaces_on_single_agent(self):
        """Verify all namespace methods can be called on a single agent without error."""
        from adk_fluent._context import C
        from adk_fluent._prompt import P

        builder = (
            Agent("test")
            .instruct(P.role("analyst") | P.task("analyze data"))
            .context(C.window(n=10))
            .tools(T.mock("search", returns="ok") | T.fn(lambda: "x"))
            .guard(G.json() | G.length(max=1000))
        )
        # Verify builder state
        assert len(builder._callbacks.get("after_model_callback", [])) >= 2
        assert len(builder._lists.get("tools", [])) >= 2

    def test_namespace_spec_protocol_all(self):
        """All expanded namespace objects conform to NamespaceSpec."""
        specs = [
            G.json(),
            T.mock("x", returns="y"),
            M.circuit_breaker(),
            S.accumulate("x"),
        ]
        for spec in specs:
            assert hasattr(spec, "_kind")
            assert hasattr(spec, "_reads_keys")
            assert hasattr(spec, "_writes_keys")
