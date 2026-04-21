---
name: adk-fluent-dev-guide
description: >
  ALWAYS ACTIVE — read at the start of any agent development session with adk-fluent.
  Development lifecycle and coding guidelines — spec-driven workflow, phase-based
  development, model selection, and troubleshooting. Use for building agents,
  not for developing the library itself.
metadata:
  license: Apache-2.0
  author: vamsiramakrishnan
  version: "0.13.5"
---

# adk-fluent Development Workflow & Guidelines

> **Building agents with adk-fluent.** For developing the library itself,
> use `/develop-feature`. For API reference, use `/cheatsheet`.

## Session Continuity

If this is a long session, re-read the relevant skill before each phase —
`/cheatsheet` before writing code, `/eval-agent` before running evals,
`/deploy-agent` before deploying, `/scaffold-project` before scaffolding.
Context compaction may have dropped earlier skill content.

---

## DESIGN_SPEC.md — Your Primary Reference

**IMPORTANT**: If `DESIGN_SPEC.md` exists in this project, it is your primary
source of truth.

Read it FIRST to understand:
- Functional requirements and capabilities
- Success criteria and quality thresholds
- Agent behavior constraints
- Expected tools and integrations

**The spec is your contract.** All implementation decisions should align with it.

---

## Phase 1: Understand the Spec

Before writing any code:
1. Read `DESIGN_SPEC.md` thoroughly
2. Identify the core capabilities required
3. Note any constraints or things the agent should NOT do
4. Understand success criteria for evaluation

---

## Phase 2: Design the Agent Topology

Use `/architect-agents` for complex multi-agent systems. Quick decision tree:

| Need | Pattern |
|------|---------|
| Single task | `Agent("name", "model").instruct("...")` |
| Steps in order | `a >> b >> c` |
| Steps in parallel | `a \| b \| c` |
| Iterative refinement | `review_loop(worker, reviewer)` |
| Rule-based routing | `Route("key").eq("val", agent)` |
| Graceful degradation | `fast // strong` |
| LLM-decided routing | `.sub_agent(specialist.isolate())` |

**Rules of thumb:**
- Use deterministic routing (`Route`) over LLM routing when decisions are rule-based
- Use `.isolate()` on specialist agents by default
- Set `.describe()` on all sub-agents (helps the coordinator pick the right one)
- Use `.agent_tool()` when the parent should stay in control
- Use `.sub_agent()` when the child should take over completely

---

## Phase 3: Build and Implement

### Agent implementation pattern

```python
from adk_fluent import Agent, Pipeline, S, C, P

# 1. Define tools
def search(query: str) -> str:
    """Search for information."""
    return f"Results for {query}"

# 2. Build agent with fluent API
agent = (
    Agent("researcher", "gemini-2.5-flash")
    .instruct(
        P.role("Senior researcher")
        | P.task("Research the given topic thoroughly")
        | P.constraint("Cite sources", "Be factual")
        | P.format("Return findings as bullet points")
    )
    .tool(search)
    .writes("findings")
    .context(C.window(n=5))
    .guard(G.length(max=2000))
)
```

### Interactive testing during development

```bash
# Option 1: adk web (requires .build() into ADK agent)
adk web .

# Option 2: Quick test with mock
python -c "
from adk_fluent import Agent
agent = Agent('test', 'gemini-2.5-flash').instruct('Hello').mock(['Hi!'])
print(agent.ask('test'))
"

# Option 3: Inline smoke test
agent.mock(["expected"]).test("input", contains="expected")
```

### Code preservation rules

When modifying existing agents:
- **NEVER change the model** unless explicitly asked
- Only modify the targeted code segments
- Preserve all surrounding configuration, comments, and formatting
- If a model returns a 404, fix `GOOGLE_CLOUD_LOCATION`, not the model name

### Model selection

For **new** agents (not modifying existing):
- Default: `gemini-2.5-flash` (fast, cheap)
- Complex reasoning: `gemini-2.5-pro`
- Never use older models unless explicitly requested

---

## Phase 4: Test

Use `/write-tests` for detailed guidance. Quick checklist:

```python
# Mock-based tests (required for CI)
def test_agent_basic():
    agent = Agent("test").instruct("Summarize.").mock(["Summary"])
    result = agent.ask("Some text")
    assert "Summary" in result

# Contract checking
from adk_fluent import check_contracts
pipeline = Agent("a").writes("x") >> Agent("b").reads("x")
assert not check_contracts(pipeline)

# Validation
assert not agent.validate()
```

**Tests (`pytest`) verify code correctness.** They do NOT verify agent behavior.
Always run evaluation (Phase 5) for behavioral validation.

```bash
uv run pytest tests/ -v --tb=short
```

---

## Phase 5: Evaluate

**This is the most important phase.** Use `/eval-agent` for detailed guidance.

```python
from adk_fluent import Agent, E

# Quick inline eval
agent.eval("What is 2+2?", expect="4")

# Full eval suite
suite = (
    E.suite(agent)
    .case("What is 2+2?", expect="4")
    .case("Summarize this text", rubrics=["Concise", "Accurate"])
    .criteria(E.semantic_match(threshold=0.7))
    .criteria(E.trajectory(match="in_order"))
)
report = suite.run()
report.print()
```

Or use the ADK CLI:

```bash
adk eval ./app evalset.json --config_file_path=eval_config.json --print_detailed_results
```

**Expect 5-10+ iterations.** Start with 1-2 cases, not a full suite.

### Eval-fix loop

1. Start small: 1-2 eval cases
2. Run eval
3. Read scores — identify failures
4. Fix prompts, tools, or instructions
5. Rerun eval
6. Repeat until passing
7. Then expand coverage

---

## Phase 6: Deploy

Once evaluation thresholds are met, use `/deploy-agent` for deployment guidance.

**IMPORTANT**: Never deploy without explicit human approval.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Import error | Use `from adk_fluent import ...`, never internal modules |
| `.ask()` raises RuntimeError | Use `.ask_async()` in async contexts (Jupyter, FastAPI) |
| `.build()` raises ValidationError | Run `agent.show()` and `agent.validate()` to inspect config |
| Pipeline data flow broken | Run `check_contracts(pipeline)` to find mismatched keys |
| Agent ignores context | Check `.context()` and `.reads()` — use `agent.show("llm")` to see what the LLM gets |
| Mock not working | Ensure enough mock responses are provided for all turns |
| Model 404 error | Fix `GOOGLE_CLOUD_LOCATION` (e.g., use `global`), not the model name |

### Deep debugging

```python
agent.show()             # Config summary (rich tree)
agent.show("llm")        # What the LLM sees
agent.show("data_flow")  # Five-concern view
agent.show("doctor")     # Full diagnostic
```

For builder-level debugging, use `/debug-builder`.

---

## Running Commands

- Always use `uv run` for Python commands: `uv run python script.py`
- Run `uv sync` before executing scripts
- Check `Makefile` and `justfile` for available project commands

---

## Best Practices

1. **Start simple** — single agent first, add complexity only when needed
2. **Use `.mock()`** in all tests — no API keys in CI
3. **Use `.validate()`** early — catch config errors before `.build()`
4. **Use `.show()`** often — understand what you've configured
5. **Use deterministic routing** when decisions are rule-based
6. **Use `.inject()`** for infrastructure deps
7. **Use `S.*` transforms** for data manipulation, not custom agents
8. **Use `C.none()`** for utility/background agents that don't need history
9. **Use `M.retry()`** instead of retry logic in tools
10. **Every `.build()` returns a real ADK object** — compatible with `adk web/run/deploy`
