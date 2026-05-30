"""Tests for cost/latency-aware routing (Route.by_cost).

Covers Capability #5: wiring the Route predicate algebra to the cost API
(CostTable / ModelRate) so users can route by estimated model cost.
"""

import pytest

from adk_fluent import Agent, CostTable, ModelRate
from adk_fluent._routing import CostRoute, Route

# A cost table where flash is markedly cheaper than pro.
COST_TABLE = CostTable(
    rates={
        "gemini-2.5-flash": ModelRate(input_per_million=0.30, output_per_million=2.50),
        "gemini-2.5-pro": ModelRate(input_per_million=1.25, output_per_million=10.00),
    }
)


class TestByCostFactory:
    def test_by_cost_returns_cost_route(self):
        route = Route.by_cost(COST_TABLE)
        assert isinstance(route, CostRoute)

    def test_by_cost_accepts_none_table(self):
        route = Route.by_cost()
        assert isinstance(route, CostRoute)


class TestCheapest:
    def test_picks_cheapest_known_model(self):
        flash = Agent("flash", "gemini-2.5-flash")
        pro = Agent("pro", "gemini-2.5-pro")
        chosen = Route.by_cost(COST_TABLE).cheapest(pro, flash)
        assert chosen is flash

    def test_order_independent(self):
        flash = Agent("flash", "gemini-2.5-flash")
        pro = Agent("pro", "gemini-2.5-pro")
        assert Route.by_cost(COST_TABLE).cheapest(flash, pro) is flash
        assert Route.by_cost(COST_TABLE).cheapest(pro, flash) is flash

    def test_unknown_model_not_chosen_over_known(self):
        flash = Agent("flash", "gemini-2.5-flash")
        mystery = Agent("mystery", "some-unlisted-model")
        chosen = Route.by_cost(COST_TABLE).cheapest(mystery, flash)
        assert chosen is flash

    def test_all_unknown_falls_back_to_first(self):
        a = Agent("a", "unknown-a")
        b = Agent("b", "unknown-b")
        chosen = Route.by_cost(COST_TABLE).cheapest(a, b)
        assert chosen is a

    def test_wildcard_makes_all_known(self):
        # With a "*" wildcard, the previously-unknown model now has a finite cost.
        table = COST_TABLE.with_rate(
            "*", input_per_million=0.01, output_per_million=0.01
        )
        flash = Agent("flash", "gemini-2.5-flash")
        cheap_wild = Agent("wild", "anything")
        # Wildcard rate (0.01/0.01) is cheaper than flash (0.30/2.50).
        chosen = Route.by_cost(table).cheapest(flash, cheap_wild)
        assert chosen is cheap_wild

    def test_no_candidates_raises(self):
        with pytest.raises(ValueError):
            Route.by_cost(COST_TABLE).cheapest()

    def test_none_table_treats_all_as_infinite(self):
        flash = Agent("flash", "gemini-2.5-flash")
        pro = Agent("pro", "gemini-2.5-pro")
        # No table -> every model is +inf -> first wins.
        assert Route.by_cost().cheapest(pro, flash) is pro

    def test_single_candidate(self):
        flash = Agent("flash", "gemini-2.5-flash")
        assert Route.by_cost(COST_TABLE).cheapest(flash) is flash


class TestCostliest:
    def test_picks_strongest_known_model(self):
        flash = Agent("flash", "gemini-2.5-flash")
        pro = Agent("pro", "gemini-2.5-pro")
        chosen = Route.by_cost(COST_TABLE).costliest(flash, pro)
        assert chosen is pro

    def test_unknown_skipped_for_known(self):
        pro = Agent("pro", "gemini-2.5-pro")
        mystery = Agent("mystery", "unlisted")
        # mystery is +inf but unknown; costliest prefers the finite known pro.
        chosen = Route.by_cost(COST_TABLE).costliest(mystery, pro)
        assert chosen is pro

    def test_no_candidates_raises(self):
        with pytest.raises(ValueError):
            Route.by_cost(COST_TABLE).costliest()


class TestEscalationPattern:
    def test_cheapest_then_otherwise_in_route(self):
        # "prefer cheapest by default, escalate on complexity" pattern.
        flash = Agent("flash", "gemini-2.5-flash")
        pro = Agent("pro", "gemini-2.5-pro")
        cheap = Route.by_cost(COST_TABLE).cheapest(flash, pro)
        route = Route("complexity").gt(0.7, pro).otherwise(cheap)
        assert route._default is flash
        assert len(route._rules) == 1


class TestExistingBehaviorUnaffected:
    """Cost routing must not perturb the existing predicate algebra."""

    def test_eq_still_works(self):
        a = Agent("a", "gemini-2.5-flash")
        route = Route("key").eq("x", a)
        assert len(route._rules) == 1
        assert route._rules[0][0]({"key": "x"}) is True
        assert route._rules[0][0]({"key": "y"}) is False

    def test_gt_otherwise_still_works(self):
        premium = Agent("premium", "gemini-2.5-pro")
        basic = Agent("basic", "gemini-2.5-flash")
        route = Route("score").gt(0.8, premium).otherwise(basic)
        assert route._rules[0][0]({"score": 0.9}) is True
        assert route._default is basic

    def test_to_ir_still_builds(self):
        a = Agent("a", "gemini-2.5-flash")
        b = Agent("b", "gemini-2.5-flash")
        route = Route("k").eq("x", a).otherwise(b)
        node = route.to_ir()
        assert node.key == "k"
