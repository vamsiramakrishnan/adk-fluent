---
name: adk-fluent-complete
description: >
  Comprehensive adk-fluent library reference for AI coding assistants.
  Auto-generated from source code introspection — always up to date.
  Covers all 133 builders, 9 namespace modules (S/C/P/A/M/T/E/G/UI),
  expression operators, composition patterns, A2A, and best practices.
  Use this skill to write accurate adk-fluent code without hallucination.
metadata:
  license: Apache-2.0
  author: vamsiramakrishnan
  version: "0.1"
---

# adk-fluent Complete Reference

> **Auto-generated** from manifest.json, seed.toml, and source code introspection.
> Package version: 0.1 | Builders: 133
> Regenerate: `just skills`

This skill provides the full adk-fluent library reference for AI coding
assistants. It enables accurate code generation, API lookups, and
architecture guidance without hallucinating non-existent methods.

## Install & Import

```bash
pip install adk-fluent
```

```python
from adk_fluent import Agent, Pipeline, FanOut, Loop, Route, Fallback
from adk_fluent import S, C, P, A, M, T, E, G, UI
from adk_fluent import until, tap, expect, map_over, gate, race
```

Never import from internal modules (`adk_fluent._base`, `adk_fluent.agent`).

---

## Core API patterns

### Fluent builder pattern

Every builder takes a required `name` as the first positional argument.
Agent accepts an optional `model` as the second positional argument.
Methods are chainable and can be called in any order.
Call `.build()` to resolve into a native ADK object.

    agent = (
        Agent("helper", "gemini-2.5-flash")
        .instruct("You are a helpful assistant.")
        .tool(search_fn)
        .build()
    )

Sub-builders passed to workflow builders are auto-built — do not call
`.build()` on individual steps.

### Workflow builders

Pipeline (sequential):

    pipeline = (
        Pipeline("flow")
        .step(Agent("a", "gemini-2.5-flash").instruct("Step 1.").writes("result"))
        .step(Agent("b", "gemini-2.5-flash").instruct("Step 2 using {result}."))
        .build()
    )

FanOut (parallel):

    fanout = (
        FanOut("parallel")
        .branch(Agent("web", "gemini-2.5-flash").instruct("Search web."))
        .branch(Agent("papers", "gemini-2.5-flash").instruct("Search papers."))
        .build()
    )

Loop:

    loop = (
        Loop("refine")
        .step(Agent("writer", "gemini-2.5-flash").instruct("Write."))
        .step(Agent("critic", "gemini-2.5-flash").instruct("Critique."))
        .max_iterations(3)
        .build()
    )

### Expression operators (alternative syntax)

All operators are immutable (copy-on-write). Sub-expressions can be reused.

    pipeline = Agent("a") >> Agent("b")          # Sequential (>>)
    fanout   = Agent("a") | Agent("b")           # Parallel (|)
    loop     = (Agent("a") >> Agent("b")) * 3    # Loop (*)

    # Conditional loop
    loop = (Agent("a") >> Agent("b")) * until(lambda s: s.get("done"), max=5)

    # Fallback chain
    result = Agent("fast", "gemini-2.5-flash") // Agent("strong", "gemini-2.5-pro")

    # Structured output
    agent = Agent("parser") @ MyPydanticSchema

    # Function steps (zero-cost, no LLM)
    pipeline = Agent("a") >> some_function >> Agent("b")

    # Deterministic routing
    router = Route("tier").eq("VIP", vip_agent).otherwise(standard_agent)

---

## Agent builder methods

### Core configuration

  .model(str)                  — set LLM model
  .instruct(str | PTransform)  — set the main instruction / system prompt. This is what
                                 the LLM is told to do. Accepts plain text, a callable,
                                 or a P module composition (P.role() | P.task() | ...).
  .describe(str)               — set agent description (metadata for transfer routing
                                 and topology — NOT sent to the LLM as instruction)
  .static(str)                 — set cached instruction. When set, .instruct() text moves
                                 from system to user content, enabling context caching.
                                 Use for large, stable prompt sections.
  .global_instruct(str)        — set instruction shared by ALL agents in a workflow.
                                 Only meaningful on the root agent. Prepended to every
                                 agent's system prompt.
  .generate_content_config()   — model-level config (temperature, top_p, etc.)

### Data flow (five orthogonal concerns)

Each method controls exactly one concern. See `data_flow()` for a snapshot.

  .reads(*keys)                — CONTEXT: inject state[key] values into agent's prompt.
                                 Side-effect: sets include_contents="none" (suppresses
                                 full conversation history; current turn is still visible).
  .context(C.xxx())            — CONTEXT: fine-grained control over what the agent sees.
                                 Pass a C transform (C.window(5), C.user_only(), etc.).
  .accepts(Schema)             — INPUT: validate input when this agent is invoked as a
                                 tool via .delegate_to(). No effect for top-level agents.
  .returns(Schema)             — OUTPUT: constrain LLM response to structured JSON
                                 matching a Pydantic model. HAS runtime effect.
  .writes(key)                 — STORAGE: store the agent's text response in state[key]
                                 after execution.
  .produces(Schema)            — CONTRACT: static annotation only — documents what state
                                 keys this agent writes. NO runtime effect.
  .consumes(Schema)            — CONTRACT: static annotation only — documents what state
                                 keys this agent needs. NO runtime effect.

### Tools

  .tool(fn)                    — add a single tool (appends to existing tools)
  .tools(list | TComposite)    — set / replace all tools at once
  .delegate_to(agent)          — wrap another agent as a callable AgentTool. The parent
                                 LLM invokes the child like any other tool and stays in
                                 control. Compare with .transfer_to() which fully transfers
                                 control to the child.

### Callbacks

  .before_agent(fn)            — run before agent executes
  .after_agent(fn)             — run after agent executes
  .before_model(fn)            — run before LLM call
  .after_model(fn)             — run after LLM call
  .before_tool(fn)             — run before tool call
  .after_tool(fn)              — run after tool call
  .guard(fn | G.xxx())         — output validation guard. Accepts a G composite
                                 (G.pii() | G.length(max=500)) or a plain callable.
                                 Guards run as after_model callbacks and validate/transform
                                 the LLM response before it is returned.
  .on_model_error(fn)          — error callback for LLM failures
  .on_tool_error(fn)           — error callback for tool failures

### Flow control

  .loop_until(pred, max=10)    — loop while predicate is false
  .loop_while(pred, max=3)     — loop while predicate is true
  .until(pred)                 — alias for loop_until
  .proceed_if(pred)            — conditional execution
  .timeout(seconds)            — wrap with time limit (returns TimedAgent)
  .dispatch(name=, on_complete=) — fire-and-forget background task (non-blocking)

### Reactive (R namespace)

  .on(predicate, handler=None, *, priority=0, preemptive=False)
                               — declarative reactor rule. When ``predicate``
                                 matches a SignalChanged event on the tape,
                                 ``handler`` fires with priority-based
                                 scheduling. If ``handler`` is omitted the
                                 builder itself becomes the handler and is
                                 invoked via ``.run.ask`` (which returns a
                                 coroutine inside the reactor loop). Works on any
                                 builder (Agent, Pipeline, FanOut, Loop).
                                 Accepts either a SignalPredicate or a bare
                                 Signal (promoted to ``.changed``). Rules are
                                 materialized by ``R.compile(*builders, tape=,
                                 bus=)`` into a ready-to-run :class:`Reactor`.

### Transfer control (multi-agent routing)

  .transfer_to(agent)          — add child agent as a transfer target. The LLM decides
                                 when to hand off via the transfer_to_agent tool.
  .isolate()                   — prevent transfers to parent AND peers. Agent completes
                                 its task, then control auto-returns to parent.
                                 Most common pattern for specialist agents.
  .stay()                      — prevent transfer to parent only (can still transfer to
                                 sibling peers). Equivalent to
                                 .disallow_transfer_to_parent(True).
  .no_peers()                  — prevent transfer to siblings only (can still return to
                                 parent). Equivalent to
                                 .disallow_transfer_to_peers(True).

### Memory

  .memory(mode="preload")      — attach memory tools
  .memory_auto_save()          — auto-save to memory after execution

### Visibility

  .show()                      — include in topology
  .hide()                      — exclude from topology
  .transparent()               — transparent visibility mode
  .filtered()                  — filtered visibility mode
  .annotated()                 — annotated visibility mode

### Configuration

  .middleware(mw)              — attach middleware
  .inject(**resources)         — inject named resources into tool function parameters.
                                 Matched by parameter name at build time. Injected params
                                 are hidden from the LLM tool schema. Use for DB clients,
                                 API keys, config objects.
  .use(preset)                 — apply a Preset object that bundles multiple builder
                                 settings (model, instruction, tools, callbacks, etc.)
  .native(fn)                  — post-build hook: fn receives the raw ADK object for
                                 direct manipulation. Escape hatch for ADK features not
                                 yet exposed by the fluent API.
  .debug(enabled=True)         — debug tracing to stderr
  .strict()                    — enable strict contract checking
  .unchecked()                 — bypass contract checking
  .prepend(fn)                 — prepend dynamic text to the LLM's input via
                                 before_model_callback. fn(ctx) → str is injected before
                                 the main instruction each turn.

### Schemas

  .tool_schema(schema)         — attach tool schema
  .callback_schema(schema)     — attach callback schema
  .prompt_schema(schema)       — attach prompt schema
  .artifact_schema(schema)     — attach artifact schema
  .artifacts(*transforms)      — artifact operations

### Execution

``.ask`` and ``.map`` are dual-mode. In sync code they block and return
the result. Inside a running event loop (Jupyter, FastAPI,
pytest-asyncio) they return an awaitable coroutine, so just ``await`` the
same call — there is no separate ``.ask_async`` / ``.map_async``.

  .build()                     — produce native ADK LlmAgent
  .ask(prompt)                 — one-shot execution. Blocks in sync code;
                                 returns an awaitable coroutine in async
  .stream(prompt)              — ASYNC streaming iterator (yields text chunks)
  .events(prompt)              — ASYNC raw ADK Event stream
  .session()                   — ASYNC context manager for multi-turn chat
  .map(prompts, concurrency=5) — batch execution (dual-mode, like .ask)
  .test(prompt, contains=)     — inline smoke test (sync, blocking)
  .mock(responses)             — replace LLM with canned responses
  .eval(prompt, expect=)       — inline evaluation
  .eval_suite()                — evaluation suite builder

### Introspection

  .show(mode="default")        — one verb, many views. Modes:
                                 "default"|"rich" rich tree, "plain" text dump,
                                 "doctor" formatted diagnostic report,
                                 "diagnose" structured Diagnosis dataclass,
                                 "data_flow" five-concern snapshot,
                                 "llm"|"anatomy" LLM call anatomy,
                                 "mermaid" topology diagram,
                                 "sequence" sequence diagram,
                                 "json"|"dict" serializable dict,
                                 "yaml" YAML string.
  .validate()                  — early error detection
  .clone(name)                 — deep copy with new name
  .with_(**overrides)          — immutable variant
  .to_ir()                     — convert to IR tree
  .to_mermaid()                — generate Mermaid diagram (alias for .show("mermaid"))
  .to_dict() / .to_yaml()     — serialization

---

## Namespace modules (S, C, P, A, M, T, E, G)

### S — State transforms

Used with `>>` operator. Compose with `>>` (pipe: feed output into next) or
`|` (combine: both transforms run on original state, deltas merge).

  S.pick(*keys)                — keep only named keys
  S.drop(*keys)                — remove named keys
  S.rename(**mapping)          — rename keys
  S.merge(*keys, into=)        — combine keys
  S.transform(key, fn)         — apply function to value
  S.compute(**factories)       — derive new keys from state
  S.set(**kv)                  — set explicit key-value pairs
  S.default(**kv)              — fill missing keys with defaults
  S.guard(pred, msg=)          — assert state invariant
  S.when(pred, transform)      — conditional transform
  S.branch(key, **transforms)  — route to different transforms
  S.capture(*keys)             — capture function args into state
  S.identity()                 — pass-through (no-op)
  S.accumulate(key)            — append to list in state
  S.counter(key)               — increment counter in state
  S.history(key)               — maintain history list
  S.validate(**schemas)        — validate state keys against schemas
  S.require(*keys)             — assert keys exist
  S.flatten(key)               — flatten nested dict
  S.unflatten(key, sep=".")    — unflatten dotted keys
  S.zip(*keys, into=)          — zip parallel lists
  S.group_by(key, by=)         — group items by field
  S.log(*keys)                 — log state keys to stderr

### C — Context engineering

Used with `.context()`. Compose with `|` (union: merge transforms) or `>>` (pipe:
post-process compiled output through a transform).

  C.none()                     — suppress all history
  C.default()                  — default ADK behavior
  C.user_only()                — only user messages
  C.window(n=5)                — last N turn-pairs
  C.from_state(*keys)          — inject state keys as context
  C.from_agents(*names)        — user + named agent outputs
  C.from_agents_windowed(n=)   — windowed agent output filtering
  C.exclude_agents(*names)     — exclude named agents
  C.template(text)             — template with {key} placeholders
  C.select(*agent_names)       — select specific agents
  C.recent(n=)                 — recent messages only
  C.compact()                  — remove redundant messages
  C.dedup()                    — remove duplicate messages
  C.truncate(max_turns=)       — hard limit
  C.project(*fields)           — project specific fields
  C.budget(max_tokens=)        — token budget constraint
  C.priority(*keys)            — prioritize certain context
  C.fit(max_tokens=)           — fit within token limit
  C.fresh(max_age=)            — filter by recency
  C.redact(*patterns)          — redact sensitive content
  C.summarize(scope=)          — LLM-powered summarization
  C.relevant(query_key=)       — semantic relevance filtering
  C.extract(key=)              — extract structured data
  C.distill()                  — distill to key points
  C.validate()                 — validate context integrity
  C.notes()                    — attach notes
  C.write_notes()              — persist notes to state
  C.rolling(n=)                — rolling window with compaction
  C.user()                     — user messages only (alias)
  C.manus_cascade()            — Manus-style cascading context
  C.when(pred, transform)      — conditional context transform

### P — Prompt composition

Used with `.instruct()`. Compose with `|` (union: merge sections) or `>>` (pipe:
post-process compiled output through a transform).
Section order: role → context → task → constraint → format → example.

  P.role(text)                 — agent persona
  P.context(text)              — background context
  P.task(text)                 — primary objective
  P.constraint(*rules)         — constraints/rules
  P.format(text)               — output format spec
  P.example(input=, output=)   — few-shot examples
  P.section(name, text)        — custom named section
  P.when(pred, block)          — conditional inclusion
  P.from_state(*keys)          — dynamic state injection
  P.template(text)             — {key}, {key?}, {ns:key} placeholders
  P.reorder(*sections)         — reorder sections
  P.only(*sections)            — include only named sections
  P.without(*sections)         — exclude named sections
  P.compress()                 — compress verbose prompts
  P.adapt(fn)                  — transform prompt dynamically
  P.scaffolded(structure)      — structured prompt scaffold
  P.versioned(v, text)         — versioned prompt variants

### A — Artifacts

Used with `.artifacts()` or `>>`. Compose with `>>` (chain).

  A.publish(filename, from_key=) — state → artifact
  A.snapshot(filename, into_key=) — artifact → state
  A.save(filename, content=)    — content → artifact
  A.load(filename)              — artifact → pipeline
  A.list()                      — list available artifacts
  A.version(filename)           — get artifact version
  A.delete(filename)            — delete artifact
  A.publish_many(**mapping)     — batch publish multiple artifacts
  A.snapshot_many(**mapping)    — batch snapshot multiple artifacts
  A.for_llm()                  — context transform for LLM-aware loading
  A.when(pred, transform)      — conditional artifact operation
  A.from_json() / A.from_csv() / A.from_markdown() — content transforms (pre-publish)
  A.as_json() / A.as_csv() / A.as_text() — content transforms (post-snapshot)

### M — Middleware

Used with `.middleware()`. Compose with `|` (chain).

  M.retry(max_attempts=)       — retry with exponential backoff
  M.log()                      — structured event logging
  M.cost()                     — token usage tracking
  M.latency()                  — per-agent latency tracking
  M.scope(agents, mw)          — restrict middleware to agents
  M.when(condition, mw)        — conditional middleware
  M.circuit_breaker(max_fails=) — circuit breaker pattern
  M.timeout(seconds)           — per-agent timeout
  M.cache(ttl=)                — response caching
  M.fallback_model(model)      — fallback to different model
  M.dedup()                    — deduplicate requests
  M.sample(rate=)              — probabilistic sampling
  M.trace()                    — distributed tracing
  M.metrics()                  — metrics collection
  M.before_agent(fn)           — pre-agent hook
  M.after_agent(fn)            — post-agent hook
  M.before_model(fn)           — pre-model hook
  M.after_model(fn)            — post-model hook
  M.on_loop(fn)                — loop iteration hook
  M.on_timeout(fn)             — timeout event hook
  M.on_route(fn)               — routing event hook
  M.on_fallback(fn)            — fallback event hook

### T — Tool composition

Used with `.tools()`. Compose with `|` (chain).

  T.fn(callable)               — wrap callable as FunctionTool
  T.agent(agent)               — wrap agent as AgentTool
  T.google_search()            — built-in Google Search
  T.search(registry)           — BM25-indexed dynamic loading
  T.toolset(toolset)           — wrap MCPToolset or similar
  T.schema(schema)             — attach ToolSchema
  T.mock(responses)            — mock tool for testing
  T.confirm(prompt=)           — human confirmation wrapper
  T.timeout(seconds)           — tool timeout wrapper
  T.cache(ttl=)                — tool response caching
  T.mcp(server)                — MCP server tool
  T.openapi(spec)              — OpenAPI spec tool
  T.transform(fn)              — transform tool output

### E — Evaluation

Used with `.eval()` and `.eval_suite()`. Build evaluation criteria and test suites.

  E.case(prompt, expect=)      — single evaluation case
  E.criterion(name, fn)        — custom evaluation criterion
  E.persona(name, style=)      — persona for evaluation
  EvalSuite                    — collection of eval cases
  EvalReport                   — evaluation results
  ComparisonReport             — compare multiple agents/models

### G — Guards (output validation)

Used with `.guard()`. Guards validate/transform the LLM response (after_model).
Compose with `|` (chain). Raise GuardViolation on failure.

  G.guard(fn)                  — custom guard function (fn receives llm_response)
  G.pii(detector=)             — detect and block/redact PII in output
  G.toxicity(threshold=)       — block toxic content above threshold
  G.length(max=)               — enforce max response length
  G.schema(model)              — validate output against Pydantic model
  GuardViolation               — raised when a guard check fails
  PIIDetector                  — PII detection provider
  ContentJudge                 — content judgment provider

### UI — Agent-to-UI composition (A2UI)

Declarative UI composition for agents. Compose with `|` (Row), `>>` (Column).
Import: ``from adk_fluent import UI`` or ``from adk_fluent._ui import UI``.

Component factories:
  UI.text(content, variant=)   — text content (h1-h5, caption, body)
  UI.button(label, action=)    — clickable button
  UI.text_field(label, bind=)  — text input with optional data binding
  UI.image(src, alt=, fit=)    — display an image
  UI.row(*children)            — horizontal layout
  UI.column(*children)         — vertical layout
  UI.component(kind, **props)  — generic escape hatch

Data binding & validation:
  UI.bind(path)                — create data binding to JSON Pointer path
  UI.required(msg=)            — required field validation
  UI.email(msg=)               — email format validation

Surface lifecycle:
  UI.surface(name, *children)  — create named surface (compilation root)
  UI.auto(catalog=)            — LLM-guided mode (agent decides UI)

Presets:
  UI.form(title, fields=)      — form surface from field spec
  UI.dashboard(title, cards=)  — dashboard with metric cards
  UI.wizard(title, steps=)     — multi-step wizard
  UI.confirm(message)          — confirmation dialog
  UI.table(columns, data_bind=) — data table

Agent integration:
  Agent.ui(spec)               — attach UI surface to agent
  T.a2ui()                     — A2UI toolset for LLM-guided mode
  G.a2ui(max_components=)      — validate LLM-generated UI
  P.ui_schema()                — inject catalog schema into prompt
  S.to_ui(*keys, surface=)     — bridge state → A2UI data model
  S.from_ui(*keys, surface=)   — bridge A2UI data model → state
  M.a2ui_log(level=)           — log A2UI surface operations
  C.with_ui(surface_id=)       — include UI state in context

---

## Expression operators explained

    A >> B           # Sequential: A runs, then B. Returns a Pipeline.
    A | B            # Parallel: A and B run concurrently. Returns a FanOut.
    (A >> B) * 3     # Loop: repeat the pipeline 3 times. Returns a Loop.
    (A >> B) * until(pred, max=5)  # Conditional loop: repeat until pred(state) is true.
    A // B           # Fallback: try A first. If A fails (exception), try B.
    A @ Schema       # Structured output: constrain A's response to a Pydantic model.
                     # Equivalent to A.returns(Schema).

## Namespace composites attach via the same grammar

Every namespace composite attaches itself to a builder through one grammar:
``Composite >> Builder``. The left-hand composite dispatches to the builder's
corresponding setter, so a full agent configuration reads as one sentence::

    agent = (
        C.window(n=5)                                # context
        >> P.role("analyst") + P.task("crunch")      # instruction
        >> T.fn(search) | T.fn(fetch)                # tools
        >> G.pii() | G.length(max=500)               # guards
        >> M.retry(max_attempts=3) | M.log()         # middleware
        >> Agent("worker", "gemini-2.5-flash")
    )

  CTransform  >> Builder  →  Builder.context(transform)
  PTransform  >> Builder  →  Builder.instruct(transform)
  TComposite  >> Builder  →  Builder.tools(composite)
  GComposite  >> Builder  →  Builder.guard(composite)
  MComposite  >> Builder  →  Builder.middleware(composite)
  AComposite  >> Builder  →  Builder.artifacts(composite)

### Named-word aliases

Every single-letter namespace has a named-word alias that resolves to the
same class. Pick whichever reads better — they are ``is`` identical::

    from adk_fluent import S, C, P, T, G, M, A, E, R, H, UI
    from adk_fluent import (
        State, Context, Prompt, Tool, Guard,
        Middleware, Artifact, Eval, Reactive, Harness, Ui,
    )

    # equivalent
    C.window(n=5) >> agent
    Context.window(n=5) >> agent

## Expression primitives

Function-level primitives for use with expression operators:

  until(pred, max=10)          — loop condition for * operator
  tap(fn)                      — inline observation step (no LLM, zero cost). Reads
                                 state, runs side-effect, never mutates state.
  expect(pred, msg=)           — inline state assertion. Raises ValueError if pred(state)
                                 is false. Unlike tap(), this is a contract check, not a
                                 side-effect observer.
  map_over(key)                — map agent over list items in state[key]
  gate(predicate)              — conditional execution (skip if false)
  race(*agents)                — first-to-complete wins
  dispatch(name=, on_complete=) — launch background task (non-blocking)
  join()                       — wait for all background tasks

Routing:
  Route(key)                   — deterministic state-based routing
    .eq(value, agent)          — exact match
    .contains(sub, agent)      — substring match
    .gt(n, agent)              — greater than
    .lt(n, agent)              — less than
    .gte(n, agent) / .lte(n, agent) / .ne(value, agent)
    .when(pred, agent)         — custom predicate
    .otherwise(agent)          — default fallback

  Fallback(name)               — explicit fallback chain
    .attempt(agent)            — add fallback alternative

---

## Composition patterns

Higher-order constructors that accept builders and return builders:

  review_loop(worker, reviewer, quality_key=, target=, max_rounds=)
  map_reduce(mapper, reducer, items_key=, result_key=)
  cascade(agent1, agent2, ...)    — fallback chain of models
  fan_out_merge(*agents, merge_key=) — parallel + merge
  chain(*agents)                  — sequential pipeline
  conditional(pred, then_agent, else_agent=)
  supervised(worker, supervisor)

A2A patterns (remote agent-to-agent):

  a2a_cascade(*endpoints, names=, timeout=)   — fallback chain across remote agents
  a2a_fanout(*endpoints, names=, timeout=)    — parallel fan-out to remote agents
  a2a_delegate(coordinator, **remotes)        — coordinator with named remote specialists

---

## A2A (Agent-to-Agent) remote communication

Experimental support for the A2A protocol. Requires `pip install google-adk[a2a]`.

### RemoteAgent — consume a remote A2A agent

    from adk_fluent import RemoteAgent

    remote = (
        RemoteAgent("researcher", agent_card="http://researcher:8001/.well-known/agent.json")
        .describe("Remote research specialist")
        .timeout(30)
        .sends("query")           # serialize state keys into A2A message
        .receives("findings")     # deserialize A2A response back into state
        .persistent_context()     # maintain contextId across calls in same session
    )

RemoteAgent extends BuilderBase — all operators (>>, |, //, *) work:

    pipeline = Agent("writer") >> remote >> Agent("reviewer")
    fallback = remote // Agent("local-fallback", "gemini-2.5-flash")

### A2AServer — publish a local agent via A2A

    from adk_fluent import A2AServer

    server = (
        A2AServer(my_agent)
        .port(8001)
        .version("1.0.0")
        .provider("Acme Corp", "https://acme.com")
        .skill("research", "Academic Research",
               description="Deep research with citations",
               tags=["research", "citations"])
        .health_check()
        .graceful_shutdown(timeout=30)
    )

### A2A middleware (M namespace)

    M.a2a_retry(max_attempts=3, backoff=2.0)   — retry with exponential backoff
    M.a2a_circuit_breaker(threshold=5, reset_after=60)  — circuit breaker
    M.a2a_timeout(seconds=30)                  — per-agent timeout

### A2A tool composition (T namespace)

    T.a2a(agent_card_url, name=, description=, timeout=)  — wrap remote agent as tool

### Discovery

    RemoteAgent.discover("research-agent.agents.acme.com")  — DNS well-known discovery
    AgentRegistry("http://registry:9000").find(name="research")  — registry-based
    RemoteAgent("code", env="CODE_AGENT_URL")  — environment variable configuration

---

## Builder Inventory (133 builders)

### agent module (3 builders)

`Agent`, `BaseAgent`, `RemoteA2aAgent`

### config module (39 builders)

`A2aAgentExecutorConfig`, `AgentConfig`, `AgentRefConfig`, `AgentSimulatorConfig`, `AgentToolConfig`, `ArgumentConfig`, `AudioCacheConfig`, `BaseAgentConfig`, `BaseGoogleCredentialsConfig`, `BaseToolConfig`, `BigQueryCredentialsConfig`, `BigQueryLoggerConfig`, `BigQueryToolConfig`, `BigtableCredentialsConfig`, `CodeConfig`, `ContextCacheConfig`, `DataAgentCredentialsConfig`, `DataAgentToolConfig`, `EventsCompactionConfig`, `ExampleToolConfig`, `FeatureConfig`, `GetSessionConfig`, `InjectionConfig`, `LlmAgentConfig`, `LoopAgentConfig`, `McpToolsetConfig`, `ParallelAgentConfig`, `PubSubCredentialsConfig`, `PubSubToolConfig`, `ResumabilityConfig`, `RetryConfig`, `RunConfig`, `SequentialAgentConfig`, `SimplePromptOptimizerConfig`, `SpannerCredentialsConfig`, `ToolArgsConfig`, `ToolConfig`, `ToolSimulationConfig`, `ToolThreadPoolConfig`

### executor module (6 builders)

`A2aAgentExecutor`, `AgentEngineSandboxCodeExecutor`, `BaseCodeExecutor`, `BuiltInCodeExecutor`, `UnsafeLocalCodeExecutor`, `VertexAiCodeExecutor`

### planner module (3 builders)

`BasePlanner`, `BuiltInPlanner`, `PlanReActPlanner`

### plugin module (12 builders)

`AgentSimulatorPlugin`, `BasePlugin`, `BigQueryAgentAnalyticsPlugin`, `ContextFilterPlugin`, `DebugLoggingPlugin`, `GlobalInstructionPlugin`, `LoggingPlugin`, `MultimodalToolResultsPlugin`, `RecordingsPlugin`, `ReflectAndRetryToolPlugin`, `ReplayPlugin`, `SaveFilesAsArtifactsPlugin`

### runtime module (3 builders)

`App`, `InMemoryRunner`, `Runner`

### service module (15 builders)

`BaseArtifactService`, `BaseMemoryService`, `BaseSessionService`, `DatabaseSessionService`, `FileArtifactService`, `ForwardingArtifactService`, `GcsArtifactService`, `InMemoryArtifactService`, `InMemoryMemoryService`, `InMemorySessionService`, `PerAgentDatabaseSessionService`, `SqliteSessionService`, `VertexAiMemoryBankService`, `VertexAiRagMemoryService`, `VertexAiSessionService`

### tool module (49 builders)

`APIHubToolset`, `ActiveStreamingTool`, `AgentTool`, `ApplicationIntegrationToolset`, `BaseAuthenticatedTool`, `BaseRetrievalTool`, `BaseTool`, `BaseToolset`, `BigQueryToolset`, `BigtableToolset`, `CalendarToolset`, `ComputerUseTool`, `ComputerUseToolset`, `DataAgentToolset`, `DiscoveryEngineSearchTool`, `DocsToolset`, `EnterpriseWebSearchTool`, `ExampleTool`, `FunctionTool`, `GmailToolset`, `GoogleApiTool`, `GoogleApiToolset`, `GoogleMapsGroundingTool`, `GoogleSearchAgentTool`, `GoogleSearchTool`, `GoogleTool`, `IntegrationConnectorTool`, `LoadArtifactsTool`, `LoadMcpResourceTool`, `LoadMemoryTool`, `LoadSkillResourceTool`, `LoadSkillTool`, `LongRunningFunctionTool`, `McpTool`, `McpToolset`, `OpenAPIToolset`, `PreloadMemoryTool`, `PubSubToolset`, `RestApiTool`, `SetModelResponseTool`, `SheetsToolset`, `SkillToolset`, `SlidesToolset`, `SpannerToolset`, `ToolboxToolset`, `TransferToAgentTool`, `UrlContextTool`, `VertexAiSearchTool`, `YoutubeToolset`

### workflow module (3 builders)

`FanOut`, `Loop`, `Pipeline`

---

## Best practices

1. Use deterministic routing (Route) over LLM routing when the decision is rule-based
2. Use `.inject()` for infrastructure deps — never expose DB clients in tool schemas
3. Use S.transform() or plain functions for data transforms, not custom BaseAgent
4. Use C.none() to hide conversation history from background/utility agents
5. Use M.retry() middleware instead of retry logic inside tool functions
6. Use `.writes()` not deprecated `.output_key()` / `.outputs()`
7. Use `.returns()` not deprecated `.output_schema()`
8. Use `.context()` not deprecated `.history()` / `.include_history()`
9. Use `.delegate_to()` not deprecated `.delegate()`
10. Use `.guard()` not deprecated `.guardrail()`
11. Use `.loop_while()` not deprecated `.retry_if()`
12. Use `.prepend()` not deprecated `.inject_context()`
13. All operators are immutable — sub-expressions can be safely reused
14. Every `.build()` returns a real ADK object compatible with adk web/run/deploy
15. Use `.transfer_to()` for transfer-based delegation (LLM decides routing);
    use `.delegate_to()` for tool-based invocation (parent stays in control)
16. Use `.isolate()` on specialist agents by default — it is the most predictable pattern
17. Always set `.describe()` on sub-agents — the description helps the coordinator LLM
    pick the right specialist during transfer routing
18. `.ask()` / `.map()` are dual-mode — they block in sync code and return
    an awaitable coroutine inside a running event loop (Jupyter, FastAPI,
    pytest-asyncio). Write `result = agent.run.ask(...)` synchronously or
    `result = await agent.run.ask(...)` in async code. No separate
    `.ask_async()` / `.map_async()` surface.

---

## Development commands

    pip install adk-fluent                  # install
    uv run pytest tests/ -v --tb=short      # run tests
    uv run ruff check .                     # lint
    uv run ruff format .                    # format
    uv run sphinx-build -b html docs/ docs/_build/html  # build docs
