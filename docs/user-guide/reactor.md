# Reactor -- reactive signals, priorities & interrupts

The reactor is adk-fluent's **reactive state** layer. It turns the
durable tape into something agents can collaborate on: typed state
cells (signals), declarative triggers (predicates), priority
scheduling, and cooperative interrupts with a resume cursor.

If the tape is the "one log, many views" substrate, the reactor is
the first-class view: the one that turns *state changes* into *agent
activations*.

## The mental model

```
          Signal.set()
             │
             ▼
   ┌───────────────────┐
   │ SignalChanged     │  ──►  EventBus (sync observers)
   │ (recorded)        │  ──►  SessionTape  (durable)
   └───────────────────┘
             │
             ▼
   ┌───────────────────┐
   │    Reactor        │  rules match by predicate
   │    scheduler      │  priority selects the winner
   │                   │  preemptive rules cancel lower runs
   └───────────────────┘
             │
             ▼
      AgentToken (per-agent, carries resumeCursor)
```

- **`Signal`** -- a typed state cell with `get()`, `set()`, and
  `version`. Equal-to-current writes are dropped (idempotent),
  force-override is opt-in.
- **`SignalPredicate`** -- declarative trigger composed from
  signals: `temp.rising.where(c > 90) & online.is_true`. Supports
  `and` / `or` / `not` / `where` / `debounce` / `throttle`.
- **`Reactor`** -- scheduler of `(predicate, handler)` rules with
  priority ordering and preemptive interrupts.
- **`AgentToken`** -- a `CancellationToken` keyed by agent name,
  carrying a `resume_cursor` so a cancelled run can pick up where
  it stopped.
- **`TokenRegistry`** -- keyed registry of tokens so the reactor can
  address "the currently running writer" without passing references
  around.

## Signals

A `Signal` holds one value, tracks a monotonic `version`, and emits
a `SignalChanged` event on every real mutation. The emission is
equality-guarded: setting the current value is a no-op unless
`force=True`.

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Signal

temp = Signal("temp", 72.0)
temp.subscribe(lambda v: print("temp now", v))

temp.set(72.0)   # same value → skipped
temp.set(74.1)   # fires observer, version -> 1
temp.update(lambda v: v + 0.5)  # atomic fn update
print(temp.version, temp.get())  # 2 74.6
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Signal } from "adk-fluent-ts";

const temp = new Signal("temp", 72.0);
const off = temp.subscribe((v) => console.log("temp now", v));

temp.set(72.0);             // same value → skipped
temp.set(74.1);             // fires observer, version -> 1
temp.update((v) => v + 0.5);
console.log(temp.version, temp.get()); // 2 74.6
off();
```
:::
::::

Attach a signal to an `EventBus` / `SessionTape` to make every change
a durable event:

```python
from adk_fluent import EventBus, Signal, SessionTape

bus = EventBus()
tape = SessionTape()
bus.subscribe(tape.record)

temp = Signal("temp", 72.0).attach(bus)
temp.set(80.0)  # emits SignalChanged(seq=0, previous=72.0, value=80.0)
```

Observers are isolated -- one throwing subscriber does not block the
rest. Subscribe returns an unsubscribe callable.

## Predicates

Signals expose three built-in predicates and compose from there:

| Factory | Fires when |
| --- | --- |
| `signal.changed` | any mutation |
| `signal.rising` | numeric value increases |
| `signal.falling` | numeric value decreases |
| `signal.is(value)` | value compares equal to `value` |

Composition mirrors boolean algebra:

```python
from adk_fluent import Signal, Reactor

temp = Signal("temp", 72.0)
online = Signal("online", False)

r = Reactor()
r.when(temp.rising.where(lambda v: v > 90) & online.is_(True),
       alert_ops)
r.start()
```

- `a & b` -- both predicates fire on the same tick
- `a | b` -- either predicate fires
- `~a` / `a.not_()` -- negation
- `a.where(fn)` -- extra guard over the current value
- `a.debounce(ms)` / `a.throttle(ms)` -- time-based smoothing

Predicates never run handlers themselves. They are pure, stateless
descriptions of *when* a handler should fire. The reactor evaluates
them.

## Reactor rules & priority

A reactor is a list of `(predicate, handler, options)` rules. When
any signal in any predicate mutates, the reactor evaluates the rules
and schedules the handlers whose predicates fire.

Rules are ordered by **priority -- lower number wins** (10 beats 100).
This matches UNIX niceness and is easy to remember once you think
"this rule is urgent, it gets a low priority number, it jumps the
queue."

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Reactor, Signal

r = Reactor()
temp = Signal("temp", 72.0)

r.when(temp.changed, log_everything, priority=100)
r.when(temp.rising.where(lambda v: v > 90),
       cool_down, priority=10)       # higher priority (runs first)

r.start()
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Reactor, Signal } from "adk-fluent-ts";

const r = new Reactor();
const temp = new Signal("temp", 72.0);

r.when(temp.changed, logEverything, { priority: 100 });
r.when(temp.rising.where((v) => (v as number) > 90),
       coolDown, { priority: 10 });  // higher priority

r.start();
```
:::
::::

### Preemption

A rule marked `preemptive: true` cancels any currently running rule
whose priority is lower (higher number). The running handler sees
`ctx.token.cancelled` flip to `True` and returns; the reactor then
dispatches the preempting rule.

```python
r.when(writer_signal.changed,
       slow_writer,
       agent_name="writer",
       priority=100)

r.when(abort_signal.is_(True),
       cancel_writer,
       agent_name="interrupter",
       priority=5,
       preemptive=True)
```

Handlers must check `ctx.token.cancelled` inside long loops to be
preemptible -- the reactor never kills threads, it asks them to stop.

## AgentToken & TokenRegistry

`AgentToken` is a per-agent cancellation token. It extends the
harness `CancellationToken` with:

- `agent_name` -- so the reactor can address a specific run
- `resume_cursor` -- the tape cursor at which the run was cancelled
- `cancel_with_cursor(cursor)` -- atomic cancel + resume record

`TokenRegistry` is the keyed container. The reactor installs a fresh
token per dispatch; in-flight handlers keep their old token via
closure (so their `cancelled` flag still fires), while the registry
always points at the live run.

```python
from adk_fluent import AgentToken, TokenRegistry

reg = TokenRegistry()
writer = reg.get_or_create("writer")
critic = reg.get_or_create("critic")

# Later: preempt just the writer
reg.cancel("writer", resume_cursor=tape.head)
assert writer.cancelled and writer.resume_cursor == tape.head
assert not critic.cancelled        # siblings unaffected
```

Cancelling an unknown agent returns `False` -- never raises. Use
`reset()` / `reset_all()` to re-arm after a recovery path.

## Priorities of the primitives

Use the reactor when **state drives behavior**: "if temp rises past
90 while online, run the cooler"; "if the writer emits a heading,
start the critic"; "if a user cancels, preempt the slowest branch."

Use a plain callback (`before_model`, `after_agent`) when **structure
drives behavior**: "after this agent, always save a fork."

Use a workflow operator (`>>`, `|`, `*`) when **ordering is fixed**:
"always write then review then render."

The three layers compose. A `Loop` with a reactor-managed stop
signal gives you best-of-both -- fixed structure plus reactive
cancellation.

## When to use what

| Goal | Reach for |
| --- | --- |
| Observe value changes with zero glue | `signal.subscribe(fn)` |
| Run an async handler on mutation | `Reactor.when(signal.changed, fn)` |
| Preempt a slow run | `preemptive=True` rule |
| Address a running agent by name | `TokenRegistry.cancel(name)` |
| Resume after cancellation | `AgentToken.resume_cursor` + `tape.tail(from_seq=...)` |
| Persist reactions for audit | `signal.attach(bus)` → tape |

The reactor's events all flow through the same tape as every other
harness event, so replays, tests, and audits see the same thing the
agents saw. See [durable events](durable-events.md) for the tape
layer underneath.
