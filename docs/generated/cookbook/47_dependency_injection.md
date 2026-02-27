# Dependency Injection: Multi-Environment Deployment (Dev/Staging/Prod)

*How to use dependency injection: multi-environment deployment (dev/staging/prod) with the fluent API.*

_Source: `47_dependency_injection.py`_

::::\{tab-set}
:::\{tab-item} Native ADK

```python
import functools

from google.adk.agents.llm_agent import LlmAgent


def query_patient_records_native(patient_id: str, db_connection=None) -> str:
    """Query patient records from the database."""
    return f"Records for patient {patient_id} from {db_connection}"


# Native ADK: manually wrap functions with partial or closures.
# The db_connection parameter leaks into the LLM schema -- the model
# sees it and may try to set it, which is a security concern.
agent_native = LlmAgent(
    name="patient_query",
    model="gemini-2.5-flash",
    instruction="Query patient records by ID.",
    tools=[functools.partial(query_patient_records_native, db_connection="prod_ehr_db")],
)
```

:::
:::\{tab-item} adk-fluent

```python
import inspect

from adk_fluent import Agent
from adk_fluent.di import inject_resources


def query_patient_records(patient_id: str, db_connection: object) -> str:
    """Query patient records from the database."""
    return f"Records for patient {patient_id} from {db_connection}"


# Scenario: A healthcare agent deployed across dev, staging, and production.
# Each environment connects to a different database. The LLM should never
# see or influence which database is used -- that's an infrastructure concern.

# Production deployment: inject the production database connection
prod_agent = (
    Agent("patient_query")
    .model("gemini-2.5-flash")
    .instruct("Query patient records by ID.")
    .tool(query_patient_records)
    .inject(db_connection="prod_ehr_db")
)

# Staging deployment: same agent definition, different database
staging_agent = (
    Agent("patient_query")
    .model("gemini-2.5-flash")
    .instruct("Query patient records by ID.")
    .tool(query_patient_records)
    .inject(db_connection="staging_ehr_db")
)

# Dev deployment: uses an in-memory mock database
dev_agent = (
    Agent("patient_query")
    .model("gemini-2.5-flash")
    .instruct("Query patient records by ID.")
    .tool(query_patient_records)
    .inject(db_connection="dev_mock_db")
)
```

:::
::::

## Equivalence

```python
# inject() stores resources on the builder for each environment
assert prod_agent._config["_resources"] == {"db_connection": "prod_ehr_db"}
assert staging_agent._config["_resources"] == {"db_connection": "staging_ehr_db"}
assert dev_agent._config["_resources"] == {"db_connection": "dev_mock_db"}

# inject_resources() wraps a function and hides injected params from the LLM schema
wrapped = inject_resources(query_patient_records, {"db_connection": "test_db"})
sig = inspect.signature(wrapped)
assert "patient_id" in sig.parameters  # visible to LLM
assert "db_connection" not in sig.parameters  # hidden from LLM
```
