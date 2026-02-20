# Live Sports Commentary -- Streaming with .stream()

Demonstrates the .stream() method for token-by-token output.  The
scenario: a live sports commentary agent that streams play-by-play
narration as it generates, providing real-time updates to viewers.
No LLM calls are made here -- we only verify builder mechanics.

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

# In production, streaming is a single async for loop:
# async for chunk in (
#     Agent("commentator")
#     .model("gemini-2.5-flash")
#     .instruct("Provide enthusiastic play-by-play sports commentary.")
#     .stream("The striker receives the ball at midfield...")
# ):
#     print(chunk, end="")

builder = (
    Agent("commentator")
    .model("gemini-2.5-flash")
    .instruct(
        "You are a live sports commentator. Provide enthusiastic, "
        "detailed play-by-play narration. Build excitement as the "
        "action unfolds and explain tactical decisions."
    )
)
```
:::
::::

## Equivalence

```python
assert hasattr(builder, "stream")
assert callable(builder.stream)
assert builder._config["name"] == "commentator"
```
