# Module: contracts

> `from adk_fluent.testing import check_contracts`

Static analysis of data flow and contracts between pipeline agents.

## `check_contracts(ir) -> list`

Analyze an IR tree for contract violations. Returns a list of issues (strings or dicts with `level` and `message` keys).

**Parameters:**
- `ir` — IR node from `pipeline.to_ir()`

**Returns:** List of issues. Empty list means no violations found.

**Example:**
```python
from adk_fluent.testing import check_contracts

pipeline = (
    Agent("classifier").outputs("intent")
    >> Agent("handler").instruct("Handle: {intent}")
)
issues = check_contracts(pipeline.to_ir())
assert issues == []  # All contracts satisfied
```

## Analysis Passes

The checker runs 7 analysis passes:

| Pass | What it checks |
|------|---------------|
| 1. Reads/Writes | State keys read and written by each agent |
| 2. Output keys | Keys declared via `.outputs()` |
| 3. Template variables | `{key}` placeholders in instructions |
| 4. Channel duplication | Same key used across multiple channels |
| 5. Route keys | Route dispatch keys exist in upstream outputs |
| 6. Data loss | Keys written but never read downstream |
| 7. Visibility coherence | Visibility classification consistency |

## Build Modes

Contract checking integrates with the build path:

| Mode | Method | Behavior |
|------|--------|----------|
| Advisory (default) | `.build()` | Log warnings, build succeeds |
| Strict | `.strict().build()` | Raise `ValueError` on errors |
| Unchecked | `.unchecked().build()` | Skip contract checking entirely |
