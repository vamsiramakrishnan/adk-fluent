# Interactive Session with .session()

*How to manage interactive sessions with agents.*

_Source: `13_interactive_session.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
# Native ADK requires manual session lifecycle:
#   runner = InMemoryRunner(agent=agent, app_name="app")
#   session = await runner.session_service.create_session(...)
#   # Send messages manually with runner.run_async()
#   # No automatic cleanup
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent

# Context manager handles everything:
# async with Agent("chat").model("gemini-2.5-flash").instruct("Tutor.").session() as chat:
#     response1 = await chat.send("What is calculus?")
#     response2 = await chat.send("Give me an example.")

builder = Agent("chat").model("gemini-2.5-flash").instruct("Tutor.")
```
:::
::::

## Equivalence

```python
assert hasattr(builder, "session")
assert callable(builder.session)
```

:::{seealso}
API reference: [InMemorySessionService](../api/service.md#builder-InMemorySessionService)
:::
