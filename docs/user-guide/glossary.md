# Glossary

:::{admonition} At a Glance
:class: tip

Term definitions for adk-fluent concepts. If a term confuses you, find it here.
:::

## A

**A2A (Agent-to-Agent)**
: Remote agent communication protocol. Allows agents to call other agents over HTTP. See {doc}`a2a`.

**A2UI (Agent-to-UI)**
: Declarative UI composition for agents. Agents can generate UI surfaces. See {doc}`a2ui`.

**ADK (Agent Development Kit)**
: Google's framework for building AI agents. adk-fluent is a builder layer on top of ADK. Every `.build()` returns a native ADK object.

**Agent**
: The core builder. Configures an `LlmAgent` via fluent method calls. `Agent("name", "model")` is the starting point for everything.

**AgentTool**
: An agent wrapped as a callable tool. The parent LLM invokes the child like any function. Created via `.agent_tool(agent)`. Compare with sub-agent (transfer-based).

**Artifact**
: A file or blob managed by the A module. Published from state, loaded back into state. See A module in {doc}`data-flow`.

## B

**Backend**
: The execution engine that runs compiled IR trees. Options: ADK (default, stable), Temporal (in dev), asyncio (in dev). See {doc}`execution-backends`.

**Builder**
: A fluent configuration object that compiles to a native ADK object via `.build()`. 132 builders across 9 modules.

**Build time**
: When `.build()` is called. Contracts are checked, IR is compiled, and the native ADK object is created. No LLM calls happen at build time.

## C

**C module (Context)**
: Namespace for controlling what conversation history and state each agent sees. `C.none()`, `C.window(n)`, `C.from_state()`, etc. See {doc}`context-engineering`.

**Callback**
: A function attached to an agent's lifecycle (before/after model, agent, tool). Additive in adk-fluent --- multiple calls stack. See {doc}`callbacks`.

**Contract**
: A static annotation (`.produces()`, `.consumes()`) that declares what state keys an agent reads and writes. Verified at build time by `check_contracts()`. No runtime effect.

**Context caching**
: When `.static()` is set, the static prompt is cached by the model provider. Dynamic `.instruct()` text moves to user content.

## D

**Data flow**
: The five orthogonal concerns: Context, Input, Output, Storage, Contract. Each controlled by a separate builder method. See {doc}`data-flow`.

**Delta transform**
: An S transform that only updates specified keys, preserving everything else. Examples: `S.default()`, `S.merge()`, `S.transform()`.

## E

**E module (Evaluation)**
: Namespace for quality assessment. `E.case()`, `E.criterion()`, `EvalSuite`. See {doc}`evaluation`.

**Expression operators**
: Python operators (`>>`, `|`, `*`, `@`, `//`) overloaded to compose agent topologies. See {doc}`expression-language`.

## F

**FanOut**
: Parallel execution builder. Runs branches concurrently. `FanOut("name").branch(a).branch(b).build()` or `a | b`. Compiles to `ParallelAgent`.

**Fallback**
: Try agents in order; first success wins. `a // b // c`. See {doc}`expression-language`.

**FnAgent**
: A zero-cost agent that executes a Python function (no LLM call). S transforms compile to FnAgent nodes.

## G

**G module (Guards)**
: Namespace for output validation. `G.pii()`, `G.length()`, `G.schema()`. Guards compile to `after_model` callbacks. See {doc}`guards`.

**Guard**
: A validation function that checks LLM output. Raises `GuardViolation` on failure. Composed with `|`.

## I

**Immutability**
: All expression operators produce new objects. Sub-expressions can be safely reused across different pipelines.

**IR (Intermediate Representation)**
: A frozen dataclass tree that represents the agent topology. Created by `.to_ir()`. Backends compile IR into executable code. See {doc}`ir-and-backends`.

**`include_contents`**
: ADK's binary switch for conversation history. `"default"` (full history) or `"none"` (current turn only). adk-fluent's C module provides finer control.

## L

**Loop**
: Iterative execution builder. `Loop("name").step(a).max_iterations(3).build()` or `(a >> b) * 3`. Compiles to `LoopAgent`.

## M

**M module (Middleware)**
: Namespace for pipeline-wide cross-cutting concerns. `M.retry()`, `M.log()`, `M.cost()`. Applied to entire pipelines, not individual agents. See {doc}`middleware`.

**Memory**
: Persistent state across sessions. `.memory()` attaches memory tools. See {doc}`memory`.

**Mock backend**
: A test backend that returns canned responses without LLM calls. Created via `mock_backend()`. See {doc}`testing`.

## O

**`output_key`**
: ADK field that stores the LLM's text response in session state. Set via `.writes()` in adk-fluent. It's a duplication mechanism --- the text also remains in conversation history.

**`output_schema`**
: ADK field that constrains the LLM to produce JSON matching a Pydantic model. Set via `.returns()` or `@ Schema`.

## P

**P module (Prompt)**
: Namespace for structured prompt composition. `P.role()`, `P.task()`, `P.constraint()`. Sections are ordered and composable. See {doc}`prompts`.

**Pipeline**
: Sequential execution builder. `Pipeline("name").step(a).step(b).build()` or `a >> b`. Compiles to `SequentialAgent`.

**Preset**
: A reusable configuration bundle applied with `.use()`. Bundles model, instructions, tools, callbacks. See {doc}`presets`.

## R

**Replacement transform**
: An S transform that replaces session-scoped keys. Unmentioned keys become `None`. Examples: `S.pick()`, `S.drop()`, `S.rename()`.

**Route**
: Deterministic state-based routing without LLM calls. `Route("key").eq("value", agent)`. See {doc}`expression-language`.

## S

**S module (State)**
: Namespace for state transforms between agent steps. `S.pick()`, `S.merge()`, `S.rename()`. Compile to zero-cost FnAgent nodes. See {doc}`state-transforms`.

**Session state**
: Flat dictionary at `session.state`. Scoped: unprefixed (session), `app:`, `user:`, `temp:`. The primary data channel between agents.

**Sub-agent**
: An agent added as a transfer target via `.sub_agent()`. The LLM decides when to hand off. Compare with AgentTool (tool-based invocation).

## T

**T module (Tools)**
: Namespace for tool composition. `T.fn()`, `T.agent()`, `T.mcp()`. Compose with `|`. See CLAUDE.md reference.

**Transfer control**
: Mechanisms for routing between agents: `.sub_agent()` (LLM decides), `.agent_tool()` (parent stays in control), `.isolate()` (no transfers). See {doc}`transfer-control`.

## U

**UI module (Agent-to-UI)**
: Namespace for declarative UI composition. `UI.text()`, `UI.button()`, `UI.form()`. Compose with `|` (row) and `>>` (column). See {doc}`a2ui`.

**`until(pred, max=)`**
: Loop condition for the `*` operator. Loops until `pred(state)` is true, with a safety limit. `(a >> b) * until(pred, max=5)`.

---

:::{seealso}
- {doc}`concept-map` --- visual map of all concepts
- {doc}`cheat-sheet` --- one-page API reference
- {doc}`architecture-and-concepts` --- system architecture
:::
