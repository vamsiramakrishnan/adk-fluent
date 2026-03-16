# Design: Dynamic Topologies (Graphs that Write Graphs)

**Issue:** #16
**Status:** Design spec — not yet implemented
**Date:** 2026-03-16

## Problem

adk-fluent's core is static compilation: you define `A >> Route >> B >> C`
and call `.build()`. But some use cases require the LLM to determine the
execution plan at runtime — e.g., a planner agent that decides which tools
to chain based on the user's request.

Currently, developers must build massive Route trees anticipating every
combination, or write custom Python functions to instantiate agents on the
fly. Both are poor for maintenance and observability.

## Goals

- Allow an agent to output an IR tree (execution plan) instead of just text
- Framework parses the generated plan and splices it into the live graph
- Full observability — dynamic branches appear in traces and diagrams
- Safety constraints — allowlists for tools, max depth, max steps
- Contract checking on dynamically generated subgraphs

## Non-Goals

- Arbitrary code execution (the planner outputs IR, not Python)
- Self-modifying agents (the planner's own topology is static)
- Replacing Route for deterministic cases (Route remains preferred)

## Proposed API

### Agent-side

```python
from adk_fluent import Agent, DynamicPlan

planner = (
    Agent("planner", "gemini-2.5-pro")
    .instruct("Generate a multi-step execution plan from the available tools.")
    .outputs_graph(
        allowed_tools=[search_web, calculate_taxes, write_report],
        allowed_models=["gemini-2.5-flash"],
        max_steps=5,
        max_depth=2,
    )
)

pipeline = intake >> planner >> summarizer
```

### Plan schema

The planner LLM outputs structured JSON matching `DynamicPlan`:

```json
{
  "steps": [
    {"agent": "step_1", "tool": "search_web", "instruction": "Search for tax rates"},
    {"agent": "step_2", "tool": "calculate_taxes", "instruction": "Calculate using {step_1}"},
    {"agent": "step_3", "tool": "write_report", "instruction": "Write report from {step_2}"}
  ]
}
```

The framework validates the plan against the allowlist and converts it to
an IR `SequenceNode` containing `AgentNode` entries.

### Programmatic plan construction

```python
# Plans can also be built programmatically in tool functions
def custom_planner(query: str) -> DynamicPlan:
    if "tax" in query:
        return DynamicPlan(steps=[
            PlanStep(tool=calculate_taxes, instruction="Calculate taxes"),
            PlanStep(tool=write_report, instruction="Write report"),
        ])
    return DynamicPlan(steps=[
        PlanStep(tool=search_web, instruction="Search for info"),
    ])
```

## Architecture

### IR integration

New IR node: `DynamicNode`

```
DynamicNode
  planner: AgentNode           # the agent that generates the plan
  allowed_tools: list[str]     # tool function allowlist
  allowed_models: list[str]    # model allowlist
  max_steps: int               # safety limit
  max_depth: int               # nesting depth limit
  fallback: Optional[IRNode]   # if plan generation fails
```

### Compilation

`DynamicNode` compiles to a special ADK agent that:
1. Runs the planner agent with `.returns(DynamicPlan)` (structured output)
2. Validates the plan against constraints
3. Converts the plan to a temporary `SequenceNode` IR tree
4. Compiles the IR tree to native ADK agents
5. Executes the compiled subgraph inline

### Plan validation

Before execution, the framework validates:
- All referenced tools are in the allowlist
- All referenced models are in the allowlist
- Step count does not exceed `max_steps`
- Nesting depth does not exceed `max_depth`
- No circular dependencies between steps
- State key references resolve to upstream outputs

Validation failures raise `DynamicPlanError` with clear diagnostics.

### Observability

- Dynamic subgraphs appear in Mermaid diagrams with a dashed border
- Trace spans include `dynamic=true` attribute
- `.explain()` shows the plan template and constraints
- Event stream includes `PlanGeneratedEvent` with the validated plan

### Data flow

- Planner agent receives upstream state (normal data flow)
- Each dynamic step can reference outputs of previous steps via `{step_n}`
- Final step's output flows downstream as the DynamicNode's output
- `.writes()` on the DynamicNode captures the final step's output

## Safety model

Dynamic topologies introduce code-generation-adjacent risks:

1. **Tool allowlist** — only pre-registered tools can be referenced
2. **Model allowlist** — only approved models can be used
3. **Step limits** — hard cap on plan complexity
4. **Depth limits** — prevent recursive plan generation
5. **No code execution** — plans are declarative IR, not Python
6. **Validation before execution** — plans are checked before any step runs

## Dependencies

- Structured output (`.returns()`) for plan extraction
- IR compilation infrastructure
- Existing tool registry

## Testing strategy

- Unit tests: DynamicPlan schema validation, allowlist enforcement
- Integration tests: planner generates plan, framework executes it
- Safety tests: verify rejection of disallowed tools, exceeded limits
- Mock tests: planner with `.mock()` returning predetermined plans

## Open questions

1. Should dynamic plans support parallel branches (fan-out), or only sequential?
2. How to handle plan generation failure — fallback agent, retry, or error?
3. Should plans be cacheable (same input → same plan → skip re-planning)?
4. Can a dynamic step itself be a planner (recursive planning)? If so, depth limits are critical.
5. Should the plan be presented to the user for approval before execution (integration with H module)?

## Estimated scope

- New file: `src/adk_fluent/_dynamic.py` (~400 lines)
- IR node addition: `DynamicNode` in `_ir.py`
- Plan schema: `DynamicPlan`, `PlanStep` Pydantic models (~80 lines)
- Compilation support in `compile/` (~150 lines)
- Agent builder method: `.outputs_graph()` in seed.manual.toml
- Tests: ~300 lines
- Docs: user guide section + cookbook example
