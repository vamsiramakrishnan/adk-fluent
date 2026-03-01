# Content Moderation with Logging -- Additive Callbacks

Demonstrates before_model and after_model callbacks.  The scenario:
a content moderation agent where we log every request before it
reaches the model and audit every response after generation.

:::{admonition} Why this matters
:class: important
Callbacks provide hooks into the agent lifecycle for logging, auditing, content filtering, and compliance. In regulated industries, every model invocation must be logged for audit trails. Content moderation callbacks prevent harmful outputs from reaching users. The fluent builder's additive callback semantics mean multiple `.before_model()` and `.after_model()` calls accumulate rather than overwrite -- so a compliance team can add audit logging without removing the content moderation hooks.
:::

:::{warning} Without this
Without lifecycle callbacks, you have no visibility into what the model receives or produces. Harmful content passes through unfiltered. Compliance audits fail because there's no record of model interactions. In native ADK, setting `before_model_callback` a second time silently overwrites the first -- meaning adding audit logging accidentally removes content filtering.
:::

:::{tip} What you'll learn
How to register lifecycle callbacks with accumulation semantics.
:::

_Source: `03_callbacks.py`_

::::{tab-set}
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent

agent_fluent = (
    Agent("content_moderator")
    .model("gemini-2.5-flash")
    .instruct(
        "You are a content moderation agent. Evaluate user-submitted "
        "content and flag anything that violates community guidelines. "
        "Provide a severity rating: safe, warning, or violation."
    )
    .before_model(log_moderation_request)
    .after_model(check_response_safety)
    .build()
)
```
:::
:::{tab-item} Native ADK
```python
from google.adk.agents.llm_agent import LlmAgent


def log_moderation_request(callback_context, llm_request):
    """Log incoming content for audit trail before the model processes it."""
    print("[AUDIT] Moderation request received")


def check_response_safety(callback_context, llm_response):
    """Verify model output meets safety standards after generation."""
    print("[AUDIT] Response safety check passed")


agent_native = LlmAgent(
    name="content_moderator",
    model="gemini-2.5-flash",
    instruction=(
        "You are a content moderation agent. Evaluate user-submitted "
        "content and flag anything that violates community guidelines. "
        "Provide a severity rating: safe, warning, or violation."
    ),
    before_model_callback=log_moderation_request,
    after_model_callback=check_response_safety,
)
```
:::
::::

## Equivalence

```python
assert type(agent_native) == type(agent_fluent)
assert agent_native.before_model_callback == agent_fluent.before_model_callback
assert agent_native.after_model_callback == agent_fluent.after_model_callback
```
