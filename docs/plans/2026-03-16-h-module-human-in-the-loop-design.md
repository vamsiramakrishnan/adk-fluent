# Design: H Module (Human-in-the-Loop)

**Issue:** #15
**Status:** Design spec — not yet implemented
**Date:** 2026-03-16

## Problem

Enterprise LLM systems need human oversight. ADK handles this via
`EventActions(escalate=True)`, which pauses the pipeline and forces
developers to write 40+ lines of boilerplate to serialize state, notify
a human, provide an approval API, and rehydrate the session on resume.

## Goals

- Declarative suspension primitives that integrate with the existing
  expression operator system (`>>`, `|`, `*`)
- Automatic state serialization and rehydration
- Configurable notification channels (webhook, email, Pub/Sub)
- Timeout and escalation policies
- Zero boilerplate for the common "pause, wait for human, resume" pattern

## Non-Goals

- Building a full approval UI (out of scope — use external tools)
- Real-time chat with a human reviewer (use A2UI for that)
- Custom durable execution engines (rely on existing backends)

## Proposed API

### Core primitives

```python
from adk_fluent import H, gate

# Simple approval gate
pipeline = analyzer >> gate(H.approval()) >> executor

# With timeout and escalation
pipeline = (
    analyzer
    >> gate(H.approval(
        timeout="7d",
        escalate_to="manager@acme.com",
        message="High-risk transaction detected: {amount}",
    ))
    >> executor
)

# Human review (returns feedback text into state)
pipeline = (
    writer
    >> H.review(prompt="Review this draft", into="feedback")
    >> reviser
)

# Human choice (pick from options)
pipeline = (
    analyzer
    >> H.choice("Select action", options=["approve", "reject", "escalate"], into="decision")
    >> Route("decision").eq("approve", executor).otherwise(escalator)
)
```

### H namespace methods

```
H.approval(timeout=, escalate_to=, message=)  — binary approve/reject gate
H.review(prompt=, into=, timeout=)             — free-text human feedback
H.choice(prompt, options=, into=, timeout=)    — pick from enumerated options
H.confirm(message=)                            — simple yes/no confirmation
H.input(prompt=, into=, schema=)               — structured human input
```

### Resumption API

```python
from adk_fluent import App

app = App(root_agent).build()

# Resume a suspended session
await app.resume(session_id="abc123", decision="approved", feedback="Looks good")
```

### Configuration

```python
from adk_fluent import App

app = (
    App(pipeline)
    .suspension_store("sqlite:///suspensions.db")  # or GCS, Firestore, etc.
    .notification_channel(webhook="https://hooks.slack.com/...")
    .build()
)
```

## Architecture

### IR integration

New IR node: `SuspensionNode`

```
SuspensionNode
  kind: "approval" | "review" | "choice" | "confirm" | "input"
  timeout: Optional[str]
  escalate_to: Optional[str]
  message_template: Optional[str]
  into_key: Optional[str]
  options: Optional[list[str]]
```

`gate(H.approval(...))` compiles to a `SuspensionNode` in the IR tree.

### Execution flow

1. Pipeline hits `SuspensionNode`
2. Framework serializes full session state (ctx.session) to durable store
3. Framework yields `SuspendedEvent` with session_id, suspension metadata
4. Notification sent via configured channel
5. Pipeline halts — runner returns control to caller
6. Human acts via external mechanism (webhook, UI, CLI)
7. `app.resume(session_id, ...)` rehydrates session and continues from suspension point

### State serialization

Leverage ADK's existing `SessionService` for state persistence:
- `InMemorySessionService` for dev/testing
- `DatabaseSessionService` for production
- `VertexAiSessionService` for managed deployments

### Contract checking

- Pass 15: validate that `H.review(into="key")` writes are visible to downstream agents
- `SuspensionNode` participates in data-flow contract checking like any other node

## Dependencies

- ADK's `EventActions(escalate=True)` mechanism
- Existing session service infrastructure
- Existing notification/webhook patterns

## Testing strategy

- Unit tests: H primitives compile to correct IR nodes
- Integration tests: suspension/resume cycle with InMemorySessionService
- Mock tests: verify notification channel invocation

## Open questions

1. Should `H.approval()` block the async generator or return a special event type?
2. How to handle timeout expiry — auto-reject, auto-escalate, or raise?
3. Should suspension metadata be extensible (custom fields for audit trails)?
4. Integration with Temporal backend — map to Temporal signals?

## Estimated scope

- New file: `src/adk_fluent/_human.py` (~300 lines)
- IR node addition: `SuspensionNode` in `_ir.py`
- Compilation support in `compile/` (~100 lines)
- App.resume() method (~50 lines)
- Tests: ~200 lines
- Docs: user guide section + cookbook example
