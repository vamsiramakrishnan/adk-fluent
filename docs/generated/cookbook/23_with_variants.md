# Immutable Variants with .with_()

*How to create builder variants.*

_Source: `23_with_variants.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
# Native ADK provides no cloning or variant mechanism. You'd manually
# duplicate constructor calls, risking drift when the base config changes.
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent

base = Agent("assistant").model("gemini-2.5-flash").instruct("You are a helpful assistant.")

# with_() creates an independent copy with overrides
creative = base.with_(name="creative", model="gemini-2.5-pro")
fast = base.with_(name="fast", instruct="You are fast and concise.")

# Original is unchanged
assert base._config["name"] == "assistant"
assert base._config["model"] == "gemini-2.5-flash"
```
:::
::::

## Equivalence

```python
# Variants have overridden values
assert creative._config["name"] == "creative"
assert creative._config["model"] == "gemini-2.5-pro"
assert creative._config["instruction"] == "You are a helpful assistant."  # Inherited

assert fast._config["name"] == "fast"
assert fast._config["model"] == "gemini-2.5-flash"  # Inherited

# Variants are independent (modifying one doesn't affect others)
creative._config["instruction"] = "Be creative!"
assert base._config["instruction"] == "You are a helpful assistant."
assert fast._config["instruction"] != "Be creative!"
```
