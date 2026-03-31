# Architecture & Core Concepts

:::{admonition} At a Glance
:class: tip

- **adk-fluent** is a thin builder layer on top of Google ADK --- every `.build()` returns a real ADK object
- Builders are typed configuration objects that compile to native ADK at build time
- Nine modules (S, C, P, A, M, T, E, G, UI) provide composable, orthogonal concerns
:::

## System Architecture

adk-fluent sits between your code and Google ADK. It adds zero runtime overhead --- builders exist only at definition time.

```mermaid
graph LR
    subgraph "Your Code"
        A["Agent('helper')
        .instruct(...)
        .tool(...)"]
    end

    subgraph "adk-fluent Layer"
        B["Builder API"] --> C["IR Tree"]
        C --> D{"Backend?"}
    end

    subgraph "ADK Layer"
        D -->|"default"| E["Native ADK Objects"]
        D -->|"temporal"| F["Temporal Workflow"]
        D -->|"asyncio"| G["Asyncio Interpreter"]
    end

    subgraph "Deployment"
        E --> H["adk web / run / deploy"]
        F --> I["Temporal Server"]
        G --> J["Python asyncio"]
    end

    A --> B

    style A fill:#1a1a2e,stroke:#e94560,color:#fff
    style B fill:#16213e,stroke:#e94560,color:#fff
    style C fill:#16213e,stroke:#0ea5e9,color:#fff
    style D fill:#0f3460,stroke:#f59e0b,color:#fff
    style E fill:#0f3460,stroke:#10b981,color:#fff
    style F fill:#0f3460,stroke:#a78bfa,color:#fff
    style G fill:#0f3460,stroke:#a78bfa,color:#fff
```

:::{tip}
**Mental model:** Think of builders as typed configuration objects that compile to ADK at `.build()` time. After `.build()`, adk-fluent is gone --- you have a pure ADK object.
:::

## Lifecycle of an Agent

Every agent follows the same path: configure with fluent methods, then compile to a native ADK object.

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant B as Builder
    participant IR as IR Tree
    participant ADK as Native ADK

    Dev->>B: Agent("helper", "gemini-2.5-flash")
    Dev->>B: .instruct("You are helpful.")
    Dev->>B: .tool(search_fn)
    Dev->>B: .writes("response")
    Dev->>B: .build()
    B->>IR: Compile builder state
    IR->>IR: Validate contracts
    IR->>ADK: Emit LlmAgent(...)
    Note over ADK: Pure ADK object ---<br/>works with adk web/run/deploy
```

## adk-fluent Concepts vs ADK Concepts

Every adk-fluent concept maps directly to an ADK concept. Nothing is invented --- everything compiles down.

| adk-fluent | ADK Equivalent | Relationship |
|---|---|---|
| `Agent` builder | `LlmAgent` | 1:1 --- identical object after `.build()` |
| `Pipeline` / `>>` | `SequentialAgent` | Sequential execution |
| `FanOut` / `\|` | `ParallelAgent` | Concurrent execution |
| `Loop` / `*` | `LoopAgent` | Iterative execution |
| `.instruct()` | `instruction` kwarg | System prompt |
| `.writes()` | `output_key` kwarg | State storage |
| `.returns()` | `output_schema` kwarg | Structured output |
| `.tool()` | `tools` list | Tool registration |
| `.sub_agent()` | `sub_agents` list | Transfer targets |
| S transforms | `FnAgent` (zero-cost) | State dict manipulation |
| IR Tree | _(no equivalent)_ | adk-fluent's compile step |

## The Nine Modules

adk-fluent organizes capabilities into nine composable modules. Each controls one concern.

```mermaid
graph TB
    subgraph "Prompt & Context"
        P["P — Prompt<br/>What the LLM is told"]
        C["C — Context<br/>What the agent sees"]
    end

    subgraph "Data Flow"
        S["S — State<br/>Transforms between agents"]
        A_["A — Artifacts<br/>File publish/load"]
    end

    subgraph "Quality & Safety"
        G["G — Guards<br/>Output validation"]
        E["E — Evaluation<br/>Testing & scoring"]
    end

    subgraph "Infrastructure"
        M["M — Middleware<br/>Retry, logging, cost"]
        T["T — Tools<br/>Tool composition"]
    end

    subgraph "Interface"
        UI["UI — Agent-to-UI<br/>Declarative UI"]
    end

    style P fill:#e94560,color:#fff
    style C fill:#0ea5e9,color:#fff
    style S fill:#10b981,color:#fff
    style A_ fill:#f59e0b,color:#fff
    style G fill:#f472b6,color:#fff
    style E fill:#a78bfa,color:#fff
    style M fill:#64748b,color:#fff
    style T fill:#06b6d4,color:#fff
    style UI fill:#8b5cf6,color:#fff
```

| Module | Import | Used With | Compose With |
|--------|--------|-----------|-------------|
| **S** — State | `from adk_fluent import S` | `>>` operator | `>>` (chain), `+` (combine) |
| **C** — Context | `from adk_fluent import C` | `.context()` | `+` (union), `\|` (pipe) |
| **P** — Prompt | `from adk_fluent import P` | `.instruct()` | `+` (union), `\|` (pipe) |
| **A** — Artifacts | `from adk_fluent import A` | `.artifacts()`, `>>` | `>>` (chain) |
| **M** — Middleware | `from adk_fluent import M` | `.middleware()` | `\|` (chain) |
| **T** — Tools | `from adk_fluent import T` | `.tools()` | `\|` (chain) |
| **E** — Evaluation | `from adk_fluent import E` | `.eval()` | builder pattern |
| **G** — Guards | `from adk_fluent import G` | `.guard()` | `\|` (chain) |
| **UI** — Agent-to-UI | `from adk_fluent import UI` | `.ui()` | `\|` (row), `>>` (column) |

---

## The Three Channels of ADK Communication

ADK has three independent mechanisms for agents to communicate. Every confusion about state traces back to not realizing they're three separate systems.

```mermaid
graph TB
    subgraph "Channel 1: Conversation History"
        CH1["All events appended to session.events<br/>Every agent sees prior agents' text by default<br/>Controlled by include_contents: 'default' or 'none'"]
    end

    subgraph "Channel 2: Session State"
        CH2["Flat dict at session.state<br/>Written via output_key or ctx.session.state<br/>Scoped: unprefixed, app:, user:, temp:"]
    end

    subgraph "Channel 3: Instruction Templating"
        CH3["{key} placeholders in instructions<br/>Replaced with state values before LLM call<br/>Bridge between state and prompt"]
    end

    CH1 -.->|"converge on"| LLM["LLM Prompt"]
    CH2 -.->|"converge on"| LLM
    CH3 -.->|"converge on"| LLM

    style CH1 fill:#0ea5e9,color:#fff
    style CH2 fill:#10b981,color:#fff
    style CH3 fill:#f59e0b,color:#fff
    style LLM fill:#e94560,color:#fff
```

:::{warning}
These three channels are configured independently but deeply entangled at runtime. A single agent response flows through **all three** simultaneously --- it becomes a conversation event, may be stored in state, and state values may appear in downstream instructions. This duplication is the source of most multi-agent debugging confusion.
:::

### Example: How Channels Converge

```python
classifier = Agent("classify").instruct("Classify intent.").writes("intent")
booker = Agent("booker").instruct("Help book. The intent is: {intent}")

pipeline = classifier >> booker
```

When `classifier` produces `"booking"`:

| Channel | What Happens | Result |
|---------|-------------|--------|
| **1. History** | `"booking"` appended to `session.events` | `booker` sees it in conversation |
| **2. State** | `state["intent"] = "booking"` via `output_key` | Available for `{intent}` template |
| **3. Template** | `{intent}` in `booker`'s instruction replaced | Instruction becomes `"Help book. The intent is: booking"` |

The booker's LLM sees `"booking"` **twice**: once in conversation history, once in the instruction. This isn't a bug --- it's three channels converging. adk-fluent's context engineering (C module) helps you control this.

---

## What `include_contents` Actually Does

The binary switch that controls conversation history visibility:

| Value | Behavior | Use Case |
|-------|----------|----------|
| `"default"` | Full conversation history (filtered, rearranged) | Conversational agents |
| `"none"` | Current turn only (latest user/agent message forward) | Stateless utility agents |

:::{warning}
`include_contents="none"` was designed for stateless utility agents that get all context from state variables. In a pipeline, a downstream agent with `"none"` **loses the user's original message**. Use `.reads()` or `.context(C.from_state(...))` to inject exactly the state keys you need.
:::

```mermaid
flowchart LR
    subgraph "include_contents = 'default'"
        D1["User msg"] --> D2["Agent A reply"] --> D3["Agent B reply"] --> D4["Agent C sees ALL"]
    end

    subgraph "include_contents = 'none'"
        N1["User msg"] --> N2["Agent A reply"] --> N3["Agent B reply"]
        N3 --> N4["Agent C sees ONLY<br/>Agent B's reply onward"]
    end
```

There is no `"user_only"` or `"exclude_agents"` in native ADK. adk-fluent bridges this gap with the **C module**: `C.user_only()`, `C.from_agents()`, `C.window()`, and more. See [Context Engineering](context-engineering.md).

---

## What `output_key` Actually Does

:::{note}
`output_key` is a **duplication** mechanism, not a **routing** mechanism. It copies the LLM's text response into state under a named key. The original text still exists in conversation history.
:::

```mermaid
sequenceDiagram
    participant LLM as LLM
    participant E as Event
    participant H as Conversation History
    participant St as Session State

    LLM->>E: Response text: "booking"
    Note over E: event.actions.state_delta<br/>mutated in-place
    E->>H: Append to session.events<br/>(text in conversation)
    E->>St: state["intent"] = "booking"<br/>(text in state)
    Note over H,St: Both writes happen<br/>atomically from same event
```

Downstream agents get the response through **both** channels. Use `.context(C.none())` or `.reads()` on downstream agents to suppress the conversation channel when you only want structured state data.

---

## The Five Orthogonal Data Flow Concerns

Every data-flow method in adk-fluent maps to exactly one of five concerns. They are fully independent of each other.

| Concern | Method | Controls | When |
|---------|--------|----------|------|
| **Context** | `.reads()`, `.context()` | What the agent SEES | Before LLM call |
| **Input** | `.accepts()` | Schema for tool-mode invocation | At tool-call time |
| **Output** | `.returns()`, `@ Schema` | Response shape (structured JSON) | During LLM call |
| **Storage** | `.writes()` | Where response is saved in state | After LLM call |
| **Contract** | `.produces()`, `.consumes()` | Static annotations for validation | Build time only |

```python
classifier = (
    Agent("classifier", "gemini-2.0-flash")
    .instruct("Classify the user query: {query}")
    .reads("query")              # CONTEXT: sees state["query"] only
    .accepts(SearchQuery)        # INPUT:   tool-mode validation
    .returns(Intent)             # OUTPUT:  structured JSON response
    .writes("intent")            # STORAGE: save to state["intent"]
    .produces(Intent)            # CONTRACT: static annotation
)
```

:::{seealso}
[Data Flow](data-flow.md) for detailed diagrams and examples of each concern.
:::

---

## What the S Module Does

The S module provides pure state transforms that compile to zero-cost `FnAgent` nodes --- no LLM calls, no events, just dict manipulation.

```mermaid
graph LR
    A1["Agent A<br/>.writes('findings')"] -->|state| S1["S.pick('findings')"]
    S1 -->|state| S2["S.rename(findings='input')"]
    S2 -->|state| A2["Agent B<br/>.reads('input')"]

    style S1 fill:#10b981,color:#fff
    style S2 fill:#10b981,color:#fff
```

S transforms operate exclusively on **Channel 2** (session state). They don't touch conversation history or instruction templating. This makes them predictable and composable.

| Transform | Effect | Type |
|-----------|--------|------|
| `S.pick(*keys)` | Keep only named keys | Replacement |
| `S.drop(*keys)` | Remove named keys | Replacement |
| `S.rename(**mapping)` | Rename keys | Replacement |
| `S.merge(*keys, into=)` | Combine keys | Delta |
| `S.transform(key, fn)` | Apply function to value | Delta |
| `S.compute(**factories)` | Derive new keys | Delta |
| `S.set(**kv)` | Set explicit values | Delta |
| `S.default(**kv)` | Fill missing keys | Delta |
| `S.guard(pred, msg=)` | Assert state invariant | Inspection |
| `S.log(*keys)` | Debug print | Inspection |

:::{seealso}
[State Transforms](state-transforms.md) for visual before/after diagrams of each transform.
:::

---

## What adk-fluent Infers From Topology

The library doesn't just wrap ADK --- it performs three kinds of inference that native ADK requires you to do manually:

### 1. Data contract verification

When you write `.writes("intent")` upstream and `Route("intent")` downstream, the contract checker verifies at build time that the data flow is satisfiable. If you forget `.writes()`, it flags the issue before any LLM call.

### 2. Topology-aware context filtering

The C module provides fine-grained control that ADK's binary `include_contents` switch cannot:

```python
# Agent sees only the user's messages + last 3 turns
agent.context(C.user_only() + C.window(n=3))

# Agent sees only state keys, no conversation history
agent.reads("topic", "constraints")
```

### 3. Cross-channel coherence analysis

The contract checker warns about common pitfalls:

| Pitfall | What Happens | How to Fix |
|---------|-------------|------------|
| Agent B references `{intent}` but no upstream writes `"intent"` | Template resolves to empty string | Add `.writes("intent")` to upstream agent |
| Agent A has `.writes("intent")` but B has full history | B sees `"booking"` twice (state + conversation) | Add `.reads("intent")` to B |
| Agent A has no `.writes()` and B has `.context(C.none())` | A's output reaches B through neither channel | Add `.writes()` to A or change B's context |

---

## Native ADK vs adk-fluent

::::{tab-set}
:::{tab-item} Native ADK
```python
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import FunctionTool

classifier = LlmAgent(
    name="classifier",
    model="gemini-2.5-flash",
    instruction="Classify the intent.",
    output_key="intent",
)

handler = LlmAgent(
    name="handler",
    model="gemini-2.5-flash",
    instruction="Handle the {intent} query.",
    include_contents="none",
)

pipeline = SequentialAgent(
    name="pipeline",
    sub_agents=[classifier, handler],
)
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent

pipeline = (
    Agent("classifier", "gemini-2.5-flash")
    .instruct("Classify the intent.")
    .writes("intent")
    >> Agent("handler", "gemini-2.5-flash")
    .instruct("Handle the {intent} query.")
    .reads("intent")
).build()
```
:::
::::

Both produce identical ADK objects. The fluent version is shorter, catches typos at definition time, and makes data flow explicit.

---

## When to Use What

```mermaid
flowchart TD
    START{What are you building?} -->|"Single agent"| SINGLE["Agent builder<br/><code>Agent('name', 'model')</code>"]
    START -->|"Multiple agents"| MULTI{How do they interact?}

    MULTI -->|"Run in sequence"| SEQ["Pipeline / >><br/><code>a >> b >> c</code>"]
    MULTI -->|"Run in parallel"| PAR["FanOut / |<br/><code>a | b | c</code>"]
    MULTI -->|"Iterate until done"| LOOP["Loop / *<br/><code>(a >> b) * 3</code>"]
    MULTI -->|"LLM picks the agent"| TRANSFER[".sub_agent()<br/>Transfer routing"]
    MULTI -->|"Route by state value"| ROUTE["Route<br/><code>Route('key').eq(...)</code>"]
    MULTI -->|"Try cheaper first"| FALL["Fallback / //<br/><code>fast // strong</code>"]

    style START fill:#e94560,color:#fff
    style SINGLE fill:#0ea5e9,color:#fff
    style SEQ fill:#10b981,color:#fff
    style PAR fill:#0ea5e9,color:#fff
    style LOOP fill:#f59e0b,color:#fff
    style TRANSFER fill:#a78bfa,color:#fff
    style ROUTE fill:#f472b6,color:#fff
    style FALL fill:#a78bfa,color:#fff
```

---

## Common Mistakes

::::{grid} 1
:gutter: 3

:::{grid-item-card} Forgetting `.writes()` before a Route
:class-card: sd-border-danger

```python
# ❌ Wrong — Route reads state["intent"] but nobody writes it
classifier = Agent("classify").instruct("Classify.")
pipeline = classifier >> Route("intent").eq("booking", booker)
```

```python
# ✅ Correct — classifier writes to state
classifier = Agent("classify").instruct("Classify.").writes("intent")
pipeline = classifier >> Route("intent").eq("booking", booker)
```
:::

:::{grid-item-card} Using full history when you only need state
:class-card: sd-border-danger

```python
# ❌ Wrong — handler sees "booking" twice (history + template)
handler = Agent("handler").instruct("Handle {intent}.")
```

```python
# ✅ Correct — suppress history, use only state
handler = Agent("handler").instruct("Handle {intent}.").reads("intent")
```
:::

:::{grid-item-card} Calling `.build()` on sub-builders
:class-card: sd-border-danger

```python
# ❌ Wrong — don't build sub-builders manually
Pipeline("flow")
    .step(Agent("a").instruct("...").build())  # NO!
    .build()
```

```python
# ✅ Correct — let the parent auto-build children
Pipeline("flow")
    .step(Agent("a").instruct("..."))
    .build()
```
:::
::::

---

## Interplay With Other Concepts

```mermaid
graph TB
    ARCH[["Architecture &<br/>Core Concepts"]]
    EXPR["Expression Language"]
    DATA["Data Flow"]
    BUILD["Builders"]
    PATT["Patterns"]
    CTX["Context Engineering"]
    ST["State Transforms"]

    ARCH --> EXPR
    ARCH --> DATA
    ARCH --> BUILD
    EXPR --> PATT
    DATA --> CTX
    DATA --> ST

    style ARCH fill:#e65100,color:#fff
```

| Concept | Relationship |
|---------|-------------|
| [Expression Language](expression-language.md) | Operators that compose builders into topologies |
| [Data Flow](data-flow.md) | The five concerns that control agent I/O |
| [Builders](builders.md) | The fluent API for configuring agents |
| [Context Engineering](context-engineering.md) | Fine-grained control over what agents see |
| [State Transforms](state-transforms.md) | Data manipulation between pipeline steps |
| [Patterns](patterns.md) | Higher-order constructors for common architectures |

---

## API Quick Reference

| Method | Purpose | Details |
|--------|---------|---------|
| `.model(str)` | Set LLM model | [Builders](builders.md) |
| `.instruct(str \| P)` | System prompt | [Prompts](prompts.md) |
| `.tool(fn)` | Add tool | [Builders](builders.md) |
| `.writes(key)` | Store output in state | [Data Flow](data-flow.md) |
| `.reads(*keys)` | Inject state keys | [Data Flow](data-flow.md) |
| `.returns(Schema)` | Structured output | [Structured Data](structured-data.md) |
| `.context(C)` | Context control | [Context Engineering](context-engineering.md) |
| `.sub_agent(agent)` | Transfer target | [Transfer Control](transfer-control.md) |
| `.build()` | Compile to ADK | [Builders](builders.md) |

---

:::{seealso}
- {doc}`expression-language` --- compose agents with operators
- {doc}`data-flow` --- the five orthogonal data flow concerns
- {doc}`builders` --- full builder method reference
- {doc}`../getting-started` --- 5-minute quickstart
- [ADK Documentation](https://google.github.io/adk-docs/) --- upstream Google ADK docs
:::
