# Module: eval

> `from adk_fluent import E`

Fluent evaluation composition. Consistent with P, C, S, M, T, A modules.

## Quick Reference

| Method                                                                                     | Returns           | Description                                        |
| ------------------------------------------------------------------------------------------ | ----------------- | -------------------------------------------------- |
| `E.trajectory(threshold=1.0, match='exact')`                                               | `EComposite`      | Tool trajectory matching criterion                 |
| `E.response_match(threshold=0.8)`                                                          | `EComposite`      | ROUGE-1 response match criterion                   |
| `E.semantic_match(threshold=0.5, judge_model='gemini-2.5-flash')`                          | `EComposite`      | LLM-as-a-judge semantic matching criterion         |
| `E.hallucination(threshold=0.8, judge_model='gemini-2.5-flash', check_intermediate=False)` | `EComposite`      | Hallucination detection criterion                  |
| `E.safety(threshold=1.0)`                                                                  | `EComposite`      | Safety evaluation criterion                        |
| `E.rubric(*texts, threshold=0.5, judge_model='gemini-2.5-flash')`                          | `EComposite`      | Rubric-based response quality criterion            |
| `E.tool_rubric(*texts, threshold=0.5, judge_model='gemini-2.5-flash')`                     | `EComposite`      | Rubric-based tool use quality criterion            |
| `E.custom(name, fn, threshold=0.5)`                                                        | `EComposite`      | User-defined custom metric                         |
| `E.case(prompt, expect=None, tools=None, rubrics=None, state=None)`                        | `ECase`           | Create a standalone eval case                      |
| `E.scenario(start, plan, persona=None)`                                                    | `Any`             | Create a conversation scenario for user simulation |
| `E.suite(agent)`                                                                           | `EvalSuite`       | Create an evaluation suite for an agent builder    |
| `E.compare(*agents)`                                                                       | `ComparisonSuite` | Compare multiple agents on the same eval set       |
| `E.from_file(path)`                                                                        | `Any`             | Load an eval set from a JSON file                  |
| `E.from_dir(path)`                                                                         | `list[Any]`       | Load all eval sets from a directory                |
| `E.gate(criteria, threshold=None)`                                                         | `Any`             | Create a quality gate for use in pipelines         |

## Criteria factories

### `E.trajectory(threshold: float = 1.0, *, match: str = exact) -> EComposite`

Tool trajectory matching criterion.

Checks that the agent's tool calls match the expected trajectory.

**Args:**

- **`threshold`**: Score threshold (0.0 to 1.0). Default 1.0 (exact match).
- **`match`**: Match type — `"exact"`, `"in_order"`, or `"any_order"`.

Usage:
E.trajectory() # exact match, threshold 1.0
E.trajectory(0.8, match="in_order") # in-order, 80% threshold

**Parameters:**

- `threshold` (*float*) — default: `1.0`
- `match` (*str*) — default: `'exact'`

### `E.response_match(threshold: float = 0.8) -> EComposite`

ROUGE-1 response match criterion.

Compares agent's response against expected text using ROUGE-1 scoring.

**Args:**

- **`threshold`**: Minimum ROUGE-1 score to pass. Default 0.8.

Usage:
E.response_match() # 80% threshold
E.response_match(0.9) # 90% threshold

**Parameters:**

- `threshold` (*float*) — default: `0.8`

### `E.semantic_match(threshold: float = 0.5, *, judge_model: str = gemini-2.5-flash) -> EComposite`

LLM-as-a-judge semantic matching criterion.

Uses a judge LLM to evaluate whether the response semantically matches
the expected output.

**Args:**

- **`threshold`**: Minimum score to pass. Default 0.5.
- **`judge_model`**: Model to use as judge. Default `"gemini-2.5-flash"`.

Usage:
E.semantic_match() # defaults
E.semantic_match(0.7, judge_model="gemini-2.5-pro")

**Parameters:**

- `threshold` (*float*) — default: `0.5`
- `judge_model` (*str*) — default: `'gemini-2.5-flash'`

### `E.hallucination(threshold: float = 0.8, *, judge_model: str = gemini-2.5-flash, check_intermediate: bool = False) -> EComposite`

Hallucination detection criterion.

Evaluates whether the agent's response is grounded and factual.

**Args:**

- **`threshold`**: Minimum groundedness score. Default 0.8.
- **`judge_model`**: Model to use as judge.
- **`check_intermediate`**: Also check intermediate NL responses.

Usage:
E.hallucination() # defaults
E.hallucination(0.9, check_intermediate=True)

**Parameters:**

- `threshold` (*float*) — default: `0.8`
- `judge_model` (*str*) — default: `'gemini-2.5-flash'`
- `check_intermediate` (*bool*) — default: `False`

### `E.safety(threshold: float = 1.0) -> EComposite`

Safety evaluation criterion.

Checks that the agent's response meets safety standards.

**Args:**

- **`threshold`**: Minimum safety score. Default 1.0 (must be fully safe).

**Parameters:**

- `threshold` (*float*) — default: `1.0`

### `E.rubric(*texts: str, threshold: float = 0.5, judge_model: str = gemini-2.5-flash) -> EComposite`

Rubric-based response quality criterion.

Uses custom rubrics to evaluate the quality of agent responses.

**Args:**

- **`texts`**: One or more rubric text strings.
- **`threshold`**: Minimum quality score. Default 0.5.
- **`judge_model`**: Model to use as judge.

Usage:
E.rubric("Response must be concise")
E.rubric("Must cite sources", "Must be factual", threshold=0.7)

**Parameters:**

- `*texts` (*str*)
- `threshold` (*float*) — default: `0.5`
- `judge_model` (*str*) — default: `'gemini-2.5-flash'`

### `E.tool_rubric(*texts: str, threshold: float = 0.5, judge_model: str = gemini-2.5-flash) -> EComposite`

Rubric-based tool use quality criterion.

Evaluates the quality of tool usage via custom rubrics.

**Args:**

- **`texts`**: One or more rubric text strings.
- **`threshold`**: Minimum quality score. Default 0.5.
- **`judge_model`**: Model to use as judge.

Usage:
E.tool_rubric("Must use search before answering")

**Parameters:**

- `*texts` (*str*)
- `threshold` (*float*) — default: `0.5`
- `judge_model` (*str*) — default: `'gemini-2.5-flash'`

### `E.custom(name: str, fn: Callable[..., float], *, threshold: float = 0.5) -> EComposite`

User-defined custom metric.

**Args:**

- **`name`**: Metric name (must be unique in the criteria set).
- **`fn`**: Callable that receives evaluation data and returns a float score.
- **`threshold`**: Minimum score to pass.

Usage:
def my_metric(invocation, expected):
return 1.0 if "keyword" in invocation.final_response else 0.0

```
E.custom("keyword_check", my_metric, threshold=1.0)
```

**Parameters:**

- `name` (*str*)
- `fn` (*Callable[..., float]*)
- `threshold` (*float*) — default: `0.5`

## Case factory

### `E.case(prompt: str, *, expect: str | None = None, tools: list[tuple[str, dict[str, Any]]] | None = None, rubrics: list[str] | None = None, state: dict[str, Any] | None = None) -> ECase`

Create a standalone eval case.

Usage:
case = E.case("What is 2+2?", expect="4")

**Parameters:**

- `prompt` (*str*)
- `expect` (*str | None*) — default: `None`
- `tools` (*list\[tuple\[str, dict[str, Any]\]\] | None*) — default: `None`
- `rubrics` (*list[str] | None*) — default: `None`
- `state` (*dict[str, Any] | None*) — default: `None`

## Scenario factory (user simulation)

### `E.scenario(start: str, plan: str, *, persona: Any | None = None) -> Any`

Create a conversation scenario for user simulation.

**Args:**

- **`start`**: The initial user prompt.
- **`plan`**: Description of the conversation plan/goal.
- **`persona`**: Optional `UserPersona` (from `E.persona.expert()` etc.).

Usage:
scenario = E.scenario(
start="Book a flight",
plan="User wants SFO to JFK next Friday, economy class",
persona=E.persona.expert(),
)

**Parameters:**

- `start` (*str*)
- `plan` (*str*)
- `persona` (*Any | None*) — default: `None`

## Suite factory

### `E.suite(agent: Any) -> EvalSuite`

Create an evaluation suite for an agent builder.

**Args:**

- **`agent`**: An agent builder (or built ADK agent).

Usage:
suite = E.suite(my_agent)
.case("prompt", expect="response")
.criteria(E.response_match())

```
report = await suite.run()
```

**Parameters:**

- `agent` (*Any*)

## Comparison factory

### `E.compare(*agents: Any) -> ComparisonSuite`

Compare multiple agents on the same eval set.

**Args:**

- **`agents`**: Two or more agent builders to compare.

Usage:
report = await (
E.compare(fast_agent, smart_agent)
.case("query", expect="answer")
.criteria(E.semantic_match())
.run()
)

**Parameters:**

- `*agents` (*Any*)

## File-based eval

### `E.from_file(path: str) -> Any`

Load an eval set from a JSON file.

**Args:**

- **`path`**: Path to the `.test.json` eval set file (ADK format).

**Returns:**

```
An ADK `EvalSet` instance.
```

**Parameters:**

- `path` (*str*)

### `E.from_dir(path: str) -> list[Any]`

Load all eval sets from a directory.

**Args:**

- **`path`**: Directory containing `.test.json` files.

**Returns:**

```
List of ADK `EvalSet` instances.
```

**Parameters:**

- `path` (*str*)

## Gate (quality threshold for pipelines)

### `E.gate(criteria: EComposite, *, threshold: float | None = None) -> Any`

Create a quality gate for use in pipelines.

The gate evaluates the preceding agent's output and blocks
propagation if the quality score falls below the threshold.

**Args:**

- **`criteria`**: Evaluation criteria to check.
- **`threshold`**: Override threshold (uses criterion default if None).

**Returns:**

```
A callable suitable for use with the `>>` operator.
```

Usage:
pipeline = agent >> E.gate(E.hallucination()) >> next_agent

**Parameters:**

- `criteria` (*EComposite*)
- `threshold` (*float | None*) — default: `None`

## Composition Operators

### `|` (compose (EComposite))

Combine evaluation criteria

## Types

| Type               | Description                                                |
| ------------------ | ---------------------------------------------------------- |
| `EComposite`       | Composable evaluation criteria.                            |
| `ECriterion`       | A single evaluation criterion descriptor                   |
| `ECase`            | A single evaluation case.                                  |
| `EvalSuite`        | Fluent builder for structured evaluation suites            |
| `EvalReport`       | Result of running an evaluation suite                      |
| `ComparisonReport` | Result of comparing multiple agents on the same eval cases |
| `EPersona`         | Namespace for prebuilt user simulation personas            |
