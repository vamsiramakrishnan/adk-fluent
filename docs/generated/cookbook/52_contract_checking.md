# Advanced Contract Checking with IR

*How to verify data contracts between pipeline steps.*

_Source: `52_contract_checking.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
# Native ADK has no static analysis of data flow between agents.
# Template variable errors are discovered only at runtime.
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, S
from adk_fluent.testing import check_contracts

MODEL = "gemini-2.5-flash"

# Valid pipeline: classifier writes "intent", handler reads {intent}
valid = (
    Agent("classifier").model(MODEL).instruct("Classify.").outputs("intent")
    >> Agent("handler").model(MODEL).instruct("Handle: {intent}")
)

# Check contracts — should pass
valid_issues = check_contracts(valid.to_ir())
valid_errors = [i for i in valid_issues if isinstance(i, dict) and i.get("level") == "error"]

# Invalid pipeline: handler reads {summary} but nothing writes it
invalid = (
    Agent("a").model(MODEL).instruct("Do stuff.")
    >> Agent("b").model(MODEL).instruct("Summary: {summary}")
)

# Check contracts — should find issues
invalid_issues = check_contracts(invalid.to_ir())

# Build modes: strict raises, unchecked skips, advisory (default) logs
strict_valid = valid.strict().build()  # Succeeds — contracts satisfied
unchecked_invalid = (
    Agent("a").model(MODEL).instruct("Do.")
    >> Agent("b").model(MODEL).instruct("Use: {missing}")
).unchecked().build()  # Succeeds — checking skipped
```
:::
::::

## Equivalence

```python
# Valid pipeline has no errors
assert len(valid_errors) == 0

# Invalid pipeline has issues
assert len(invalid_issues) > 0

# Strict build succeeds for valid pipeline
assert strict_valid is not None

# Unchecked build succeeds even with contract violations
assert unchecked_invalid is not None
```
