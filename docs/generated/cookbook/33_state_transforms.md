# State Transforms: S Factories with >>

*How to work with state keys and state transforms.*

_Source: `33_state_transforms.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
# Native ADK requires custom BaseAgent subclasses for any state transform:
from google.adk.agents.base_agent import BaseAgent as NativeBaseAgent


class SelectKeys(NativeBaseAgent):
    async def _run_async_impl(self, ctx):
        # Keep only "findings" and "sources"
        for key in list(ctx.session.state.keys()):
            if key not in ("findings", "sources"):
                del ctx.session.state[key]


class RenameKey(NativeBaseAgent):
    async def _run_async_impl(self, ctx):
        if "findings" in ctx.session.state:
            ctx.session.state["research"] = ctx.session.state.pop("findings")

# Each transform = a new class. No composability.
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, S, Pipeline

# S.pick — keep only specified keys
picked = S.pick("findings", "sources")
assert picked({"findings": "data", "sources": ["a"], "noise": 123}) == {"findings": "data", "sources": ["a"]}

# S.drop — remove specified keys
dropped = S.drop("_internal", "_debug")
assert dropped({"result": "ok", "_internal": "x"}) == {"result": "ok"}

# S.rename — rename keys (unmapped pass through)
renamed = S.rename(findings="research", raw_score="score")
assert renamed({"findings": "data", "other": 1}) == {"research": "data", "other": 1}

# S.default — fill missing keys without overwriting
defaulted = S.default(confidence=0.5, language="en")
assert defaulted({"confidence": 0.9}) == {"confidence": 0.9, "language": "en"}

# S.merge — combine keys (default: newline join)
merged = S.merge("web", "papers", into="research")
assert merged({"web": "Web data", "papers": "Paper data"}) == {"research": "Web data\nPaper data"}

# S.merge with custom function
summed = S.merge("a", "b", into="total", fn=lambda a, b: a + b)
assert summed({"a": 10, "b": 20}) == {"total": 30}

# S.transform — apply function to single key
transformed = S.transform("text", str.upper)
assert transformed({"text": "hello"}) == {"text": "HELLO"}

# S.compute — derive new keys from full state
computed = S.compute(
    word_count=lambda s: len(s.get("text", "").split()),
    preview=lambda s: s.get("text", "")[:50],
)
assert computed({"text": "hello world"}) == {"word_count": 2, "preview": "hello world"}

# S.guard — assert state invariant
guarded = S.guard(lambda s: "key" in s, msg="Missing required key")

# Compose with >> in pipelines
pipeline = (
    Agent("researcher").model("gemini-2.5-flash").instruct("Research the topic.")
    >> S.pick("findings", "sources")
    >> S.rename(findings="research_data")
    >> S.default(confidence=0.0)
    >> Agent("writer").model("gemini-2.5-flash").instruct("Write a report.")
)

# Full research pipeline with S transforms
research_pipeline = (
    (   Agent("web").model("gemini-2.5-flash").instruct("Search web.")
      | Agent("scholar").model("gemini-2.5-flash").instruct("Search papers.")
    )
    >> S.merge("web", "scholar", into="research")
    >> S.default(confidence=0.0, draft_count=0)
    >> Agent("writer").model("gemini-2.5-flash").instruct("Write report.")
    >> S.compute(
        word_count=lambda s: len(s.get("report", "").split()),
    )
)
```
:::
::::

## Equivalence

```python
# S transforms compose with >> into Pipeline
assert isinstance(pipeline, Pipeline)
built = pipeline.build()
assert len(built.sub_agents) == 5  # researcher, pick, rename, default, writer

# All transform agent names are valid identifiers
for sub in built.sub_agents:
    assert sub.name.isidentifier(), f"Invalid name: {sub.name}"

# Research pipeline builds correctly
assert isinstance(research_pipeline, Pipeline)
built_research = research_pipeline.build()
assert len(built_research.sub_agents) == 5  # fanout, merge, default, writer, compute
```
