"""Typed State Keys with StateKey"""

# --- NATIVE ---
# Native ADK uses raw string keys and untyped state access:
#   ctx.state["call_count"] = ctx.state.get("call_count", 0) + 1
#   ctx.state["temp:processing"] = True
#
# Problems: typos are silent, no type hints, scope prefixes are manual.

# --- FLUENT ---
from adk_fluent import StateKey

# Define typed state keys with scope and defaults
call_count = StateKey("call_count", scope="session", type=int, default=0)
is_processing = StateKey("processing", scope="temp", type=bool, default=False)
user_pref = StateKey("preference", scope="user", type=str, default="standard")
app_config = StateKey("config_version", scope="app", type=str, default="v1")

# StateKey auto-builds the full key with scope prefix
# session scope: no prefix (default)
# temp/user/app: prefixed

# Usage in callbacks/tools:
#   current = call_count.get(ctx)    # Returns int, typed
#   call_count.set(ctx, current + 1)
#   call_count.increment(ctx)        # Convenience for numerics
#
#   items = StateKey("items", type=list, default=[])
#   items.append(ctx, "new_item")    # List append convenience

# --- ASSERT ---
# Key construction
assert call_count.key == "call_count"  # session scope = no prefix
assert is_processing.key == "temp:processing"
assert user_pref.key == "user:preference"
assert app_config.key == "app:config_version"

# Properties
assert call_count.name == "call_count"
assert call_count.scope == "session"


# Get/set with mock state
class MockCtx:
    def __init__(self):
        self.state = {}


ctx = MockCtx()
assert call_count.get(ctx) == 0  # Returns default
call_count.set(ctx, 5)
assert call_count.get(ctx) == 5

# Increment
call_count.increment(ctx)
assert call_count.get(ctx) == 6

# Append
items = StateKey("items", type=list, default=[])
items.append(ctx, "first")
items.append(ctx, "second")
assert items.get(ctx) == ["first", "second"]

# Invalid scope raises
import pytest

with pytest.raises(ValueError, match="Invalid scope"):
    StateKey("bad", scope="nonexistent")
