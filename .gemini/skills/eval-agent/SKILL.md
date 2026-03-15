---
name: eval-agent
description: >
  MUST READ before running any agent evaluation with adk-fluent.
  Evaluation methodology — E namespace, eval suites, criteria, LLM-as-judge,
  tool trajectory scoring, and common failure causes. Use when evaluating
  agent quality, writing eval suites, or debugging eval results.
  Do NOT use for API code patterns (use cheatsheet) or deployment (use deploy-agent).
allowed-tools: Bash, Read, Glob, Grep
---

# adk-fluent Evaluation Guide

> **adk-fluent wraps native ADK evaluation** with the E namespace and fluent
> builders. Every eval produces standard ADK-compatible evalsets and configs.

## Reference Files

| File | Contents |
|------|----------|
| [`../_shared/references/namespace-methods.md`](../_shared/references/namespace-methods.md) | E namespace — all eval methods and signatures |

---

## Quick Start

### Inline eval (fastest)

```python
from adk_fluent import Agent

agent = Agent("helper", "gemini-2.5-flash").instruct("You answer math questions.")

# Single case
agent.eval("What is 2+2?", expect="4")
```

### Eval suite (comprehensive)

```python
from adk_fluent import Agent, E

agent = Agent("helper", "gemini-2.5-flash").instruct("You answer questions.")

suite = (
    E.suite(agent)
    .case("What is 2+2?", expect="4")
    .case("What is the capital of France?", expect="Paris")
    .criteria(E.semantic_match(threshold=0.7))
    .criteria(E.trajectory(match="in_order"))
)

report = suite.run()
report.print()
```

### Compare agents/models

```python
comparison = (
    E.compare(
        Agent("fast", "gemini-2.5-flash").instruct("Answer concisely."),
        Agent("strong", "gemini-2.5-pro").instruct("Answer thoroughly."),
    )
    .case("Explain quantum computing", expect="...")
    .criteria(E.semantic_match(threshold=0.5))
)
comparison.run().print()
```

---

## The Eval-Fix Loop

Evaluation is iterative. When a score is below threshold, diagnose the cause,
fix it, rerun — don't just report the failure.

### How to iterate

1. **Start small**: 1-2 eval cases, not the full suite
2. **Run eval**: `suite.run()` or `adk eval`
3. **Read the scores** — identify what failed and why
4. **Fix the code** — adjust prompts, tool logic, instructions, or the evalset
5. **Rerun eval** — verify the fix worked
6. **Repeat steps 3-5** until the case passes
7. **Only then** add more eval cases and expand coverage

**Expect 5-10+ iterations.** This is normal.

---

## Choosing the Right Criteria

| Goal | Criterion | adk-fluent |
|------|-----------|------------|
| Regression testing (fast, deterministic) | Tool trajectory + response match | `E.trajectory() + E.response_match()` |
| Semantic response correctness | LLM-as-judge semantic match | `E.semantic_match(threshold=0.7)` |
| Response quality without reference | Rubric-based evaluation | `E.rubric("Concise", "Accurate")` |
| Validate tool usage reasoning | Rubric-based tool quality | `E.tool_rubric("Uses search before answering")` |
| Detect hallucinated claims | Hallucination detection | `E.hallucination(threshold=0.8)` |
| Safety compliance | Safety evaluation | `E.safety()` |
| Custom business logic | Custom metric | `E.custom("metric_name", my_fn)` |

### Criteria composition

```python
# Combine multiple criteria
suite = (
    E.suite(agent)
    .case("prompt", expect="answer")
    .criteria(E.trajectory(threshold=1.0, match="in_order"))
    .criteria(E.semantic_match(threshold=0.7))
    .criteria(E.rubric("Professional", "Helpful", threshold=0.8))
    .criteria(E.hallucination(threshold=0.8))
)
```

---

## E Namespace — Full Reference

### Cases

```python
E.case("prompt", expect="answer")                      # Basic case
E.case("prompt", tools=[("search", {"q": "..."})])     # With tool trajectory
E.case("prompt", rubrics=["Clear", "Accurate"])         # With rubrics
E.case("prompt", state={"key": "value"})                # With initial state
```

### Criteria

```python
E.trajectory(threshold=1.0, match="exact")              # Tool call matching
E.response_match(threshold=0.8)                          # ROUGE-1 match
E.semantic_match(threshold=0.5, judge_model="gemini-2.5-flash")  # LLM judge
E.rubric("text1", "text2", threshold=0.5)                # Response quality
E.tool_rubric("text1", threshold=0.5)                    # Tool use quality
E.hallucination(threshold=0.8)                           # Hallucination check
E.safety(threshold=1.0)                                  # Safety check
E.custom("name", lambda prompt, response: 0.9)          # Custom metric
```

### Suites and comparison

```python
E.suite(agent)                                           # Create eval suite
E.compare(agent1, agent2)                                # Compare agents
E.from_file("evalset.json")                              # Load from file
E.from_dir("eval/")                                      # Load from directory
E.gate(criteria, threshold=0.8)                          # Quality gate
```

### User simulation

```python
E.scenario("Hello, I need help with billing",
           plan="Ask about account, then request refund",
           persona=E.persona.frustrated())
```

---

## ADK CLI Evaluation

adk-fluent agents are native ADK objects, so `adk eval` works directly:

```bash
# Run evaluation
adk eval ./app evalset.json --config_file_path=eval_config.json --print_detailed_results

# Run specific cases
adk eval ./app evalset.json:eval_1,eval_2

# With GCS storage
adk eval ./app evalset.json --eval_storage_uri gs://bucket/evals
```

### eval_config.json format

```json
{
  "criteria": {
    "tool_trajectory_avg_score": {
      "threshold": 1.0,
      "match_type": "IN_ORDER"
    },
    "final_response_match_v2": {
      "threshold": 0.8
    },
    "rubric_based_final_response_quality_v1": {
      "threshold": 0.8,
      "rubrics": [
        {
          "rubric_id": "quality",
          "rubric_content": { "text_property": "Response must be helpful." }
        }
      ]
    }
  }
}
```

### evalset.json format

```json
{
  "eval_set_id": "my_eval_set",
  "eval_cases": [
    {
      "eval_id": "test_1",
      "conversation": [
        {
          "invocation_id": "inv_1",
          "user_content": { "parts": [{ "text": "Find flights to NYC" }] },
          "final_response": {
            "role": "model",
            "parts": [{ "text": "Found a flight for $500." }]
          },
          "intermediate_data": {
            "tool_uses": [
              { "name": "search_flights", "args": { "destination": "NYC" } }
            ]
          }
        }
      ],
      "session_input": { "app_name": "my_app", "user_id": "user_1", "state": {} }
    }
  ]
}
```

---

## What to Fix When Scores Fail

| Failure | What to change |
|---------|---------------|
| `trajectory` score low | Fix agent instructions (tool ordering), update evalset `tool_uses`, or switch to `in_order`/`any_order` match type |
| `response_match` score low | Adjust agent instruction wording, or relax the expected response |
| `semantic_match` score low | Refine agent instructions, or adjust expected response |
| `rubric` score low | Refine agent instructions to address the specific rubric |
| `hallucination` score low | Tighten instructions to stay grounded in tool output |
| Agent calls wrong tools | Fix tool descriptions, agent instructions, or tool_config |
| Agent calls extra tools | Use `in_order` match type, add stop instructions, or use `tool_rubric` |

---

## Common Gotchas

### The Proactivity Trajectory Gap

LLMs often call extra tools not asked for. This causes `trajectory` failures
with `exact` match. Solutions:

1. Use `match="in_order"` or `match="any_order"` — tolerates extra calls
2. Include ALL tools the agent might call in expected trajectory
3. Use `E.tool_rubric()` instead of trajectory matching
4. Add strict stop instructions

### Multi-turn tool_uses

Trajectory evaluates each turn. Specify expected tool calls for ALL turns:

```python
E.case("Find a flight", tools=[("search_flights", {"dest": "NYC"})]),
E.case("Book the first one", tools=[("book_flight", {"id": "1"})]),
```

### App name must match directory name

```python
# CORRECT — matches the "app" directory
app = App(root_agent=root_agent, name="app")

# WRONG — causes "Session not found"
app = App(root_agent=root_agent, name="my_agent")
```

### State type mismatches in evalsets

```json
// WRONG — string instead of list
"state": { "history": "" }

// CORRECT — matches Python type
"state": { "history": [] }
```

### Score fluctuates between runs

Set `temperature=0` via `.generate_content_config()` or use rubric-based eval
which is more tolerant of variation.

---

## Debugging Example

User says: "trajectory score is 0, what's wrong?"

1. Check if agent uses `google_search` (model-internal tool) — trajectory can't track it
2. Check if using `exact` match and agent calls extra tools — try `in_order`
3. Compare expected `tool_uses` with actual agent behavior
4. Fix mismatch (update evalset or agent instructions)
