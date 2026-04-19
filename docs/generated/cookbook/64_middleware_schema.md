# MiddlewareSchema: Typed Middleware State Declarations

Demonstrates MiddlewareSchema for declaring middleware state dependencies,
enabling the contract checker to validate middleware reads/writes at
compile time.

Key concepts:
  - MiddlewareSchema: base class for typed middleware declarations
  - Reads(scope=...): field read from state before execution
  - Writes(scope=...): field written to state after execution
  - reads_keys() / writes_keys(): introspect declared dependencies
  - schema attribute: bind a MiddlewareSchema to a middleware class
  - agents attribute: scope middleware to specific pipeline agents
  - Contract checker Pass 14: validates scoped middleware at build time
  - M.when(PredicateSchema, mw): state-aware conditional middleware

:::{tip} What you'll learn
How to compose agents into a sequential pipeline.
:::

_Source: `64_middleware_schema.py`_

```python
from typing import Annotated

from adk_fluent._middleware_schema import MiddlewareSchema
from adk_fluent._schema_base import Reads, Writes

# --- 1. Declaring a MiddlewareSchema ---


class BudgetState(MiddlewareSchema):
    """Declares that a middleware reads a token budget and writes usage."""

    token_budget: Annotated[int, Reads(scope="app")]
    tokens_used: Annotated[int, Writes(scope="temp")]


# Introspect reads and writes
assert BudgetState.reads_keys() == frozenset({"app:token_budget"})
assert BudgetState.writes_keys() == frozenset({"temp:tokens_used"})

# --- 2. Mixed reads and writes ---


class EnrichmentState(MiddlewareSchema):
    """Reads a config key, writes an enriched result."""

    api_key: Annotated[str, Reads(scope="app")]
    enriched_data: Annotated[str, Writes()]  # default scope is "session"


assert EnrichmentState.reads_keys() == frozenset({"app:api_key"})
assert EnrichmentState.writes_keys() == frozenset({"enriched_data"})

# --- 3. Session-scoped reads (default scope) ---


class AuditState(MiddlewareSchema):
    user_id: Annotated[str, Reads()]  # scope defaults to "session"
    request_context: Annotated[str, Reads()]


assert AuditState.reads_keys() == frozenset({"user_id", "request_context"})
assert AuditState.writes_keys() == frozenset()  # no writes

# --- 4. Empty schema ---


class NoOpState(MiddlewareSchema):
    pass


assert NoOpState.reads_keys() == frozenset()
assert NoOpState.writes_keys() == frozenset()

# --- 5. Binding schema to middleware class ---


class BudgetEnforcer:
    """Middleware that enforces token budgets.

    The `schema` attribute declares state dependencies.
    The `agents` attribute scopes it to specific agents.
    """

    agents = "writer"
    schema = BudgetState

    async def before_agent(self, ctx, agent_name):
        # In production: read token_budget from state, check remaining
        pass

    async def after_model(self, ctx, response):
        # In production: update tokens_used in state
        pass


# Schema is accessible on the middleware instance
enforcer = BudgetEnforcer()
assert enforcer.schema is BudgetState
assert enforcer.agents == "writer"
assert enforcer.schema.reads_keys() == frozenset({"app:token_budget"})

# --- 6. Schema survives M.scope() and M.when() wrapping ---
from adk_fluent._middleware import M

scoped = M.scope("writer", enforcer)
wrapped = scoped.to_stack()[0]
assert wrapped.schema is BudgetState  # forwarded from inner via __getattr__

conditional = M.when("pipeline", enforcer)
cond_wrapped = conditional.to_stack()[0]
assert cond_wrapped.schema is BudgetState  # forwarded by _ConditionalMiddleware

# --- 7. Contract checker Pass 14 validation ---
from adk_fluent.testing.contracts import check_contracts

# Helper to create minimal IR nodes for contract checking
from types import SimpleNamespace

from adk_fluent._ir_generated import SequenceNode


def agent_node(name, output_key=None):
    return SimpleNamespace(
        name=name,
        output_key=output_key,
        tool_schema=None,
        callback_schema=None,
        prompt_schema=None,
        writes_keys=frozenset(),
        reads_keys=frozenset(),
        include_contents="default",
        instruction="",
        context_spec=None,
        produces_type=None,
        consumes_type=None,
        rules=(),
        predicate=None,
    )


# 7a. Satisfied reads: middleware reads "result", producer writes "result"
class NeedsResult(MiddlewareSchema):
    result: Annotated[str, Reads()]


class ReaderMW:
    agents = "reviewer"
    schema = NeedsResult


producer = agent_node("writer", output_key="result")
consumer = agent_node("reviewer")
seq = SequenceNode(
    name="test_pipeline",
    children=(producer, consumer),
    middlewares=(ReaderMW(),),
)

issues = check_contracts(seq)
mw_issues = [i for i in issues if isinstance(i, dict) and "MiddlewareSchema" in i.get("message", "")]
assert len(mw_issues) == 0  # reads satisfied -- no warnings


# 7b. Unsatisfied reads: middleware reads "missing_key", nobody produces it
class NeedsMissing(MiddlewareSchema):
    missing_key: Annotated[str, Reads()]


class MissingMW:
    agents = "reviewer"
    schema = NeedsMissing


seq_missing = SequenceNode(
    name="test_pipeline",
    children=(producer, consumer),
    middlewares=(MissingMW(),),
)

issues_missing = check_contracts(seq_missing)
mw_issues_missing = [i for i in issues_missing if isinstance(i, dict) and "MiddlewareSchema" in i.get("message", "")]
assert len(mw_issues_missing) == 1
assert "missing_key" in mw_issues_missing[0]["message"]


# 7c. Unscoped middleware: skipped by contract checker
class GlobalMW:
    schema = NeedsMissing  # has schema but no agents scope


seq_global = SequenceNode(
    name="test_pipeline",
    children=(producer, consumer),
    middlewares=(GlobalMW(),),
)

issues_global = check_contracts(seq_global)
mw_issues_global = [i for i in issues_global if isinstance(i, dict) and "MiddlewareSchema" in i.get("message", "")]
assert len(mw_issues_global) == 0  # unscoped middleware not validated


# 7d. Middleware writes promoted to downstream
class WriterSchema(MiddlewareSchema):
    enriched: Annotated[str, Writes()]


class EnricherMW:
    agents = "enricher"
    schema = WriterSchema


class ReaderSchema(MiddlewareSchema):
    enriched: Annotated[str, Reads()]


class DownstreamReaderMW:
    agents = "consumer"
    schema = ReaderSchema


enricher = agent_node("enricher")
downstream = agent_node("consumer")
seq_writes = SequenceNode(
    name="test_pipeline",
    children=(enricher, downstream),
    middlewares=(EnricherMW(), DownstreamReaderMW()),
)

issues_writes = check_contracts(seq_writes)
mw_issues_writes = [i for i in issues_writes if isinstance(i, dict) and "MiddlewareSchema" in i.get("message", "")]
assert len(mw_issues_writes) == 0  # writes promoted -- reads satisfied

# --- 8. Repr ---
m = BudgetState()
r = repr(m)
assert "BudgetState" in r
assert "token_budget" in r
assert "tokens_used" in r

# --- 9. PredicateSchema with M.when() ---
from adk_fluent._predicate_schema import PredicateSchema


class PremiumOnly(PredicateSchema):
    """Only fire middleware for premium users."""

    user_tier: Annotated[str, Reads(scope="user")]

    @staticmethod
    def evaluate(user_tier):
        return user_tier == "premium"


# Reads keys
assert PremiumOnly.reads_keys() == frozenset({"user:user_tier"})

# Can be used with M.when() for state-aware conditional middleware
premium_mw = M.when(PremiumOnly, M.scope("writer", M.cost()))
assert len(premium_mw) == 1
# Condition is deferred to invocation time -- wraps in _ConditionalMiddleware
inner = premium_mw.to_stack()[0]
assert callable(getattr(inner, "after_model", None))

print("All MiddlewareSchema and contract checking assertions passed!")
```
