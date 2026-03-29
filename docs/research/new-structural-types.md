# New Structural Types: Beyond Pipeline, FanOut, Loop

> **Status**: Research / RFC
> **Date**: 2026-03-29
> **Branch**: `claude/skill-based-agents-research-NSzDc`

---

## The Gap

adk-fluent has five structural types today:

```
Pipeline  (>>)   — A then B then C          — SequentialAgent
FanOut    (|)    — A and B and C at once     — ParallelAgent
Loop      (*)    — repeat until done         — LoopAgent
Route            — if X then A else B        — before_agent callback
Fallback  (//)   — try A, if fail try B      — before_agent + exception handling
```

These handle **static, predetermined topologies**. The wiring is fixed at
build time. But sophisticated agents need topologies that are **dynamic**,
**conversational**, **graph-shaped**, or **transactional**. These patterns
exist in the wild but require 30-50 lines of manual callback wiring today.
A new structural type would collapse them to 1-3 lines.

---

## Proposed New Types

### 1. `Graph` — Arbitrary DAG with Explicit Edges

**What Pipeline can't express:**

```
A ──► B ──► D
 │         ▲
 └──► C ──┘
```

B and C both depend on A. D depends on both B and C. Today:

```python
# WRONG — D only sees the FanOut result, not B and C individually
pipeline = A >> (B | C) >> D

# HACK — manual state wiring, loses the topology meaning
pipeline = A >> (B.writes("b_out") | C.writes("c_out")) >> D.reads("b_out", "c_out")
```

The hack works but the DAG structure is invisible. No tooling, no visualization,
no contract checking.

**With `Graph`:**

```python
from adk_fluent import Graph

flow = (
    Graph("research")
    .node(A)
    .node(B).after(A)
    .node(C).after(A)
    .node(D).after(B, C)
    .build()
)
```

Or with operator syntax — the `&` operator for "depends-on":

```python
flow = Graph("research").edges(
    A >> B,
    A >> C,
    (B & C) >> D,  # D waits for both B and C
)
```

**Why it's foundational**: Graph subsumes Pipeline (`A >> B >> C` is a linear graph)
and FanOut+merge (`A >> (B | C) >> D` is a diamond graph). It's the general case
that unlocks arbitrary agent topologies without manual state plumbing.

**What it compiles to**: ADK doesn't have a native GraphAgent. Build compiles the
DAG into nested SequentialAgent + ParallelAgent by topological sort. Nodes at the
same depth with no dependencies run in parallel. The compiler figures out the optimal
nesting.

```
Graph(A→B, A→C, B→D, C→D)
  compiles to:
  SequentialAgent([
      A,
      ParallelAgent([B, C]),
      D,
  ])
```

**API:**

```python
class Graph(BuilderBase):
    def __init__(self, name: str): ...
    def node(self, agent) -> Self: ...          # Add a node
    def edge(self, src, dst) -> Self: ...       # Add dependency
    def edges(self, *exprs) -> Self: ...        # Bulk add from >> expressions
    def after(self, *deps) -> Self: ...         # Last-added node depends on deps
    def build(self) -> _ADK_BaseAgent: ...      # Compile DAG → nested ADK agents
    def to_mermaid(self) -> str: ...            # Visualize the DAG
```

---

### 2. `Turn` — Multi-Agent Conversation (Agents Talk to Each Other)

**What Loop can't express:**

In a Loop, agents run sequentially and share state. But they don't *converse* —
agent B doesn't see agent A's reasoning as a message, it sees a state key.
There's no back-and-forth dialogue.

**Real patterns that need Turn:**

- **Debate**: pro argues, con rebuts, pro counters, con counters, judge decides
- **Negotiation**: buyer proposes, seller counters, repeat until agreement
- **Interview**: interviewer asks, candidate answers, interviewer follows up
- **Peer review**: author presents, reviewer critiques, author revises

**With `Turn`:**

```python
from adk_fluent import Turn

debate = (
    Turn("policy_debate")
    .participant(Agent("pro").instruct("Argue FOR the proposition."))
    .participant(Agent("con").instruct("Argue AGAINST the proposition."))
    .judge(Agent("judge").instruct("Evaluate both sides. Declare a winner."))
    .rounds(3)
    .build()
)

result = debate.ask("Should we adopt a four-day work week?")
```

**Key difference from Loop**: In a `Turn`, each participant sees the **full
conversation transcript** from all participants in prior rounds — like a
chat thread. In a Loop, each agent only sees its configured state keys.
Turn creates a shared conversational context.

**Operator syntax:**

```python
# The ~ operator: "A converses with B"
debate = (Agent("pro") ~ Agent("con")).rounds(3).judge(Agent("judge"))
```

**API:**

```python
class Turn(BuilderBase):
    def __init__(self, name: str): ...
    def participant(self, agent) -> Self: ...   # Add participant
    def judge(self, agent) -> Self: ...         # Final judge (optional)
    def rounds(self, n: int) -> Self: ...       # Number of conversation rounds
    def until(self, pred) -> Self: ...          # Stop when predicate is true
    def visible_to(self, strategy) -> Self: ... # Who sees what (all/adjacent/judge-only)
    def build(self) -> _ADK_BaseAgent: ...
```

**What it compiles to**: A LoopAgent containing a SequentialAgent of participants,
with a custom `before_model_callback` that injects the conversation transcript
as context. Each round appends to a shared `_turn_transcript` state key.

---

### 3. `Swarm` — Dynamic Agent Selection (Agents Choose Who Goes Next)

**What Route can't express:**

Route is deterministic — a Python predicate picks the next agent. But in a
Swarm, the **LLM decides** which agent should handle the next step, and agents
can hand off to each other dynamically.

Today this requires `.sub_agent()` with manual transfer control:

```python
coordinator = (
    Agent("coordinator", "gemini-2.5-pro")
    .instruct("Route to the right specialist.")
    .sub_agent(researcher.isolate().describe("Research specialist"))
    .sub_agent(writer.isolate().describe("Writing specialist"))
    .sub_agent(coder.isolate().describe("Coding specialist"))
)
```

This works but the coordinator is a bottleneck — every handoff goes through it.
Agents can't talk to each other directly.

**With `Swarm`:**

```python
from adk_fluent import Swarm

team = (
    Swarm("project_team")
    .agent(Agent("researcher").instruct("Research. Hand off to writer when done."))
    .agent(Agent("writer").instruct("Write. Hand off to reviewer when done."))
    .agent(Agent("reviewer").instruct("Review. Hand off to researcher if more info needed."))
    .agent(Agent("publisher").instruct("Publish. This is the final step."))
    .entry("researcher")       # First agent to run
    .exit("publisher")         # Conversation ends when this agent finishes
    .max_handoffs(10)          # Safety limit
)
```

**Key difference from sub_agent coordinator**: In a Swarm, every agent can
transfer to every other agent directly. There's no coordinator bottleneck.
The LLM in each agent decides who goes next using ADK's native
`transfer_to_agent` tool.

**What it compiles to**: A root LlmAgent with all swarm agents as `sub_agents`.
Each agent gets `.describe()` auto-set from its instruction. Transfer control
is configured so agents can transfer to peers (no `.isolate()`). The entry
agent is the root, with a `before_agent_callback` that routes the initial
prompt.

**API:**

```python
class Swarm(BuilderBase):
    def __init__(self, name: str): ...
    def agent(self, agent) -> Self: ...         # Add swarm member
    def entry(self, name: str) -> Self: ...     # Starting agent
    def exit(self, name: str) -> Self: ...      # Terminal agent
    def max_handoffs(self, n: int) -> Self: ... # Safety limit
    def topology(self, t: str) -> Self: ...     # "full" (any→any), "ring", "star"
    def build(self) -> _ADK_BaseAgent: ...
```

---

### 4. `Saga` — Transactional Multi-Step with Compensation

**What Pipeline can't express:**

Pipeline runs A → B → C. If C fails, A and B's effects remain. There's no
rollback. For workflows that modify external systems (databases, APIs, payments),
you need compensation logic.

**With `Saga`:**

```python
from adk_fluent import Saga

order = (
    Saga("order_fulfillment")
    .step(reserve_agent,   compensate=unreserve_agent)
    .step(charge_agent,    compensate=refund_agent)
    .step(ship_agent,      compensate=cancel_shipment_agent)
    .step(notify_agent)    # No compensate — notification is idempotent
    .build()
)

# If ship_agent fails:
#   1. cancel_shipment_agent runs (no-op since shipping failed)
#   2. refund_agent runs (reverses the charge)
#   3. unreserve_agent runs (releases inventory)
```

**What it compiles to**: A SequentialAgent with `after_agent_callback` on each
step that records completion in `state["_saga_completed_steps"]`. If any step
raises, an error handler runs compensation agents in reverse order.

**API:**

```python
class Saga(BuilderBase):
    def __init__(self, name: str): ...
    def step(self, agent, *, compensate=None) -> Self: ...
    def on_rollback(self, fn) -> Self: ...     # Hook called when rolling back
    def build(self) -> _ADK_BaseAgent: ...
```

---

### 5. `EachOf` — Stateful Map with Accumulation

**What `map_over` can't express well:**

`map_over(key)` maps an agent over list items, but each invocation is
independent — no shared accumulator, no early termination, no ordering
guarantees.

**With `EachOf`:**

```python
from adk_fluent import EachOf

analyzer = (
    EachOf("analyze_docs", items_key="documents")
    .do(Agent("analyzer").instruct("Analyze this document: {item}"))
    .accumulate("findings")           # Append each result to a list
    .stop_if(lambda acc: len(acc) >= 5)  # Early termination
    .concurrency(3)                   # Process 3 at a time
    .build()
)
```

**Key difference from map_over**: EachOf supports accumulation across items,
early termination based on accumulated results, and bounded concurrency. It's
a proper iterator pattern, not just parallel map.

**API:**

```python
class EachOf(BuilderBase):
    def __init__(self, name: str, *, items_key: str): ...
    def do(self, agent) -> Self: ...                    # Agent to run per item
    def accumulate(self, key: str) -> Self: ...         # Collect results
    def stop_if(self, pred) -> Self: ...                # Early termination
    def concurrency(self, n: int) -> Self: ...          # Bounded parallelism
    def order(self, strategy: str) -> Self: ...         # "parallel" | "sequential" | "priority"
    def build(self) -> _ADK_BaseAgent: ...
```

---

## Comparison: What Each Type Unlocks

| Type | Topology | Today's Workaround | Lines Saved | New Capability |
|------|----------|-------------------|-------------|----------------|
| **Graph** | Arbitrary DAG | Nested Pipeline + FanOut + manual state | 10-30 | Visualizable DAGs, auto-parallel |
| **Turn** | Multi-agent conversation | Loop + manual transcript state | 15-25 | Agents actually converse |
| **Swarm** | Dynamic handoff mesh | sub_agent + coordinator bottleneck | 10-20 | Peer-to-peer transfer, no bottleneck |
| **Saga** | Transactional pipeline | Pipeline + manual error callbacks | 10-20 | Automatic rollback |
| **EachOf** | Stateful iteration | map_over + manual accumulation | 5-10 | Early stop, bounded concurrency |

## Which Operators?

| Type | Operator | Mnemonic |
|------|----------|----------|
| Graph | `(B & C) >> D` | `&` = "both must complete" |
| Turn | `A ~ B` | `~` = "conversation between" |
| Swarm | (no operator, too complex) | Builder-only |
| Saga | (no operator) | Builder-only |
| EachOf | `agent % items_key` | `%` = "for each" |

## Implementation Priority

| Priority | Type | Reason |
|----------|------|--------|
| **1** | **Graph** | Most foundational — subsumes Pipeline + FanOut, unlocks all DAGs |
| **2** | **Turn** | Most novel — no other framework has a first-class conversation type |
| **3** | **Swarm** | High demand — mirrors OpenAI Swarm, CrewAI hierarchical |
| **4** | **EachOf** | Practical — every real pipeline has a "process these items" step |
| **5** | **Saga** | Niche — only needed for external-system workflows |

## Design Principles

1. **Every type compiles to native ADK agents** — no custom runtime, `adk web` still works
2. **Every type supports all operators** — `Graph >> Agent`, `Turn | Turn`, `Swarm * 3`
3. **Every type inherits BuilderBase** — `.mock()`, `.explain()`, `.ask()` just work
4. **Every type has a `.to_mermaid()`** — visual introspection is mandatory
5. **Operators are optional sugar** — builder form is always available and clearer for complex cases
