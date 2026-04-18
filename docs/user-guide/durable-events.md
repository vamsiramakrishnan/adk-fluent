# Durable event log -- seq, cursors, tail & backends

The **durable event log (DEL)** is the backbone of every production
harness. It is the ordered, cursor-addressable, persistent record of
everything that happened in a session: text chunks, tool calls,
permission decisions, workflow steps, signal changes, subagent runs,
and anything else a plugin records.

One log. Many views. Resumable, replayable, testable.

## One log, many views

The principle is Kappa-architecture clean: writes go to one place,
every consumer reads from that place at its own pace.

```
                ┌──────────────────────────────┐
                │         SessionTape          │
                │   (seq 0..N, append-only)    │
                └──────────────────────────────┘
                 ▲                    ▲       ▲
                 │ record()           │ tail()│ since(n)
    ┌────────────┘                    │       │
    │                                 │       │
  EventBus                       Reactor    CLI/UI renderer
  (sync notify)             (priority rules) (replay from cursor)
```

The tape has three properties that make it a substrate for everything
else:

1. **Monotonic `seq`** — every recorded entry gets a sequence number
   starting at 0. Cursors are `int`, not wall-clock timestamps.
2. **Codec-agnostic persistence** — tapes load and save JSONL. Pre-seq
   tapes back-fill `seq` from the line index so old captures keep
   working.
3. **Pluggable backends** — the in-memory tape can mirror writes to a
   JSONL file, a chain of destinations, or nothing at all (`NullBackend`
   for tests). Backend failures never block the write path.

## Cursors & seq

Every entry carries a `seq` and the tape tracks `head` (the next
unwritten seq).

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import SessionTape

tape = SessionTape()
a = tape.record({"kind": "text", "text": "hello", "timestamp": 0})
b = tape.record({"kind": "text", "text": "world", "timestamp": 0})

assert a["seq"] == 0
assert b["seq"] == 1
assert tape.head == 2

# Read tail after a checkpoint
for entry in tape.since(1):
    print(entry["seq"], entry["kind"])
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { SessionTape } from "adk-fluent-ts";

const tape = new SessionTape();
const a = tape.record({ kind: "text", text: "hello", timestamp: 0 });
const b = tape.record({ kind: "text", text: "world", timestamp: 0 });

console.assert(a.seq === 0);
console.assert(b.seq === 1);
console.assert(tape.head === 2);

for (const entry of tape.since(1)) {
  console.log(entry.seq, entry.kind);
}
```
:::
::::

`since(n)` is synchronous and returns only the records already on the
tape. For long-running consumers (UIs, reactor rules, remote mirrors)
use `tail()` -- an async iterator that drains history, then blocks on
new writes until you cancel.

## Async tail

```python
import anyio

from adk_fluent import SessionTape

async def mirror_to_ui(tape: SessionTape):
    async for entry in tape.tail(from_seq=0):
        await push_to_ui(entry)
```

```ts
import { SessionTape } from "adk-fluent-ts";

async function mirrorToUi(tape: SessionTape, signal: AbortSignal) {
  for await (const entry of tape.tail(0, { signal })) {
    await pushToUi(entry);
  }
}
```

Cancel via `AbortSignal` (TS) or cancel-scope / ``anyio.CancelScope``
(Python). Callers always get every entry in seq order, even if they
start before any writes arrive.

## Pluggable backends

`SessionTape` keeps its in-memory deque for fast reads; a **backend**
mirrors every write to durable storage. Backends implement the tiny
`TapeBackend` Protocol (`append(entry)` at minimum).

| Backend | Use when |
| --- | --- |
| `InMemoryBackend` | tests, read-back parity, deterministic replay |
| `JsonlBackend(path=)` | default persistence, JSONL one-event-per-line |
| `NullBackend` | drop writes entirely (shadow sessions) |
| `ChainBackend([a, b])` | fan-out to several backends at once |

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import SessionTape, JsonlBackend, ChainBackend, InMemoryBackend

mirror = InMemoryBackend()
tape = SessionTape(backend=ChainBackend([
    JsonlBackend(path="/tmp/session.jsonl"),
    mirror,
]))

tape.record({"kind": "text", "text": "a", "timestamp": 0})

assert mirror.entries[0]["text"] == "a"
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import {
  SessionTape,
  JsonlBackend,
  ChainBackend,
  InMemoryBackend,
} from "adk-fluent-ts";

const mirror = new InMemoryBackend();
const tape = new SessionTape({
  backend: new ChainBackend([
    new JsonlBackend({ path: "/tmp/session.jsonl" }),
    mirror,
  ]),
});
tape.record({ kind: "text", text: "a", timestamp: 0 });
```
:::
::::

Backend exceptions are swallowed. A failing disk or a broken remote
must never stop the agent -- the tape is the single writable path, so
it is allowed to keep going even when a replica falls over.

## Workflow lifecycle events

The Phase-C event family makes Pipeline, Loop and FanOut observable
through the same tape. Every built-in workflow emits:

- `StepStarted` / `StepCompleted` -- one pair per sequential step
- `IterationStarted` / `IterationCompleted` -- one pair per `Loop` turn
- `BranchStarted` / `BranchCompleted` -- one pair per `FanOut` branch
- `SubagentStarted` / `SubagentCompleted` -- one pair per dynamic
  subagent run
- `AttemptFailed` -- recorded whenever a retry/fallback path triggers

Install `WorkflowLifecyclePlugin` (Python) or the TS equivalent on the
root `App` so every workflow inside the invocation tree auto-records
these events:

```python
from adk_fluent import App, H, WorkflowLifecyclePlugin

store = H.session_store()
app = (
    App("coder")
    .root(my_workflow)
    .plugin(WorkflowLifecyclePlugin(tape=store.tape))
    .build()
)
```

The tape becomes a complete transcript of *what the workflow did* --
reviewable after the fact, filterable by `kind`, replayable step by
step.

## Stream from a cursor

`stream_from_cursor(tape, from_seq)` (Python) / `streamFromCursor(tape, fromSeq)`
(TS) is a convenience helper: it drains `tape.since(fromSeq)` first,
then switches to `tape.tail()` live. UI clients use it to render
history, then subscribe to updates without racing with new writes.

```python
import anyio
from adk_fluent import H, stream_from_cursor

tape = H.tape()

async def watch_text(cursor: int):
    async for entry in stream_from_cursor(tape, cursor, kind="text"):
        print(entry["seq"], entry["text"])
```

```ts
import { streamFromCursor, SessionTape } from "adk-fluent-ts";

async function watchText(tape: SessionTape, cursor: number, signal: AbortSignal) {
  for await (const entry of streamFromCursor(tape, cursor, { kind: "text", signal })) {
    console.log(entry.seq, (entry as { text: string }).text);
  }
}
```

The default filter is `kind="text"` -- human-readable streaming for
chat UIs. Pass `kind=None` (Python) / `{ kind: null }` (TS) to see every
event, or a specific kind like `"tool_call_end"`.

## EventRecord view

`EventRecord` / `Cursor` are thin typed aliases (a record entry dict
with `seq`, `kind`, `timestamp`, and event-specific fields; `Cursor`
is just `int`). Use them in public signatures when you want to carry a
tape-shaped value without pinning to a specific event subclass.

## When to use what

| Goal | Reach for |
| --- | --- |
| Notify sync observers (UI tick, metric) | `EventBus` (non-durable) |
| Record and replay an agent session | `SessionTape.record` / `.load` |
| Rebuild UI state from scratch | `stream_from_cursor(tape, 0)` |
| Resume a subagent after crash | `AgentToken(resume_cursor=...)` + `tail(from_seq=...)` |
| React to state changes across agents | `Signal` + `Reactor` (see [reactor](reactor.md)) |
| Persist durably with fanout | `SessionTape(backend=ChainBackend([...]))` |

The tape and the reactor are two halves of the same story. The tape
is the durable *past*; the reactor is the reactive *present*. Both
read the same cursor.
