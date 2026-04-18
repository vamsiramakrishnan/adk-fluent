# Session store, fork & replay

The `adk_fluent._session` package is adk-fluent's **session-scoped
storage mechanism** — the unified home for three concerns that used to
live as three separate harness modules:

1. **Replay** — record every harness event to a tape, persist as
   JSONL, inspect after the fact.
2. **Fork** — snapshot named branches of session state, diff and merge
   them, roll back to any previous branch.
3. **Store** — bundle the tape and the fork manager behind one object
   so you can persist (and re-hydrate) a whole session atomically.

:::{admonition} Looking for cursors, async tail, or pluggable backends?
:class: tip

This page covers the store / fork APIs. For the **durable event log**
layer underneath -- monotonic `seq`, `since(n)`, `tail()`, `TapeBackend`
(JSONL / InMemory / Null / Chain), `stream_from_cursor`, and the workflow
lifecycle events -- see [durable events](durable-events.md). For the
reactive layer on top (`Signal`, `Reactor`, `AgentToken`), see
[reactor](reactor.md).
:::

## The five pieces

| Type | Role | Mutable? |
| --- | --- | --- |
| `SessionTape` | Ordered log of `HarnessEvent` entries with timestamps. | mutable |
| `Branch` | Frozen-ish dataclass: one named state snapshot + messages + metadata. | mutable dataclass |
| `ForkManager` | Keeps a dict of `Branch` objects, supports `switch`, `merge`, `diff`. | mutable |
| `SessionSnapshot` | Frozen bundle of tape entries + branches + active pointer. Serialises to JSON. | frozen |
| `SessionStore` | Unified container that owns one tape + one fork manager and can snapshot/restore both atomically. | mutable |
| `SessionPlugin` | ADK `BasePlugin` that wires a store into `after_agent_callback` for the whole invocation tree. | wraps a store |

The split is the same pattern used by `_usage` and `_budget`: mutable
runtime objects (`SessionTape`, `ForkManager`, `SessionStore`) for live
accounting, and a frozen value object (`SessionSnapshot`) for
persistence and replay.

## Quick start

### Persist a whole session

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import H, SessionSnapshot, SessionStore

store = H.session_store()

# Wire the tape to your event dispatcher
dispatcher = H.dispatcher()
dispatcher.subscribe(store.record_event)

# Auto-fork state after a key agent completes
my_agent.after_agent(store.auto_fork("post_writer"))

# ... run the session ...

# End of session: dump everything to disk
store.snapshot().save("/project/.harness/session.json")
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { H, SessionSnapshot, SessionStore } from "adk-fluent-ts";

const store = H.sessionStore();

// Wire the tape to your event dispatcher
const dispatcher = H.dispatcher();
dispatcher.subscribe((event) => store.recordEvent(event));

// Auto-fork state after a key agent completes
myAgent.afterAgent(store.autoFork("post_writer"));

// ... run the session ...

// End of session: dump everything to disk
store.snapshot().save("/project/.harness/session.json");
```
:::
::::

### Replay later

```python
snapshot = SessionSnapshot.load("/project/.harness/session.json")
store = SessionStore.from_snapshot(snapshot)

print(store.summary())
for event in store.tape.events:
    print(event["t"], event["kind"])

# Inspect a saved branch
writer_state = store.forks.get("post_writer").state
```

### Session-wide plugin

For multi-agent apps, install `SessionPlugin` on the root app. It
auto-forks state after every agent in the tree — coordinator,
transfer targets, and subagent specialists — with no per-agent wiring:

```python
from adk_fluent import App, H, Runner

plugin = H.session_plugin(fork_prefix="snap")

runner = (
    Runner()
    .app(App("coder").root(my_agent).plugin(plugin))
    .build()
)

await runner.run_async("Write a plan")

# Every agent contributes one branch named "snap:<agent_name>"
for entry in plugin.store.forks.list_branches():
    print(entry["name"], entry["keys"], "keys")
```

## ForkManager deep dive

### Creating and switching

```python
from adk_fluent import H

forks = H.forks()

forks.fork("base", {"plan": "outline"})
forks.fork("alt", {"plan": "outline", "variant": "humor"})

# Roll back to base
state = forks.switch("base")
```

`switch()` always returns a deep copy so the caller cannot mutate a
stored branch by accident.

### Diffing branches

```python
d = forks.diff("base", "alt")
# {
#     "only_a": {},
#     "only_b": {"variant": "humor"},
#     "different": {},
#     "same": {"plan"},
# }
```

### Merging

```python
merged = forks.merge("base", "alt", strategy="union")
merged = forks.merge("base", "alt", strategy="intersection")
merged = forks.merge("base", "alt", strategy="prefer", prefer="base")
```

- **union**: last branch wins on key conflicts.
- **intersection**: keep only keys present in every branch.
- **prefer**: take the given branch's value for any conflicting key.

### Auto-capturing via callbacks

```python
agent = (
    Agent("writer")
    .before_agent(forks.restore_callback("checkpoint"))
    .after_agent(forks.save_callback("checkpoint"))
    .build()
)
```

These are exposed on `SessionStore` too as `store.auto_restore(name)`
and `store.auto_fork(name)`.

## SessionTape deep dive

Every tape entry is a plain dict, not an event object. That makes
tapes friendly to external tools (`jq`, `grep`, `diff`) and lets them
survive across Python versions without worrying about class changes.

Every recorded entry is stamped with a monotonic `seq` and the tape
tracks a `head` cursor. `since(n)` returns history at or after the
cursor; `tail(from_seq=...)` is an async iterator that blocks on new
writes. See [durable events](durable-events.md) for the full cursor
API and the `TapeBackend` Protocol (`JsonlBackend`, `InMemoryBackend`,
`NullBackend`, `ChainBackend`).

```python
from adk_fluent import H

tape = H.tape()
dispatcher = H.dispatcher()
dispatcher.subscribe(tape.record)

# ... session runs ...

tape.save("/tmp/session.jsonl")

# Later
tape = SessionTape.load("/tmp/session.jsonl")
tool_calls = tape.filter("tool_call_start")
print(tape.summary())

# Resume a consumer from a cursor (see durable-events.md)
for entry in tape.since(42):
    print(entry["seq"], entry["kind"])
```

## Putting it together

Use `SessionStore` when you care about both halves. Use `SessionTape`
or `ForkManager` directly when you only need one of them. Use
`SessionPlugin` when you want automatic capture across every agent in
an invocation tree.

```python
from adk_fluent import H

# Manual (direct API)
store = H.session_store()
dispatcher.subscribe(store.record_event)

# Session-wide plugin (recommended for multi-agent apps)
plugin = H.session_plugin()

# Just event recording, no branches
tape = H.tape()

# Just state branching, no events
forks = H.forks()
```

All four paths produce objects that can feed each other:
`SessionStore.from_snapshot(snap)` rebuilds a store from a bare
snapshot, `store.tape` returns the inner tape for ad-hoc inspection,
and every piece is independently serialisable.
