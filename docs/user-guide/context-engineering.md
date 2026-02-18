# Context Engineering

`C` factories return frozen descriptors that control what conversation history and state each agent sees. They compose with `+` (union) and `|` (pipe) and are passed to `Agent.context()`.

## Quick Start

```python
from adk_fluent import Agent, C

# Suppress all conversation history
clean_agent = Agent("processor").context(C.none()).instruct("Process input.").build()

# Only see last 3 turn-pairs + state keys
focused_agent = (
    Agent("analyst")
    .context(C.window(n=3) + C.from_state("topic"))
    .instruct("Analyze {topic}.")
    .build()
)
```

## The Problem

In multi-agent pipelines, every agent shares the same conversation session. Without context engineering, each agent sees the full history -- including irrelevant turns, other agents' internal reasoning, and tool-call noise. This wastes token budget and degrades output quality.

Context engineering solves three problems:

1. **Token budgets.** LLMs have finite context windows. Passing the full history to every agent burns tokens on content that does not help the current task.
2. **Irrelevant history.** A classifier agent does not need to see the drafts produced by a writer agent three steps earlier. Passing them in adds noise.
3. **Leaked reasoning.** When agents see each other's chain-of-thought, they anchor on prior conclusions instead of reasoning independently.

`C` primitives let you declare exactly what each agent should see -- and nothing more.

## Primitives Reference

| Factory | Purpose |
|---------|---------|
| `C.none()` | Suppress all conversation history |
| `C.default()` | Keep default history (pass-through) |
| `C.user_only()` | Include only user messages |
| `C.from_state(*keys)` | Inject state keys into instruction |
| `C.from_agents(*names)` | Include user + named agent outputs |
| `C.exclude_agents(*names)` | Exclude named agent outputs |
| `C.window(n=)` | Last N turn-pairs only |
| `C.template(str)` | Render template from state |
| `C.capture(key)` | Capture user message to state |
| `C.budget(max_tokens=)` | Token budget constraint |
| `C.priority(tier=)` | Priority tier for ordering |

## `C.none()`

Suppress all conversation history. The agent sees only its instruction:

```python
agent = Agent("classifier").context(C.none()).instruct("Classify the input.").build()
```

## `C.default()`

Keep the default conversation history. This is the pass-through -- equivalent to not calling `.context()` at all:

```python
agent = Agent("assistant").context(C.default()).instruct("Help the user.").build()
```

## `C.user_only()`

Include only user messages, filtering out all agent and tool responses:

```python
# The reviewer sees what the user said, not what other agents produced
agent = Agent("reviewer").context(C.user_only()).instruct("Review the request.").build()
```

## `C.from_state(*keys)`

Read named keys from session state and inject them as context. Suppresses conversation history by default so the agent works purely from state:

```python
# After a prior agent writes state["topic"] and state["style"]
agent = (
    Agent("writer")
    .context(C.from_state("topic", "style"))
    .instruct("Write about {topic} in {style} style.")
    .build()
)
```

## `C.from_agents(*names)`

Include user messages plus outputs from specific named agents. All other agent outputs are excluded:

```python
# The editor sees only what the user said and what "writer" produced
agent = (
    Agent("editor")
    .context(C.from_agents("writer"))
    .instruct("Edit the draft for clarity.")
    .build()
)
```

## `C.exclude_agents(*names)`

Include everything except outputs from the named agents:

```python
# The summarizer sees the full history but ignores the verbose "researcher" output
agent = (
    Agent("summarizer")
    .context(C.exclude_agents("researcher"))
    .instruct("Summarize the conversation.")
    .build()
)
```

## `C.window(n=)`

Include only the last N turn-pairs (user message + model response). Useful for long-running conversations where only recent context matters:

```python
# Only see the last 3 exchanges
agent = Agent("responder").context(C.window(n=3)).instruct("Continue the conversation.").build()
```

## `C.template(str)`

Render a template string using state values. Supports `{key}` (required) and `{key?}` (optional, replaced with empty string if missing):

```python
agent = (
    Agent("reporter")
    .context(C.template("Topic: {topic}\nNotes: {notes?}"))
    .instruct("Write a report from the context above.")
    .build()
)
```

## `C.capture(key)`

Capture the most recent user message into a state key. This delegates to `S.capture(key)` and is used as a pipeline step, not inside `.context()`:

```python
from adk_fluent import Agent, C, S

pipeline = (
    S.capture("user_message")
    >> Agent("handler")
        .context(C.from_state("user_message"))
        .instruct("Respond to: {user_message}")
)
```

## `C.budget(max_tokens=)`

Declare a token budget constraint on the context. Defaults to 8000 tokens with `truncate_oldest` overflow:

```python
agent = (
    Agent("analyst")
    .context(C.budget(max_tokens=4000))
    .instruct("Analyze the data.")
    .build()
)
```

## `C.priority(tier=)`

Set a priority tier for context ordering. Lower tier values mean higher priority:

```python
agent = (
    Agent("critical")
    .context(C.priority(tier=1))
    .instruct("Handle urgent requests.")
    .build()
)
```

## Composition

Primitives compose with two operators:

**`+` (union)** combines transforms. Both are applied to produce the final context:

```python
# Window + state keys: agent sees last 3 turns AND the topic from state
ctx = C.window(n=3) + C.from_state("topic", "style")

agent = Agent("analyst").context(ctx).instruct("Analyze {topic}.").build()
```

**`|` (pipe)** feeds the output of one transform into another:

```python
# Window output piped through a template
ctx = C.window(n=5) | C.template("Recent conversation:\n{history}")

agent = Agent("summarizer").context(ctx).instruct("Summarize.").build()
```

You can chain multiple unions:

```python
ctx = C.window(n=3) + C.from_state("topic") + C.budget(max_tokens=4000)
```

## Integration with Agent Builder

Pass any `C` transform to `.context()` on the agent builder. The transform is compiled at `.build()` time into the underlying ADK configuration:

```python
agent = Agent("writer").context(C.from_state("topic")).instruct("Write about {topic}.").build()
```

When `.context()` sets `include_contents="none"`, the agent's conversation history is suppressed and replaced by the context transform's output. The developer instruction is still templated with state variables via `{key}` placeholders.

## Complete Example

A realistic multi-agent pipeline where context engineering keeps each agent focused:

```python
from adk_fluent import Agent, C, S

pipeline = (
    S.capture("user_message")
    >> Agent("classifier")
        .model("gemini-2.5-flash")
        .instruct("Classify the user's intent.")
        .context(C.none())  # No history needed
        .outputs("intent")
    >> Agent("handler")
        .model("gemini-2.5-flash")
        .instruct("Help the user.")
        .context(C.from_state("user_message", "intent") + C.user_only())
)
```

The classifier sees only its instruction -- no history, no prior agent output. The handler sees the original user message and classified intent from state, plus user-only history for conversational continuity. Each agent gets exactly the context it needs.
