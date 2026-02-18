# Dependency Injection

*How to inject infrastructure resources into tool functions.*

_Source: n/a (v4 feature)_

::::{tab-set}
:::{tab-item} Native ADK
```python
from google.adk.agents.llm_agent import LlmAgent
import functools

# Native ADK: manually wrap functions with partial or closures
def search_db(query: str, db=None) -> str:
    """Search the database."""
    return f"Results for {query} from {db}"

# LLM sees the db parameter -- not ideal
agent = LlmAgent(
    name="searcher",
    model="gemini-2.5-flash",
    instruction="Search for data.",
    tools=[functools.partial(search_db, db=my_database)],
)
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent

def search_db(query: str, db: object) -> str:
    """Search the database."""
    return f"Results for {query} from {db}"

# .inject() hides db from LLM schema, injects at call time
agent = (
    Agent("searcher")
    .model("gemini-2.5-flash")
    .instruct("Search for data.")
    .tool(search_db)
    .inject(db="my_database")
    .build()
)
```
:::
::::

## Equivalence

```python
# inject() stores resources on the builder
from adk_fluent import Agent
a = Agent("a").inject(db="fake", cache="mem")
assert a._config["_resources"] == {"db": "fake", "cache": "mem"}
```

## inject_resources() Utility

The low-level `inject_resources()` function can be used independently:

```python
import inspect
from adk_fluent.di import inject_resources

def lookup(query: str, db: object) -> str:
    return f"{query} via {db}"

wrapped = inject_resources(lookup, {"db": "sqlite"})

# db is hidden from the signature
sig = inspect.signature(wrapped)
assert "query" in sig.parameters
assert "db" not in sig.parameters
```

:::{seealso}
User guide: [Builders - Dependency Injection](../user-guide/builders.md#dependency-injection)
:::
