# Streaming with .stream()

*How to use streaming execution for real-time output.*

_Source: `09_streaming.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
# Native ADK requires manual event iteration:
#   async for event in runner.run_async(user_id="u", session_id=s.id, new_message=content):
#       if event.content and event.content.parts:
#           for part in event.content.parts:
#               if part.text:
#                   print(part.text, end="")
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent

# Streaming in one line:
# async for chunk in Agent("s").model("gemini-2.5-flash").instruct("Tell stories.").stream("Once upon a time"):
#     print(chunk, end="")

builder = Agent("s").model("gemini-2.5-flash").instruct("Tell stories.")
```
:::
::::

## Equivalence

```python
assert hasattr(builder, "stream")
assert callable(builder.stream)
```
