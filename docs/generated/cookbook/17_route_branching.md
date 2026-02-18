# Deterministic Route Branching

*How to implement conditional routing and branching.*

_Source: `17_route_branching.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
# Native ADK has no built-in deterministic router. You'd need:
#   1. An LlmAgent coordinator (wastes API calls for simple decisions), OR
#   2. A custom BaseAgent subclass with predicate logic
# Neither approach is ergonomic.
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent
from adk_fluent._routing import Route

booker = Agent("booker").model("gemini-2.5-flash").instruct("Book flights.")
info = Agent("info").model("gemini-2.5-flash").instruct("Provide info.")
default = Agent("fallback").model("gemini-2.5-flash").instruct("Handle other.")

# Route on exact match
route = Route("intent").eq("booking", booker).eq("info", info).otherwise(default)

# Route on substring
urgent = Agent("urgent").model("gemini-2.5-flash").instruct("Handle urgently.")
normal = Agent("normal").model("gemini-2.5-flash").instruct("Handle normally.")
text_route = Route("message").contains("URGENT", urgent).otherwise(normal)

# Route on threshold
premium = Agent("premium").model("gemini-2.5-flash").instruct("Premium service.")
basic = Agent("basic").model("gemini-2.5-flash").instruct("Basic service.")
score_route = Route("score").gt(0.8, premium).otherwise(basic)

# Complex multi-key predicate
complex_route = (
    Route().when(lambda s: s.get("status") == "vip" and float(s.get("score", 0)) > 0.5, premium).otherwise(basic)
)
```
:::
::::

## Equivalence

```python
from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.llm_agent import LlmAgent

# Route builds to BaseAgent (deterministic, no LLM)
built = route.build()
assert isinstance(built, BaseAgent)
assert not isinstance(built, LlmAgent)
assert len(built.sub_agents) == 3  # booker, info, default

# Text route works
built_text = text_route.build()
assert len(built_text.sub_agents) == 2

# Score route works
built_score = score_route.build()
assert len(built_score.sub_agents) == 2
```
