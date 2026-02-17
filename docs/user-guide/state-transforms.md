# State Transforms

`S` factories return dict transforms that compose with `>>` as zero-cost workflow nodes. They manipulate session state between agent steps without making LLM calls.

## Basic Usage

```python
from adk_fluent import S

pipeline = (
    (web_agent | scholar_agent)
    >> S.merge("web", "scholar", into="research")
    >> S.default(confidence=0.0)
    >> S.rename(research="input")
    >> writer_agent
)
```

## Transform Reference

| Factory | Purpose |
|---------|---------|
| `S.pick(*keys)` | Keep only specified keys |
| `S.drop(*keys)` | Remove specified keys |
| `S.rename(**kw)` | Rename keys |
| `S.default(**kw)` | Fill missing keys |
| `S.merge(*keys, into=)` | Combine keys |
| `S.transform(key, fn)` | Map a single value |
| `S.compute(**fns)` | Derive new keys |
| `S.guard(pred)` | Assert invariant |
| `S.log(*keys)` | Debug-print |

## `S.pick(*keys)`

Keep only the specified keys in state, dropping everything else:

```python
# After this, state only contains "name" and "email"
pipeline = agent >> S.pick("name", "email") >> next_agent
```

## `S.drop(*keys)`

Remove the specified keys from state:

```python
# Remove temporary/internal keys before the next step
pipeline = agent >> S.drop("_internal", "_debug") >> next_agent
```

## `S.rename(**kw)`

Rename keys in state. The keyword argument maps old names to new names:

```python
# Rename "research" to "input" for the next agent
pipeline = researcher >> S.rename(research="input") >> writer
```

## `S.default(**kw)`

Fill in missing keys with default values. Existing keys are not overwritten:

```python
# Ensure "confidence" exists with a default of 0.0
pipeline = agent >> S.default(confidence=0.0) >> evaluator
```

## `S.merge(*keys, into=)`

Combine multiple keys into a single key:

```python
# Merge "web" and "scholar" results into "research"
pipeline = (
    (web_agent | scholar_agent)
    >> S.merge("web", "scholar", into="research")
    >> writer
)
```

## `S.transform(key, fn)`

Apply a function to transform a single value in state:

```python
# Uppercase the "title" value
pipeline = agent >> S.transform("title", str.upper) >> next_agent
```

## `S.compute(**fns)`

Derive new keys by applying functions to the state:

```python
# Compute a new "summary_length" key from the existing state
pipeline = agent >> S.compute(
    summary_length=lambda s: len(s.get("summary", "")),
    has_citations=lambda s: "cite" in s.get("text", "").lower()
) >> evaluator
```

## `S.guard(pred)`

Assert an invariant on the state. Raises an error if the predicate fails:

```python
# Ensure "data" key is present before proceeding
pipeline = agent >> S.guard(lambda s: "data" in s) >> processor
```

## `S.log(*keys)`

Debug-print specified keys from state. Useful during development:

```python
# Print "web" and "scholar" values for debugging
pipeline = (
    (web_agent | scholar_agent)
    >> S.log("web", "scholar")
    >> S.merge("web", "scholar", into="research")
    >> writer
)
```

## Complete Example

```python
from pydantic import BaseModel
from adk_fluent import Agent, S, until

class Report(BaseModel):
    title: str
    body: str
    confidence: float

pipeline = (
    (   Agent("web").model("gemini-2.5-flash").instruct("Search web.")
      | Agent("scholar").model("gemini-2.5-flash").instruct("Search papers.")
    )
    >> S.log("web", "scholar")                          # Debug
    >> S.merge("web", "scholar", into="research")       # Combine
    >> S.default(confidence=0.0)                         # Default
    >> S.rename(research="input")                        # Rename
    >> Agent("writer").model("gemini-2.5-flash").instruct("Write.") @ Report
    >> S.guard(lambda s: s.get("confidence", 0) > 0)    # Assert
)
```
