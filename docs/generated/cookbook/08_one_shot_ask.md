# Quick Code Review -- One-Shot Execution with .ask()

Demonstrates the .ask() convenience method for fire-and-forget
queries.  The scenario: a code review agent that can be invoked
with a single line to get feedback on a code snippet.
No LLM calls are made here -- we only verify builder mechanics.

*How to use one-shot execution for quick queries.*

_Source: `08_one_shot_ask.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
# Native ADK requires 15+ lines of boilerplate:
#   from google.adk.agents.llm_agent import LlmAgent
#   from google.adk.runners import InMemoryRunner
#   from google.genai import types
#   import asyncio
#
#   agent = LlmAgent(
#       name="code_reviewer",
#       model="gemini-2.5-flash",
#       instruction="Review code for bugs, style issues, and security vulnerabilities.",
#   )
#   runner = InMemoryRunner(agent=agent, app_name="app")
#
#   async def run():
#       session = await runner.session_service.create_session(app_name="app", user_id="u")
#       content = types.Content(role="user", parts=[types.Part(text="Review this: def f(x): return x+1")])
#       async for event in runner.run_async(user_id="u", session_id=session.id, new_message=content):
#           if event.content and event.content.parts:
#               return event.content.parts[0].text
#
#   result = asyncio.run(run())
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent

# In production, one line is all you need:
# feedback = (
#     Agent("code_reviewer")
#     .model("gemini-2.5-flash")
#     .instruct("Review code for bugs, style issues, and security vulnerabilities.")
#     .ask("Review this: def f(x): return x+1")
# )

# Builder mechanics verification (no LLM call):
builder = (
    Agent("code_reviewer")
    .model("gemini-2.5-flash")
    .instruct(
        "Review code for bugs, style issues, and security vulnerabilities. "
        "Focus on correctness, readability, and potential edge cases."
    )
)
```
:::
::::

## Equivalence

```python
assert hasattr(builder, "ask")
assert callable(builder.ask)
assert hasattr(builder, "ask_async")
assert callable(builder.ask_async)
assert builder._config["name"] == "code_reviewer"
```
