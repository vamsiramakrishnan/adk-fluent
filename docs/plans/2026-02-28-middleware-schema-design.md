# MiddlewareSchema Design

## Context

Middleware v2 introduced agent-scoped middleware (`agents` attribute) and topology-aware hooks. This makes middleware position-aware in the pipeline — scoped middleware runs at a specific agent's position, reading/writing state just like tools and callbacks. A `MiddlewareSchema` declaration enables the contract checker to validate middleware state dependencies at the scoped agent's position, completing the uniform schema family: `ToolSchema`, `CallbackSchema`, `PredicateSchema`, `MiddlewareSchema`.

Additionally, `M.when()` currently accepts string shortcuts and callables but cannot accept state-aware predicates. Extending `M.when()` to accept `PredicateSchema` subclasses enables deferred condition checking against session state at invocation time.

## Design

### 1. MiddlewareSchema Type

New file `src/adk_fluent/_middleware_schema.py` following the `DeclarativeMetaclass` pattern:

```python
class BudgetState(MiddlewareSchema):
    token_budget: Annotated[int, Reads(scope="app")]
    tokens_used: Annotated[int, Writes(scope="temp")]

class BudgetEnforcer:
    agents = "writer"          # existing scoping
    schema = BudgetState       # NEW: state dependencies
    async def before_agent(self, ctx, agent_name): ...
```

`MiddlewareSchema` uses the shared `DeclarativeMetaclass` to introspect `Annotated` type hints into `DeclarativeField` objects, consistent with `ToolSchema`/`CallbackSchema`/`PredicateSchema`.

Binding: class attribute `schema = SomeMiddlewareSchema` on the middleware class, parallel to the existing `agents` attribute.

### 2. Contract Checker Integration (Pass 15)

New pass in `_contract_checking.py`:

```python
def _check_middleware_contracts(sequence, middlewares):
    """Validate scoped middleware schemas against pipeline state flow."""
```

**Rules:**

- Only validates middleware with BOTH `agents` AND `schema` attributes
- Unscoped middleware (no `agents`): skip validation — schema is introspection-only
- Scoped middleware: validate reads/writes at the target agent's position in the pipeline
- Reads must be satisfied by prior writes in the sequence
- Writes are added to available state at the agent's position

### 3. `_ConditionalMiddleware` Rewrite

Current `_ConditionalMiddleware.__getattr__` evaluates the condition and returns `None` if false, preventing hook discovery and precluding state-aware predicates (no state available at `__getattr__` time).

**Rewrite:** Return a guarded wrapper function that defers condition evaluation to invocation time:

```python
def __getattr__(self, name):
    fn = getattr(self._inner, name, None)
    if fn is None or not callable(fn):
        raise AttributeError(name)
    @functools.wraps(fn)
    async def _guarded(*args, **kwargs):
        if not self._check():
            return None
        return await fn(*args, **kwargs)
    return _guarded
```

This enables `M.when(PredicateSchema, middleware)` — the predicate reads session state from `TraceContext.invocation_context` at hook invocation time.

### 4. `M.when()` Overload

`M.when()` in `_middleware.py` is extended to accept `PredicateSchema` subclasses:

```python
@staticmethod
def when(condition: str | Callable[[], bool] | type, mw: MComposite | Any) -> MComposite:
    """Conditionally apply middleware.

    Accepts: str shortcut, callable, or PredicateSchema subclass.
    """
```

Usage:

```python
class PremiumOnly(PredicateSchema):
    user_tier: Annotated[str, Reads(scope="user")]
    @staticmethod
    def evaluate(user_tier): return user_tier == "premium"

pipeline.middleware(
    M.when(PremiumOnly, M.scope("writer", BudgetEnforcer()))
)
```

### 5. Backward Compatibility

| Concern                              | Resolution                                           |
| ------------------------------------ | ---------------------------------------------------- |
| Middleware without `schema`          | Unchanged, no validation                             |
| Middleware without `agents`          | Unchanged, no position-based validation              |
| `M.when(str_shortcut)`               | Works as before                                      |
| `M.when(callable)`                   | Works as before                                      |
| `_ConditionalMiddleware.__getattr__` | Returns guarded wrappers (improvement, not breaking) |

### 6. Files Modified

| File                                   | Changes                                                                 |
| -------------------------------------- | ----------------------------------------------------------------------- |
| `src/adk_fluent/_middleware_schema.py` | **NEW** — `MiddlewareSchema` class, `middleware_schema_fields()` helper |
| `src/adk_fluent/middleware.py`         | `_ConditionalMiddleware` rewrite, `_evaluate_predicate` helper          |
| `src/adk_fluent/_middleware.py`        | `M.when()` extended for `PredicateSchema`                               |
| `src/adk_fluent/_contract_checking.py` | Pass 15: `_check_middleware_contracts()`                                |

### 7. Testing Strategy

1. Unit: `MiddlewareSchema` metaclass introspection
1. Unit: `_ConditionalMiddleware` with `PredicateSchema` (deferred evaluation)
1. Unit: `_evaluate_predicate` with mock invocation context
1. Contract checker: scoped middleware with reads satisfied / unsatisfied
1. Contract checker: unscoped middleware skipped
1. Integration: `M.when(PredicateSchema, M.scope("agent", mw))` end-to-end
