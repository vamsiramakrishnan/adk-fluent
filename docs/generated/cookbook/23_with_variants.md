# A/B Prompt Testing for Marketing Copy with .with_()

:::{admonition} Why this matters
:class: important
Prompt engineering requires systematic experimentation: testing formal vs. casual tone, different temperature settings, or alternative instructions while keeping everything else identical. The `.with_()` method creates a new builder variant with specific overrides, preserving the original. This enables structured A/B testing without the risk of accidentally mutating the base agent.
:::

:::{warning} Without this
Without immutable variants, changing a prompt for experimentation risks mutating the original agent (if using mutable state) or requires full constructor duplication (if using native ADK). With `.with_()`, the original agent is guaranteed unchanged, and each variant is a minimal diff from the base.
:::

:::{tip} What you'll learn
How to create agent variants for prompt experimentation with .with_().
:::

_Source: `23_with_variants.py`_

::::{tab-set}
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent

# Base marketing copywriter agent
base_copywriter = (
    Agent("copywriter")
    .model("gemini-2.5-flash")
    .instruct("Write compelling marketing copy for product launches. Focus on benefits, not features.")
)

# with_() creates independent copies with overrides -- perfect for A/B testing
variant_a = base_copywriter.with_(
    name="copywriter_formal",
    instruct="Write formal, authoritative marketing copy for enterprise products. "
    "Use data-driven language and industry terminology.",
)
variant_b = base_copywriter.with_(
    name="copywriter_casual",
    instruct="Write casual, conversational marketing copy for consumer products. Use humor and relatable language.",
)

# Original is unchanged -- variants are fully independent
assert base_copywriter._config["name"] == "copywriter"
assert base_copywriter._config["model"] == "gemini-2.5-flash"
```
:::
:::{tab-item} Native ADK
```python
# Native ADK provides no cloning or variant mechanism. You'd manually
# duplicate constructor calls, risking drift when the base config changes.
```
:::
::::

## Equivalence

```python
# Variants have overridden values
assert variant_a._config["name"] == "copywriter_formal"
assert "formal" in variant_a._config["instruction"]
assert variant_a._config["model"] == "gemini-2.5-flash"  # Inherited from base

assert variant_b._config["name"] == "copywriter_casual"
assert "casual" in variant_b._config["instruction"]
assert variant_b._config["model"] == "gemini-2.5-flash"  # Inherited from base

# Variants are truly independent (modifying one doesn't affect others)
variant_a._config["instruction"] = "Modified!"
assert "benefits" in base_copywriter._config["instruction"]
assert variant_b._config["instruction"] != "Modified!"
```
