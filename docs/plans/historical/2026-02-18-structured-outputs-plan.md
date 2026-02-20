# Plan: Structured Outputs & Transfer Control DX

## Context

The user wants structured outputs (input_schema, output_schema, output_key) and transfer control
(disallow_transfer_to_parent, disallow_transfer_to_peers) made "easy and accessible" in code, docs, etc.

**Current gaps:**

- `.pyi` stubs have empty docstrings for these 5 fields
- `disallow_transfer_to_parent`/`disallow_transfer_to_peers` are verbose with no short aliases
- Setting both transfer flags is the most common pattern (every specialist agent) but requires two method calls
- `input_schema` has no alias (unlike `output_key` which has `.outputs()`)
- No user guide pages for structured data patterns or transfer control
- No cookbook examples dedicated to these topics
- No `[field_docs]` section in seed.manual.toml and the seed_generator doesn't merge it

## Tasks

### Task 1: Add `[field_docs]` to seed.manual.toml + merge support

**Files:** `seeds/seed.manual.toml`, `scripts/seed_generator.py`

Add a `[field_docs]` section to seed.manual.toml with descriptive docstrings for:

- `output_schema` — "Pydantic model enforcing structured JSON output. When set, the agent cannot use tools."
- `input_schema` — "Schema defining the expected input structure when this agent is used as a tool."
- `output_key` — "Session state key where the agent's response text is stored for downstream access."
- `disallow_transfer_to_parent` — "Prevent this agent from transferring control back to its parent. Also prevents the agent from continuing to reply, forcing a handoff back to parent next turn."
- `disallow_transfer_to_peers` — "Prevent this agent from transferring control to sibling agents."

Update `merge_manual_seed()` in seed_generator.py to merge `[field_docs]` from the manual overlay (dict update, manual wins).

### Task 2: Add transfer control aliases + `.isolate()` convenience

**Files:** `seeds/seed.manual.toml`

Add aliases in `[builders.Agent.aliases]` section (requires adding this section to manual.toml):

- (No aliases needed — the names are too different from the targets to benefit from simple aliases)

Add a new `[[builders.Agent.extras]]` entry:

- `.isolate()` — sets both `disallow_transfer_to_parent=True` and `disallow_transfer_to_peers=True`
  - behavior: `dual_field_set` or `runtime_helper`
  - This is the most impactful DX win — every specialist agent needs this
  - Implementation: new helper function in `_helpers.py` that sets both config keys

### Task 3: Create structured data user guide

**File:** `docs/user-guide/structured-data.md`

Sections:

1. **Overview** — Why structured outputs matter (type-safe pipelines, state key access, downstream consumption)
1. **output_key / .outputs()** — Store agent response in session state, access from downstream agents via `{key}` in instructions
1. **output_schema / @ operator** — Pydantic models as output contracts, how the LLM is constrained, tool limitation
1. **input_schema** — When agents are used as tools, define expected input structure
1. **State access patterns** — How Pydantic model properties map to state keys, accessing structured data in downstream agents
1. **Complete example** — Multi-agent pipeline where data flows through typed schemas

### Task 4: Create transfer control user guide

**File:** `docs/user-guide/transfer-control.md`

Sections:

1. **Overview** — Agent transfer in ADK (parent→child, child→parent, peer-to-peer)
1. **Control flags** — `disallow_transfer_to_parent`, `disallow_transfer_to_peers`, and `.isolate()`
1. **Control matrix** — Table showing all flag combinations and resulting behavior
1. **Common patterns** — Coordinator vs specialist, hub-and-spoke, sequential handoff
1. **Flow selection** — How ADK picks SingleFlow vs AutoFlow based on flags
1. **Complete example** — Customer service system with coordinator + isolated specialists

### Task 5: Add cookbook examples (53 + 54)

**Files:** `examples/cookbook/53_structured_schemas.py`, `examples/cookbook/54_transfer_control.py`

**53_structured_schemas.py** — E.g. "Insurance Claim Processing: Structured Data Pipeline"

- Pydantic models for claim intake, assessment, payout
- Uses output_schema + output_key to flow typed data through pipeline
- Shows native ADK vs fluent side-by-side
- Demonstrates accessing schema fields in downstream agents

**54_transfer_control.py** — E.g. "Customer Service Hub: Transfer Control Patterns"

- Coordinator agent that can transfer to specialists
- Specialist agents with `.isolate()` that complete their task and return
- Shows the control matrix in practice
- Native vs fluent comparison

### Task 6: Implement `.isolate()` helper

**Files:** `src/adk_fluent/_helpers.py` (add helper), `seeds/seed.manual.toml` (add extra entry)

The `.isolate()` method needs a helper function. Options:

- A: New behavior type `dual_field_set` in the generator
- B: Simple `runtime_helper` that modifies `_config` directly

Option B is simpler — add a helper that sets both config keys:

```python
def _isolate_agent(builder):
    builder._config["disallow_transfer_to_parent"] = True
    builder._config["disallow_transfer_to_peers"] = True
    return builder
```

Then the seed entry uses `behavior = "runtime_helper"` with `helper_func = "_isolate_agent"`.

### Task 7: Regenerate code + docs, update toctree

**Files:** Generated files, `docs/user-guide/index.md`

1. Run `just seed` to regenerate seed.toml with merged field_docs
1. Run `just generate` to regenerate agent.py, agent.pyi, config.py, config.pyi with:
   - New field_docs in docstrings
   - New `.isolate()` method
1. Run `just docs` to regenerate API documentation
1. Update `docs/user-guide/index.md` toctree to include `structured-data` and `transfer-control`

### Task 8: Run tests + commit

Run full test suite to verify nothing breaks. Commit all changes.

## Order

Tasks 1, 2, 6 are interdependent (seeds → helpers → codegen) — do sequentially.
Tasks 3, 4, 5 are independent docs/cookbooks — can parallelize after Task 7 generates code.

Execution order: 1 → 6 → 2 → 7 → (3 | 4 | 5) → 8
