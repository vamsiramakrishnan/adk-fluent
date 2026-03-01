# Order Processing with Typed State Keys

:::{admonition} Why this matters
:class: important
State keys are the backbone of inter-agent communication. When multiple agents read and write to shared state using raw strings, typos create silent bugs -- `s["order_toal"]` instead of `s["order_total"]` produces `None` with no error. Typed `StateKey` descriptors provide IDE autocompletion, scope enforcement (session vs. temp vs. user vs. app), and runtime validation. They turn state access from a stringly-typed minefield into a type-safe API.
:::

:::{warning} Without this
Without typed state keys, a misspelled key name returns `None` instead of raising an error. The downstream agent receives empty data and produces garbage output. Debugging requires tracing through every state read/write across all agents to find the typo. With `StateKey`, the IDE catches the typo before you even run the code.
:::

:::{tip} What you'll learn
How to use typed StateKey descriptors for safe state access.
:::

_Source: `21_statekey.py`_

::::{tab-set}
:::{tab-item} adk-fluent
```python
from adk_fluent import StateKey

# Define typed state keys for an order processing system
order_count = StateKey("order_count", scope="session", type=int, default=0)
cart_items = StateKey("cart_items", scope="temp", type=list, default=[])
customer_tier = StateKey("customer_tier", scope="user", type=str, default="standard")
store_version = StateKey("store_version", scope="app", type=str, default="v2.1")

# StateKey auto-builds the full key with scope prefix:
#   session scope: no prefix (default ADK behavior)
#   temp/user/app: prefixed as "temp:key", "user:key", "app:key"

# Usage in callbacks/tools:
#   current = order_count.get(ctx)      # Returns int, typed
#   order_count.increment(ctx)          # Convenience for numerics
#   cart_items.append(ctx, {"sku": "LAPTOP-001", "qty": 1})
```
:::
:::{tab-item} Native ADK
```python
# Native ADK uses raw string keys and untyped state access:
#   ctx.state["order_count"] = ctx.state.get("order_count", 0) + 1
#   ctx.state["temp:cart_items"] = []
#
# Problems: typos are silent, no type hints, scope prefixes are manual,
# and there's no way to set defaults or validate types.
```
:::
::::

## Equivalence

```python
# Key construction with correct scope prefixes
assert order_count.key == "order_count"  # session scope = no prefix
assert cart_items.key == "temp:cart_items"
assert customer_tier.key == "user:customer_tier"
assert store_version.key == "app:store_version"

# Properties
assert order_count.name == "order_count"
assert order_count.scope == "session"


# Get/set with mock state
class MockCtx:
    def __init__(self):
        self.state = {}


ctx = MockCtx()
assert order_count.get(ctx) == 0  # Returns default when unset
order_count.set(ctx, 5)
assert order_count.get(ctx) == 5

# Increment: track how many orders processed
order_count.increment(ctx)
assert order_count.get(ctx) == 6

# Append: build up a shopping cart
cart_items.append(ctx, {"sku": "LAPTOP-001", "qty": 1})
cart_items.append(ctx, {"sku": "MOUSE-042", "qty": 2})
assert cart_items.get(ctx) == [{"sku": "LAPTOP-001", "qty": 1}, {"sku": "MOUSE-042", "qty": 2}]

# Invalid scope raises ValueError
import pytest

with pytest.raises(ValueError, match="Invalid scope"):
    StateKey("bad", scope="nonexistent")
```
