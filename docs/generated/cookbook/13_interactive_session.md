# Customer Support Chat Session with .session()

:::{admonition} Why this matters
:class: important
Multi-turn conversations require session state: the agent needs to remember what the customer said three messages ago. The `.session()` context manager handles session creation, state persistence, and cleanup automatically. This is essential for customer support chatbots, guided workflows, and any interaction that spans multiple exchanges.
:::

:::{warning} Without this
Without managed sessions, multi-turn agents either lose context between messages (treating each turn as independent) or require manual session lifecycle management -- creating `InMemorySessionService`, generating session IDs, and ensuring cleanup on errors. A leaked session consumes memory indefinitely. The `.session()` context manager handles all of this automatically.
:::

:::{tip} What you'll learn
How to manage interactive multi-turn sessions with agents.
:::

_Source: `13_interactive_session.py`_

::::{tab-set}
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent

# The fluent API wraps everything in an async context manager:
# async with (
#     Agent("support_bot")
#     .model("gemini-2.5-flash")
#     .instruct("You are a customer support agent for an online store. "
#               "Help customers with orders, returns, and product questions.")
#     .session()
# ) as chat:
#     response1 = await chat.send("I need to return an item I bought last week.")
#     response2 = await chat.send("The order number is ORD-98234.")
#     response3 = await chat.send("Thanks for the help!")

# Builder verification (no LLM call needed):
builder = (
    Agent("support_bot")
    .model("gemini-2.5-flash")
    .instruct(
        "You are a customer support agent for an online store. "
        "Help customers with orders, returns, and product questions."
    )
)
```
:::
:::{tab-item} Native ADK
```python
# Native ADK requires manual session lifecycle management:
#   from google.adk.agents.llm_agent import LlmAgent
#   from google.adk.runners import InMemoryRunner
#
#   agent = LlmAgent(
#       name="support_bot",
#       model="gemini-2.5-flash",
#       instruction="You are a customer support agent for an online store.",
#   )
#   runner = InMemoryRunner(agent=agent, app_name="support_app")
#   session = await runner.session_service.create_session(
#       app_name="support_app", user_id="customer_42"
#   )
#   # Then manually call runner.run_async() for each message
#   # No context manager -- you must track session/runner yourself
```
:::
::::

## Equivalence

```python
assert hasattr(builder, "session")
assert callable(builder.session)
assert builder._config["name"] == "support_bot"
assert builder._config["model"] == "gemini-2.5-flash"
assert "customer support" in builder._config["instruction"]
```

:::{seealso}
API reference: [InMemorySessionService](../api/service.md#builder-InMemorySessionService)
:::
