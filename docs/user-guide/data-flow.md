# Data Flow Between Agents

Every data-flow method in adk-fluent maps to exactly one of **five orthogonal concerns**. Understanding these five concerns eliminates all confusion about which method to use.

## The Five Concerns

| Concern      | Method                           | What it controls                        | ADK field                                   |
| ------------ | -------------------------------- | --------------------------------------- | ------------------------------------------- |
| **Context**  | `.reads()` / `.context()`        | What the agent SEES                     | `include_contents` + `instruction_provider` |
| **Input**    | `.accepts()` / `.input_schema()` | What input the agent ACCEPTS as a tool  | `input_schema`                              |
| **Output**   | `.returns()` / `@ Model`         | What SHAPE the response takes           | `output_schema`                             |
| **Storage**  | `.writes()` / `.save_as()`       | Where the response is STORED            | `output_key`                                |
| **Contract** | `.produces()` / `.consumes()`    | Checker ANNOTATIONS (no runtime effect) | _(extension fields)_                        |

### Recommended builder chain

```python
from adk_fluent import Agent
from pydantic import BaseModel

class SearchQuery(BaseModel):
    query: str
    max_results: int = 10

class Intent(BaseModel):
    category: str
    confidence: float

classifier = (
    Agent("classifier", "gemini-2.0-flash")
    .instruct("Classify the user query: {query}")
    .reads("query")              # CONTEXT: I see state["query"]
    .accepts(SearchQuery)        # INPUT:   Tool-mode validation
    .returns(Intent)             # OUTPUT:  Structured JSON response
    .writes("intent")            # STORAGE: Save to state["intent"]
)
```

Each line maps to exactly one ADK field. Each verb is unambiguous.

______________________________________________________________________

## What Gets Sent to the LLM

When an agent runs, data is assembled and sent to the LLM in this order:

### 1. System Message

The instruction text, assembled from:

- `static_instruction` (if set — cached, always at position 0)
- `global_instruction` (if set — shared across all agents)
- `instruction` (the main instruction, templated with state variables)

Template variables like `{query}` are replaced with `state["query"]` at runtime.

### 2. Conversation History

Controlled by `include_contents`:

- **`"default"`** (the default) — ALL prior conversation turns are included
- **`"none"`** — NO history is sent to the LLM

**Important:** `.reads()` sets `include_contents="none"`. When you use `.reads("topic")`, the agent does **not** see any conversation history — only the injected state values.

### 3. Context Injection

When `.reads("topic", "tone")` is set, state values are injected into the instruction as a `<conversation_context>` block:

```
[Your instruction text]

<conversation_context>
[topic]: value from state
[tone]: value from state
</conversation_context>
```

This is delivered via an async `instruction_provider` that replaces the instruction field at runtime.

### 4. User Message

- For `.ask("prompt")`: the prompt string you provide
- For pipelines: ADK manages turn flow automatically between agents

### 5. Tools

Tool descriptions are sent as function declarations to the LLM. **Tools are NOT sent if `output_schema` is set** — this is an ADK constraint.

### 6. Output Constraint

- If `output_schema` is set (via `.returns(Model)` or `@ Model`), the LLM MUST respond with JSON matching the schema
- If not set, the LLM responds in free-form text

### What Does NOT Get Sent

| Not sent                               | Why                                                     |
| -------------------------------------- | ------------------------------------------------------- |
| State keys not in `.reads()`           | Only explicitly declared keys are injected              |
| State keys not in `{template}`         | Only template variables in the instruction are resolved |
| `.produces()` / `.consumes()`          | Contract annotations — never sent to the LLM            |
| `.writes()` target key                 | Only used AFTER the LLM responds                        |
| `.accepts()` schema                    | Only validated at tool-call time, not sent to LLM       |
| History when `include_contents="none"` | Conversation history is suppressed                      |

### After the LLM Responds

1. Response text is captured
1. If `output_key` is set (`.writes()`), `state[key] = response_text`
1. If `output_schema` is set and using `.ask()`, response is parsed to a Pydantic model
1. `after_model_callback` / `after_agent_callback` hooks run

______________________________________________________________________

## Context: What the Agent Sees

### Default: Full history

By default, an agent sees the entire conversation history from all agents. No `.reads()` or `.context()` needed.

### `.reads()`: Selective state injection

```python
Agent("writer").reads("topic", "tone")
```

This does two things:

1. Sets `include_contents="none"` — conversation history is **suppressed**
1. Injects `state["topic"]` and `state["tone"]` as a `<conversation_context>` block

### `.context()`: Advanced context control

```python
from adk_fluent import C

Agent("writer").context(C.window(n=3))      # Last 3 turns only
Agent("writer").context(C.user_only())       # User messages only
Agent("writer").context(C.none())            # No context at all
```

### Composing context

`.context()` and `.reads()` compose additively with the `+` operator:

```python
Agent("writer")
    .context(C.window(n=3))   # Include last 3 turns
    .reads("topic")           # AND inject state["topic"]
```

______________________________________________________________________

## Input: What the Agent Accepts (Tool Mode)

### `.accepts(Model)`: Schema validation at tool-call time

```python
class SearchQuery(BaseModel):
    query: str

Agent("searcher").accepts(SearchQuery)
```

When another agent invokes this agent via `AgentTool`, the input is validated against this schema. **This has no effect for top-level agents** — only for agents used as tools.

______________________________________________________________________

## Output: What Shape the Response Takes

### Default: Plain text

Without `.returns()`, the agent responds in free-form text and **can use tools**.

### `.returns(Model)`: Structured JSON

```python
class Intent(BaseModel):
    category: str
    confidence: float

Agent("classifier").returns(Intent)
```

Forces the LLM to respond with JSON matching the schema. **Tools are disabled** when this is set.

The `@` operator is shorthand: `Agent("classifier") @ Intent`

### Using `.ask()` with structured output

```python
result = await Agent("classifier").returns(Intent).ask_async("Classify this query")
# result is an Intent instance (automatically parsed)
```

______________________________________________________________________

## Storage: Where the Response Goes

### `.writes(key)`: Store raw text in state

```python
Agent("researcher").writes("findings")
```

After the agent runs, `state["findings"]` holds the **raw text response** (not a parsed Pydantic model).

### Template variables

Downstream agents reference stored values with `{key}` placeholders:

```python
pipeline = (
    Agent("researcher").writes("findings")
    >> Agent("writer").instruct("Summarize: {findings}")
)
```

______________________________________________________________________

## Contracts: Static Annotations

### `.produces(Model)` / `.consumes(Model)`

These have **no runtime effect**. They are annotations for the contract checker:

```python
Agent("classifier").produces(Intent).consumes(SearchQuery)
```

The contract checker uses these to verify data flow between agents at build time.

______________________________________________________________________

## Inspecting Data Flow

### `.data_flow()`: Five-concern snapshot

```python
agent = Agent("classifier").reads("query").returns(Intent).writes("intent")
print(agent.data_flow())
# Data Flow:
#   reads:    C.from_state('query') — state keys only
#   accepts:  (not set — accepts any input as tool)
#   returns:  structured JSON → Intent (tools disabled)
#   writes:   state['intent']
#   contract: (not set)
```

### `.llm_anatomy()`: What the LLM will see

```python
print(agent.llm_anatomy())
# LLM Call Anatomy: classifier
#   1. System:     "Classify the user query: {query}"
#   2. History:    SUPPRESSED
#   3. Context:    state["query"] injected
#   4. Tools:      DISABLED (output_schema is set)
#   5. Constraint: must return Intent {category: ..., confidence: ...}
#   6. After:      response stored → state["intent"]
```

### `.explain()`: Full builder state

```python
print(agent.explain())
```

Shows model, instruction, data flow (five concerns), tools, callbacks, children, and contract issues.

______________________________________________________________________

## Common Patterns

### Classify then route

```python
pipeline = (
    Agent("classifier")
    .instruct("Classify the query.")
    .returns(Intent)
    .writes("intent")
    >> Agent("handler")
    .reads("intent")
    .instruct("Handle the {intent} query.")
    .writes("response")
)
```

### Fan-out research with merge

```python
from adk_fluent import Agent, FanOut, S

research = (
    FanOut("research")
    .add(Agent("web").writes("web_results"))
    .add(Agent("docs").writes("doc_results"))
    >> S.merge("web_results", "doc_results", into="all_results")
    >> Agent("synthesizer").reads("all_results").writes("synthesis")
)
```

### Review loop

```python
from adk_fluent.patterns import review_loop

pipeline = review_loop(
    worker=Agent("writer").instruct("Write a draft."),
    reviewer=Agent("reviewer").instruct("Review the draft."),
    quality_key="review_score",
    target=0.8,
    max_rounds=3,
)
```

______________________________________________________________________

## Future Modules

### T Module (Tools) — planned

A compositional namespace for tool construction, analogous to C/P/S:

```python
# Future API:
from adk_fluent import T

agent = Agent("assistant").tools(
    T.google_search(),
    T.code_executor(),
    T.from_function(my_func),
)
```

### A Module (Artifacts) — planned

A namespace for artifact handling (files, images, large outputs):

```python
# Future API:
from adk_fluent import A

agent = Agent("generator").artifacts(A.save("report.pdf"))
```
