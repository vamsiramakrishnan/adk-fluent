# Evaluation

:::{admonition} At a Glance
:class: tip

- E module provides three tiers: inline `.eval()`, `EvalSuite` for batch, `ComparisonReport` for A/B testing
- Custom criteria with `E.criterion()`, LLM-as-judge scoring, tool trajectory checks
- Use eval to catch quality regressions before they reach production
:::

adk-fluent wraps Google ADK's evaluation framework with a fluent `E` module, consistent with the other namespace modules (P, C, S, M, T, A). It provides three tiers of evaluation — inline, suite, and comparison — all composable with the `|` operator.

## Quick Start

```python
from adk_fluent import Agent, E

agent = Agent("math", "gemini-2.5-flash").instruct("You are a math tutor.")

# Inline: one-line smoke test
report = await agent.eval("What is 2+2?", expect="4").run()
assert report.ok
```

## Three Tiers

### Tier 1: Inline Evaluation

The fastest way to test a single prompt. Call `.eval()` directly on any agent builder:

```python
# With expected response (auto-selects response_match criterion)
report = await agent.eval("What is 2+2?", expect="4").run()

# With explicit criteria
report = await agent.eval(
    "Explain gravity",
    criteria=E.semantic_match(0.7)
).run()

print(report.summary())
```

### Tier 2: Evaluation Suites

For structured evaluation with multiple test cases and criteria:

```python
report = await (
    E.suite(agent)
    .case("What is 2+2?", expect="4")
    .case("What is 3*5?", expect="15")
    .case("Factor x^2-1", expect="(x+1)(x-1)")
    .criteria(E.response_match() | E.safety())
    .num_runs(3)
    .run()
)

print(report.summary())
# Eval Report
# ========================================
#   response_match_score: 0.850 (threshold: 0.8) [PASS]
#   safety_v1: 1.000 (threshold: 1.0) [PASS]
# ========================================
# Overall: PASSED
```

You can also use `.eval_suite()` on the agent directly:

```python
report = await (
    agent.eval_suite()
    .case("What is 2+2?", expect="4")
    .criteria(E.trajectory() | E.response_match())
    .run()
)
```

### Tier 3: Model Comparison

Compare multiple agents (or the same agent with different models) side-by-side:

```python
fast = Agent("fast", "gemini-2.5-flash").instruct("Answer concisely.")
strong = Agent("strong", "gemini-2.5-pro").instruct("Answer thoroughly.")

report = await (
    E.compare(fast, strong)
    .case("Explain quantum entanglement", expect="correlated particles")
    .case("What causes tides?", expect="gravitational pull of the moon")
    .criteria(E.semantic_match() | E.safety())
    .run()
)

print(report.summary())
print(f"Winner: {report.winner}")
print(report.ranked())  # [("strong", 0.92), ("fast", 0.78)]
```

## Criteria

Criteria are composable evaluation metrics. Combine them with `|`:

```python
criteria = E.trajectory() | E.response_match() | E.safety()
```

### Built-in Criteria

| Criterion            | Metric                                   | Description                                       |
| -------------------- | ---------------------------------------- | ------------------------------------------------- |
| `E.trajectory()`     | `tool_trajectory_avg_score`              | Tool call sequence matches expected trajectory    |
| `E.response_match()` | `response_match_score`                   | ROUGE-1 text similarity against expected response |
| `E.semantic_match()` | `final_response_match_v2`                | LLM-as-a-judge semantic evaluation                |
| `E.hallucination()`  | `hallucinations_v1`                      | Groundedness and factual accuracy                 |
| `E.safety()`         | `safety_v1`                              | Response safety standards                         |
| `E.rubric()`         | `rubric_based_final_response_quality_v1` | Custom rubric-based quality                       |
| `E.tool_rubric()`    | `rubric_based_tool_use_quality_v1`       | Custom rubric for tool usage                      |
| `E.custom()`         | user-defined                             | User-provided scoring function                    |

### Configuring Criteria

Each criterion accepts a `threshold` parameter (0.0 to 1.0):

```python
E.response_match(0.9)          # Require 90% ROUGE-1 match
E.trajectory(0.8, match="in_order")  # 80%, in-order matching
E.semantic_match(0.7, judge_model="gemini-2.5-pro")
E.hallucination(0.9, check_intermediate=True)
```

### Custom Criteria

Define your own scoring function:

```python
def keyword_check(invocation, expected):
    text = invocation.final_response.parts[0].text
    return 1.0 if "quantum" in text.lower() else 0.0

criteria = E.custom("keyword_present", keyword_check, threshold=1.0)
```

### Rubric-Based Evaluation

Use natural-language rubrics for qualitative assessment:

```python
criteria = E.rubric(
    "Response must cite at least one source",
    "Response must be under 200 words",
    threshold=0.7,
)
```

## Eval Cases

Cases define what to test. Each case specifies a prompt and expected outcomes:

```python
suite = (
    E.suite(agent)
    # Simple response check
    .case("What is 2+2?", expect="4")

    # Tool trajectory check
    .case(
        "Search for recent news about AI",
        tools=[("google_search", {"query": "AI news"})],
    )

    # Rubric-based quality check
    .case(
        "Write a haiku about coding",
        rubrics=["Must follow 5-7-5 syllable structure"],
    )

    # Expected final state
    .case(
        "Classify this as positive or negative: Great product!",
        state={"sentiment": "positive"},
    )
)
```

You can also create standalone cases:

```python
case = E.case("What is 2+2?", expect="4")
```

## Reports

### EvalReport

The result of running an evaluation suite:

```python
report = await suite.run()

report.ok          # True if all metrics passed
report.scores      # {"response_match_score": 0.85, "safety_v1": 1.0}
report.thresholds  # {"response_match_score": 0.8, "safety_v1": 1.0}
report.passed      # {"response_match_score": True, "safety_v1": True}
report.summary()   # Formatted text table
```

### ComparisonReport

The result of comparing multiple agents:

```python
report = await comparison.run()

report.winner              # "strong" (highest avg score)
report.ranked()            # [("strong", 0.92), ("fast", 0.78)]
report.agent_reports       # {"fast": EvalReport, "strong": EvalReport}
report.summary()           # Formatted comparison table
```

## File-Based Eval Sets

Serialize eval suites to JSON for CI pipelines or sharing:

```python
# Save to file (ADK-compatible format)
(
    E.suite(agent)
    .case("What is 2+2?", expect="4")
    .case("What is 3*5?", expect="15")
    .criteria(E.response_match())
    .to_file("tests/math_eval.json")
)

# Load and run from file
suite = E.from_file("tests/math_eval.json", agent=agent)
report = await suite.run()
```

## User Simulation (Personas)

For multi-turn conversation testing, create scenarios with simulated user personas:

```python
scenario = E.scenario(
    start="Book a flight from SFO to JFK",
    plan="User wants economy class, next Friday, window seat",
    persona=E.persona.expert(),
)
```

### Built-in Personas

| Persona                 | Description                                     |
| ----------------------- | ----------------------------------------------- |
| `E.persona.expert()`    | Knows exactly what they want, professional tone |
| `E.persona.novice()`    | Relies on the agent, conversational tone        |
| `E.persona.evaluator()` | Assessing agent capabilities                    |

### Custom Personas

```python
persona = E.persona.custom(
    persona_id="impatient_user",
    description="A user who wants quick answers and gets frustrated with long responses",
    behaviors=["Sends short messages", "Asks for summaries"],
)
```

> **Note:** Personas require `google-adk >= 1.26.0`.

## Integration with Other Modules

The E module composes naturally with other adk-fluent namespaces:

```python
from adk_fluent import Agent, E, C, S

# Eval an agent with context constraints
agent = Agent("helper", "gemini-2.5-flash").context(C.window(5))
report = await agent.eval("What was my first question?", expect="...").run()

# Assert state after agent runs
report = await (
    E.suite(agent)
    .case("Classify: great product!", state={"sentiment": "positive"})
    .criteria(E.response_match())
    .run()
)
```

## pytest Integration

Use evaluations in your test suite:

```python
import pytest
from adk_fluent import Agent, E

agent = Agent("math", "gemini-2.5-flash").instruct("You are a math tutor.")

@pytest.mark.asyncio
async def test_math_accuracy():
    report = await (
        agent.eval_suite()
        .case("What is 2+2?", expect="4")
        .case("What is 10/2?", expect="5")
        .criteria(E.response_match(0.8))
        .run()
    )
    assert report.ok, report.summary()

@pytest.mark.asyncio
async def test_tool_trajectory():
    search_agent = Agent("searcher", "gemini-2.5-flash").tool(search_fn)
    report = await (
        search_agent.eval(
            "Find news about AI",
            criteria=E.trajectory(),
        )
        .case("Find news about AI", tools=[("search", {"query": "AI news"})])
        .run()
    )
    assert report.ok

@pytest.mark.asyncio
async def test_model_comparison():
    fast = Agent("fast", "gemini-2.5-flash").instruct("Be concise.")
    strong = Agent("strong", "gemini-2.5-pro").instruct("Be thorough.")

    report = await (
        E.compare(fast, strong)
        .case("Explain gravity", expect="gravitational force")
        .criteria(E.semantic_match())
        .run()
    )
    assert report.winner is not None
```

## Suite Configuration

Fine-tune evaluation execution:

```python
suite = (
    E.suite(agent)
    .name("math_eval_v2")
    .description("Math tutor accuracy evaluation")
    .case("What is 2+2?", expect="4")
    .criteria(E.response_match())
    .threshold("response_match_score", 0.9)  # Override per-metric
    .num_runs(5)                               # Statistical significance
)

report = await suite.run()
```

## API Summary

### E (static namespace)

| Method               | Returns                | Description                          |
| -------------------- | ---------------------- | ------------------------------------ |
| `E.trajectory()`     | `EComposite`           | Tool trajectory matching criterion   |
| `E.response_match()` | `EComposite`           | ROUGE-1 response match criterion     |
| `E.semantic_match()` | `EComposite`           | LLM-as-a-judge semantic matching     |
| `E.hallucination()`  | `EComposite`           | Hallucination detection              |
| `E.safety()`         | `EComposite`           | Safety evaluation                    |
| `E.rubric()`         | `EComposite`           | Custom rubric-based quality          |
| `E.tool_rubric()`    | `EComposite`           | Rubric for tool usage quality        |
| `E.custom()`         | `EComposite`           | User-defined custom metric           |
| `E.case()`           | `ECase`                | Create a standalone eval case        |
| `E.scenario()`       | `ConversationScenario` | Create a user simulation scenario    |
| `E.suite()`          | `EvalSuite`            | Create an evaluation suite           |
| `E.compare()`        | `ComparisonSuite`      | Compare multiple agents              |
| `E.from_file()`      | `EvalSuite`            | Load eval set from JSON file         |
| `E.persona`          | `EPersona`             | Namespace for prebuilt user personas |

### Agent eval methods

| Method                    | Returns     | Description                               |
| ------------------------- | ----------- | ----------------------------------------- |
| `agent.eval(prompt, ...)` | `EvalSuite` | Inline evaluation with a single case      |
| `agent.eval_suite()`      | `EvalSuite` | Create an empty suite bound to this agent |

### EvalSuite (builder)

| Method                      | Returns      | Description                 |
| --------------------------- | ------------ | --------------------------- |
| `.case(prompt, ...)`        | `EvalSuite`  | Add an evaluation case      |
| `.criteria(composite)`      | `EvalSuite`  | Set evaluation criteria     |
| `.rubric(text)`             | `EvalSuite`  | Add a rubric to all cases   |
| `.threshold(metric, value)` | `EvalSuite`  | Override a metric threshold |
| `.num_runs(n)`              | `EvalSuite`  | Set number of eval runs     |
| `.name(text)`               | `EvalSuite`  | Set suite name              |
| `.description(text)`        | `EvalSuite`  | Set suite description       |
| `.to_file(path)`            | `EvalSuite`  | Serialize to JSON file      |
| `.run()`                    | `EvalReport` | Run the evaluation (async)  |
