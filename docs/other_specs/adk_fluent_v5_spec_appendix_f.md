# SPEC v5 — Appendix F: Hard Questions

## A Functional Interrogation of What adk-fluent v5 Is Actually For

This document asks the questions a sharp beginner would ask, and the questions a skeptic would ask, and tries to answer both honestly. If a feature doesn't survive scrutiny, it says so.

______________________________________________________________________

## Question 0: What is the mission?

Before any feature discussion, the mission needs to be stated plainly enough that someone who's never heard of ADK can evaluate whether a given feature belongs.

**Mission:** adk-fluent provides better primitives for composing agent systems on Google ADK. It exists because ADK optimized for the single-agent story and left multi-agent composition to imperative wiring. adk-fluent fills that gap with a small set of operators (`>>`, `|`, `*`, `Route`, `S.*`, `until`) that make pipeline topology visible in the code's structure, and an intermediate representation (IR) that makes the topology inspectable, analyzable, and simulatable before any LLM call.

Everything in v5 must justify itself against that mission. If a feature doesn't make composition better or doesn't leverage the IR for something ADK can't do, it doesn't belong.

______________________________________________________________________

## Question 1: Why should I care about an IR if `.build()` already works?

This is the most important question in the entire project and the answer needs to be honest.

Right now, every adk-fluent example ends with `.build()`. That method calls ADK constructors directly — `LlmAgent(...)`, `SequentialAgent(...)`, `ParallelAgent(...)` — and hands you a native ADK agent. The IR (`.to_ir()`) exists in parallel but most users never touch it.

**So why does the IR exist?**

The IR exists because `.build()` is a one-way door. Once you have an `LlmAgent` object, you can run it — but you can't ask it questions. You can't ask "which agent reads a key that nobody writes?" You can't ask "what will this pipeline cost at 10,000 invocations per day?" You can't ask "does this pipeline have a streaming-incompatible edge?" You can't ask "draw me a diagram." You can't ask "replay yesterday's failure deterministically."

The IR is the structural representation that makes the pipeline queryable. It's what separates a "builder that makes agents" from a "system that understands agents."

**The honest tension:** Most users will never use `.to_ir()` directly. And that's fine — the progressive disclosure ladder starts at Level 0 where `.build()` works exactly as expected. But the features that make v5 actually worth building — cost estimation, contract checking, replay, evaluation targeting — all require the IR. If nobody uses the IR, half of v5 is dead code.

**Resolution: Make the IR invisible but present.** The right design is: `.build()` internally calls `.to_ir()` then compiles, so every build goes through the IR. Contract checking runs by default (see Question 3). Cost estimates are available without the user knowing about IR nodes. The IR is the implementation substrate, not a user-facing concept — unless you need it to be.

This means changing the build path from:

```
builder.build() → ADK constructor calls → native agent
```

to:

```
builder.build() → .to_ir() → check_contracts() → backend.compile() → native agent
```

The user sees the same `.build()`. But now every pipeline is checked before it runs. That's the real value of the IR — not as something you "use," but as something that's always working underneath.

______________________________________________________________________

## Question 2: If the codegen pipeline auto-generates everything from ADK, isn't adk-fluent just a thinner wrapper that gets stale?

The scanner reads ADK's Pydantic models, produces `manifest.json`, and the generator produces fluent builders. When ADK adds a new field to `LlmAgent`, the scanner picks it up automatically. When ADK removes one, it disappears. This is the Tide Principle at work.

**But the question cuts deeper:** If adk-fluent is a 1:1 mapping of ADK's API surface, why not just use ADK directly? What does the wrapper layer actually buy?

**Answer: The generated builders are the uninteresting part.** `Agent("x").instruct("...")` vs `LlmAgent(name="x", instruction="...")` saves a few characters but doesn't change your life. The real value lives in the *hand-written* parts — the operator overloading (`_base.py`), the state transforms (`_transforms.py`), the routing (`_routing.py`), the IR nodes (`_ir.py`), the backend compilation (`backends/adk.py`), and all the v5 modules. The generated builders are the paved parking lot. The hand-written composition layer is the building.

The codegen pipeline's real purpose isn't "make ADK API fluent." It's "keep the parking lot maintained automatically so humans spend zero time on it and 100% of their time on the building."

**The risk:** If the generated surface becomes the perceived product (because it's what `__init__.py` exports and what autocomplete shows), people will correctly conclude that it's not worth a dependency. The perception must be: "adk-fluent gives me `>>`, `|`, `Route`, `S.*`, typed state, cost estimation, and contract checking. Oh, and the ADK API is fluent too, as a bonus."

______________________________________________________________________

## Question 3: Contract checking is opt-in. Why not make it the default?

Today, you call `check_contracts()` explicitly on an IR node. This means nobody calls it in production. Contracts that nobody runs are contracts that don't exist.

**How to make it the default:**

Change `.build()` to call `check_contracts()` before compiling. If the check finds errors, raise an exception. If it finds warnings, log them. The user never asked for checking — it just happens. This is how Python's type system works (via mypy/pyright), how Rust's borrow checker works, how database schemas work. You don't opt into integrity; integrity is the default.

```python
# Current: checking is opt-in (almost nobody does it)
ir = pipeline.to_ir()
issues = check_contracts(ir)  # User must know this exists
if issues:
    ...
agent = ADKBackend().compile(ir)

# Proposed: checking is built into .build()
agent = pipeline.build()  # Internally: to_ir() → check_contracts() → compile()
# If check_contracts finds ReadBeforeWrite or TypeMismatch → raises ContractError
# If check_contracts finds DeadState (warning) → logs a warning
```

**The escape hatch:** `pipeline.build(check=False)` bypasses checking for prototyping. But the default is safe.

**The deeper question: what do we check?** With untyped agents (no `StateSchema`), we can only check `writes_keys`/`reads_keys` — and only if the user declared `.writes()` and `.reads()`. Without declarations, there's nothing to check.

This is where `StateSchema` becomes load-bearing. If state schemas are optional AND contract checking is default, then most users get... no checking. The schema-adoption incentive has to be strong: IDE autocomplete on state fields, type errors at write time, scoped key generation. The checking is the outcome; the autocomplete is the bait.

**Implementation detail:** The check runs in \<100ms for a 100-node graph (it's a topological sort + set intersection, not LLM inference). There is no reason not to run it on every build.

______________________________________________________________________

## Question 4: What are the actual programming primitives, and why do they matter?

ADK provides three composition agents: `SequentialAgent` (do A then B), `ParallelAgent` (do A and B simultaneously), `LoopAgent` (do A repeatedly). For anything else — conditional branching, early exit, state transformation, fan-in aggregation — you write a `BaseAgent` subclass with `_run_async_impl`.

This is like having `for`, `concurrent`, and `while` but no `if`, no `map`, no `filter`, no early `return`. You can build anything with the three primitives — Turing completeness isn't the issue. The issue is that every team reinvents the missing primitives, differently, untestably, invisibly to tooling.

**adk-fluent's primitive set:**

| Primitive        | Syntax                                            | ADK Equivalent                                                 | What it eliminates                                        |
| ---------------- | ------------------------------------------------- | -------------------------------------------------------------- | --------------------------------------------------------- |
| Sequence         | `a >> b`                                          | `SequentialAgent(sub_agents=[a, b])`                           | Nested constructor boilerplate                            |
| Parallel         | `a \| b`                                          | `ParallelAgent(sub_agents=[a, b])`                             | Same                                                      |
| Loop             | `a * 5`                                           | `LoopAgent(sub_agents=[a], max_iterations=5)`                  | Same                                                      |
| Conditional exit | `(a >> b).loop_until(pred)`                       | `LoopAgent` + custom `exit_loop` tool + instruction to call it | LLM-dependent exit → deterministic predicate              |
| If/branch        | `Route("key").eq("a", x).eq("b", y).otherwise(z)` | Custom `BaseAgent` subclass with `_run_async_impl`             | Ad-hoc routing → declarative, zero-LLM-cost               |
| Transform        | `>> S.rename(a="b")`                              | Custom `BaseAgent` or `before_agent` callback                  | Full agent for a dict operation → zero-cost function      |
| For-each         | `map_over("items", Agent("process"))`             | Custom `BaseAgent` that iterates `ctx.session.state["items"]`  | Manual iteration → IR-visible parallelizable loop         |
| Fallback         | `a // b`                                          | Custom try/except in `_run_async_impl`                         | Manual error handling → declarative fallback chain        |
| Race             | `race(a, b)`                                      | Custom parallel + cancellation                                 | Manual cancellation → first-to-complete primitive         |
| Gate             | `gate(pred, a)`                                   | `if pred: run(a)` in custom agent                              | Manual conditional → IR-visible predicated execution      |
| Tap              | `a @ logger_fn`                                   | `after_agent_callback` on next agent                           | Callback coupled to wrong agent → independent observation |

**Why this matters beyond convenience:** Every hand-written `BaseAgent` subclass is a black box to the IR. It has no `writes_keys`, no `reads_keys`, no cost model, no streaming semantics, no visualization shape. The contract checker can't look inside it. The cost estimator can't price it. The Mermaid renderer draws it as a generic rectangle.

When the same logic is expressed via `Route`, `S.rename`, or `gate`, the IR knows the semantics. The contract checker knows what keys a `Route` reads. The cost estimator knows `S.rename` costs \$0. The Mermaid renderer draws `Route` as a diamond and transforms as arrows.

**The primitives aren't about saving keystrokes. They're about making composition semantics visible to machines.**

______________________________________________________________________

## Question 5: Show me the full lifecycle. How does a fluent pipeline become a running agent?

ADK's lifecycle has four objects: `Agent` (the logic), `Runner` (the execution engine), `SessionService` (state persistence), and `App` (the top-level container). Here's what the full lifecycle looks like in both:

**ADK — Full lifecycle from agent to running conversation:**

```python
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

# 1. Define agents
writer = LlmAgent(name="writer", model="gemini-2.5-flash",
                   instruction="Write a draft.", output_key="draft")
reviewer = LlmAgent(name="reviewer", model="gemini-2.5-flash",
                     instruction="Review: {draft}")

pipeline = SequentialAgent(name="write_review", sub_agents=[writer, reviewer])

# 2. Set up infrastructure
session_service = InMemorySessionService()
runner = Runner(agent=pipeline, app_name="my_app", session_service=session_service)

# 3. Create session
session = await session_service.create_session(
    app_name="my_app", user_id="user1", session_id="session1"
)

# 4. Run
content = Content(role="user", parts=[Part(text="Write about AI agents")])
async for event in runner.run_async(
    user_id="user1", session_id=session.id, new_message=content
):
    if event.content and event.content.parts:
        for part in event.content.parts:
            if part.text:
                print(part.text)
```

**adk-fluent — Same lifecycle, same ADK objects underneath:**

```python
from adk_fluent import Agent

# 1. Define pipeline (>> produces SequentialAgent at build time)
pipeline = (
    Agent("writer").model("gemini-2.5-flash").instruct("Write a draft.").outputs("draft")
    >> Agent("reviewer").model("gemini-2.5-flash").instruct("Review: {draft}")
)

# 2. One-shot (Runner + Session created internally, identical to above)
response = await pipeline.ask_async("Write about AI agents")

# 3. Or: multi-turn session (explicit Runner, explicit Session)
async with create_session(pipeline) as chat:
    r1 = await chat.send("Write about AI agents")
    r2 = await chat.send("Now make it shorter")

# 4. Or: for adk web / adk run (just export root_agent)
root_agent = pipeline.build()
```

**What `pipeline.ask_async()` does internally** (from `_helpers.py`):

1. `builder.build()` → calls ADK constructors → native `SequentialAgent`
1. Creates `InMemoryRunner(agent=agent, app_name=...)` — ADK's runner
1. Creates session via `runner.session_service.create_session(...)`
1. Calls `runner.run_async(...)` — ADK's event loop
1. Collects text from events, returns it

There's no custom runtime. There's no custom event loop. There's no custom session management. It's ADK's `Runner`, ADK's `InMemorySessionService`, ADK's `run_async`. The fluent layer handles the plumbing so the user doesn't write 15 lines of setup for a one-shot call.

**What `pipeline.build()` does** — produces a native ADK agent tree. `adk web my_agent` works because `root_agent` is a standard `SequentialAgent`. The web UI sees the same agent hierarchy, the same trace spans, the same event stream. The fluent layer is gone at runtime.

**What about `App`?** adk-fluent has a generated `App` builder:

```python
from adk_fluent import App

app = App("billing_support", root_agent=pipeline.build())
    .plugins([my_plugin])
    .events_compaction_config(...)
    .resumability_config(...)
    .build()

runner = InMemoryRunner(app=app)
```

It mirrors ADK's `App` exactly — because it's generated from ADK's `App` class via the scanner. No new concepts. Just fluent syntax over the same object.

**Honest admission:** The `App`/`Runner` builders don't add much. `App(name="x", root_agent=agent, plugins=[...])` is already clean in ADK. The fluent wrapper saves maybe 2 lines. The real value is upstream — in how you build the `root_agent` that goes into the `App`.

______________________________________________________________________

## Question 6: What is middleware actually for? Isn't it just callbacks with extra steps?

ADK has callbacks (`before_agent`, `after_model`, `before_tool`, etc.) on individual agents. adk-fluent has a middleware protocol with the same 13 hooks. So: why middleware?

**Callbacks are per-agent. Middleware is per-pipeline.**

When you write `before_model_callback` on an `LlmAgent`, it fires for that one agent. If you have 8 agents in a pipeline and want to log every LLM call, you add the callback to all 8 agents. If you add a 9th agent, you must remember to add the callback. If you forget, that agent is invisible.

Middleware wraps the entire pipeline. Add `RetryMiddleware(max_attempts=3)` once, and every agent in the pipeline gets retry behavior. Add `OTelEnrichmentMiddleware()` once, and every span gets enriched. Remove an agent, add an agent — the middleware still applies.

```python
# ADK callbacks: per-agent, must be added to every agent individually
def log_model_call(callback_context, llm_request):
    print(f"Calling model: {llm_request.model}")
    return None

writer = LlmAgent(name="writer", ..., before_model_callback=log_model_call)
reviewer = LlmAgent(name="reviewer", ..., before_model_call=log_model_call)
# Forgot the refactorer? It's invisible now.

# adk-fluent middleware: per-pipeline, applied once
from adk_fluent.middleware import StructuredLogMiddleware

pipeline = (
    Agent("writer").instruct("Write.")
    >> Agent("reviewer").instruct("Review.")
    >> Agent("refactorer").instruct("Refactor.")
).with_middleware(StructuredLogMiddleware())
# All three agents are logged. Add a fourth? Still logged.
```

**How it compiles:** `_MiddlewarePlugin` adapter converts a middleware stack into a single ADK `BasePlugin`. ADK's plugin system is pipeline-wide — it receives lifecycle hooks for every agent in the tree. The middleware protocol maps 1:1 to the plugin protocol. So middleware IS the ADK plugin system, just with a stack model (multiple middleware compose) instead of a list model.

**What middleware should do (v5 list, interrogated):**

| Middleware                  | Purpose                                          | Is this a real need?                                                                                                                        |
| --------------------------- | ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `RetryMiddleware`           | Retry failed LLM calls with backoff              | **Yes.** LLM APIs fail transiently. Every production system needs this.                                                                     |
| `OTelEnrichmentMiddleware`  | Annotate ADK's OTel spans with pipeline metadata | **Yes.** Without it, traces show ADK internals but not pipeline context.                                                                    |
| `CostAttributionMiddleware` | Emit cost OTel metrics per agent                 | **Yes, if you care about cost.** No ADK equivalent.                                                                                         |
| `TokenBudgetMiddleware`     | Enforce per-invocation token limits              | **Maybe.** ADK's `generate_content_config` has `max_output_tokens`. This adds *input* budget tracking — useful for cost control, but niche. |
| `CacheMiddleware`           | Cache LLM responses for identical inputs         | **Maybe.** ADK has `ContextCacheConfig` for context caching. Semantic response caching is different — but complex to get right.             |
| `RateLimiterMiddleware`     | Throttle LLM calls per time window               | **Maybe.** Most teams handle this at the API key / quota level, not middleware.                                                             |
| `CircuitBreakerMiddleware`  | Stop calling a model that's consistently failing | **Yes.** Standard resilience pattern. Retries without circuit breaking → retry storms.                                                      |
| `ToolApprovalMiddleware`    | Require human approval before tool execution     | **Yes.** ADK has `require_confirmation` on tools. This promotes it to pipeline-level policy: "all tools in this pipeline require approval." |
| `PiiFilterMiddleware`       | Scrub PII from LLM inputs/outputs                | **Yes for regulated industries.** But the implementation is non-trivial — needs entity detection, not just regex.                           |
| `RecorderMiddleware`        | Capture events for replay                        | **Yes, for debugging.** The replay story (Question 8 below) depends on this.                                                                |

**Honest assessment:** retry, OTel enrichment, cost attribution, circuit breaker, and tool approval are clear wins. Cache, rate limiter, and PII filter are "nice to have" that most teams will build differently. The middleware *framework* matters more than the specific built-in set — teams need the ability to write their own middleware and compose it into a stack.

______________________________________________________________________

## Question 7: The "for-each" problem — why do better primitives enable alchemy?

Consider this real pattern: you have a list of customer complaints. You want to classify each one, route it, and aggregate the results. In ADK:

```python
# ADK: Process a list of items
# There is no built-in "for each item in state, run this agent"
# You must write a custom BaseAgent

class ForEachAgent(BaseAgent):
    async def _run_async_impl(self, ctx):
        items = ctx.session.state.get("complaints", [])
        results = []
        for item in items:
            ctx.session.state["current_item"] = item
            async for event in self.sub_agents[0].run_async(ctx):
                yield event
            results.append(ctx.session.state.get("classification"))
        ctx.session.state["all_classifications"] = results
```

This is 12 lines of agent plumbing for what is conceptually `map(classify, complaints)`. And it's a black box — the IR doesn't know it iterates, the contract checker can't verify the inner agent's reads/writes, the cost estimator doesn't know the cost multiplies by `len(complaints)`.

```python
# adk-fluent: map_over is an IR-visible primitive
from adk_fluent import Agent, map_over

pipeline = (
    map_over("complaints",
        Agent("classifier").instruct("Classify: {current_item}").outputs("classification"),
        output_key="all_classifications"
    )
    >> Agent("reporter").instruct("Summarize: {all_classifications}")
)
```

`map_over` produces a `MapOverNode` in the IR. The cost estimator knows to multiply the inner agent's cost by the expected item count. The contract checker verifies the inner agent reads `current_item` and writes `classification`. The Mermaid renderer draws it as a loop with the inner agent visible.

**The alchemy:** When primitives are composable and IR-visible, you get emergent combinations:

```python
# Research each topic in parallel, gate on quality, loop until all pass
pipeline = (
    map_over("topics",
        Agent("researcher").instruct("Research: {current_item}").outputs("finding")
        >> gate(lambda s: float(s.get("quality", 0)) > 0.7,
                Agent("enhancer").instruct("Improve: {finding}"))
    )
    >> S.merge("findings", into="report")
    >> (Agent("writer").instruct("Write: {report}").outputs("draft")
        >> Agent("critic").instruct("Critique: {draft}").outputs("quality"))
        .loop_until(lambda s: s.get("quality") == "approved", max_iterations=3)
)
```

Each primitive (`map_over`, `gate`, `>>`, `loop_until`, `S.merge`) is individually simple. Their composition creates sophisticated behavior: parallel fan-out over topics, conditional enhancement per item, aggregation, iterative refinement with deterministic exit. Every node is IR-visible, analyzable, costable.

Writing this in ADK requires 3-4 custom `BaseAgent` subclasses, each with async generator plumbing, manual state management, and manual escalation. The primitives enable alchemy because they're *composable without custom code*.

______________________________________________________________________

## Question 8: Isn't `estimate_cost()` just... multiplication? Why dress it up?

If you know the tokens per call and the price per token, cost estimation is `tokens × price × calls`. Why does this need an IR?

**Because multiplication doesn't handle branching, parallelism, loops, or routing.**

A pipeline with `Route("intent").eq("billing", billing_agent).eq("tech", tech_agent)` doesn't call both agents — it calls one based on state. The cost depends on *which branch is taken*. At estimation time, you don't know — but you can supply branch probabilities: "60% billing, 30% tech, 10% general."

A pipeline with a loop runs the inner agents N times. The N depends on when the exit condition triggers. At estimation time, you estimate: "average 2.3 iterations based on historical data."

A pipeline with `map_over("items", agent)` multiplies by the item count, which varies per invocation. The estimate uses average item counts.

A pipeline with `S.rename(...)` or `Route(...)` costs \$0 — no LLM call. The IR knows this because `TransformNode` and `RouteNode` are distinct from `AgentNode`.

**The IR makes cost estimation structural, not arithmetic.** Walking the IR produces a cost equation that accounts for the pipeline's actual topology. Flat multiplication doesn't.

______________________________________________________________________

## Question 9: Does the fluent API make ADK harder to debug?

Honest answer: **it can, if you're not careful.**

When something goes wrong in ADK, you look at the agent tree in the web UI, click on an event, and see the trace. The agent names are the names you gave them. The structure matches your code because your code IS the structure.

With adk-fluent, the structure is generated. `a >> b` produces a `SequentialAgent(name="a_then_b")`. The auto-generated name may not match what you expected. The web UI shows `a_then_b` as the parent, which is correct but surprising if you didn't think about the intermediate agent.

**Mitigations that exist:**

- You can name pipelines explicitly: `Pipeline("review_cycle").step(a).step(b)`
- Agent names propagate: `a` and `b` keep their names as sub-agents
- `ir_to_mermaid()` shows you the full tree before you run
- OTel spans carry both ADK names and `adk_fluent.pipeline` attributes (with v5 enrichment)

**Mitigation that should exist but doesn't:**

- A `pipeline.explain()` method that prints a human-readable description of the compiled agent tree, including all auto-generated names and the ADK types they correspond to
- Better auto-generated names: `"writer_then_reviewer"` instead of `"writer_then_reviewer_then_refactorer_then_..."` for long pipelines

**The rule:** If a fluent expression makes debugging harder than the equivalent ADK code, the fluent expression has failed. Brevity that costs debuggability is a bad trade.

______________________________________________________________________

## Question 10: What is adk-fluent NOT?

This is as important as what it is.

**adk-fluent is NOT a framework.** It doesn't own the runtime. It doesn't own the event loop. It doesn't own the session. It doesn't own the model layer. It produces ADK objects that ADK runs. If adk-fluent disappeared, your agents would still work — you'd just have more boilerplate.

**adk-fluent is NOT an abstraction over multiple LLM providers.** `Agent("x").model("gemini-2.5-flash")` passes through to ADK's model resolution. ADK itself supports multiple models (Gemini, Claude, Ollama, vLLM, LiteLLM). adk-fluent doesn't add or restrict model choice.

**adk-fluent is NOT an alternative to ADK.** It sits on top. Every feature compiles to ADK constructs. The relationship is deliberate: ADK handles the hard runtime problems (sessions, memory, event loops, deployment, streaming, A2A protocol), and adk-fluent handles the composition problem (topology, contracts, cost, evaluation authoring).

**adk-fluent is NOT necessary for simple agents.** A single `LlmAgent` with tools is perfectly good ADK code. The composition layer pays for itself starting at ~3 agents, and pays handsomely at 5+.

**adk-fluent is NOT a no-code/low-code tool.** You write Python. The operators are Python operators. The transforms are Python lambdas. The routing predicates are Python functions. The value is in the *primitives*, not in removing code — it's in making the *right* code shorter and the *wrong* code impossible.

______________________________________________________________________

## Question 11: What's the honest progressive disclosure curve?

| You need            | You use                                        | You learn                        | Time to value |
| ------------------- | ---------------------------------------------- | -------------------------------- | ------------- |
| A single agent      | `Agent("x").instruct("...").build()`           | One class, three methods         | 5 minutes     |
| A pipeline          | `a >> b >> c`                                  | `>>` operator                    | 10 minutes    |
| Parallel + merge    | `(a \| b) >> S.merge(...)`                     | `\|` operator, `S` transforms    | 20 minutes    |
| Conditional routing | `>> Route("key").eq(...)`                      | `Route` class                    | 20 minutes    |
| Loop with exit      | `(a >> b).loop_until(pred)`                    | `until` primitive                | 15 minutes    |
| Quick test          | `pipeline.ask("test prompt")`                  | `.ask()` method                  | 5 minutes     |
| Multi-turn chat     | `async with create_session(pipeline) as chat:` | `create_session` context manager | 10 minutes    |
| Deploy to `adk web` | `root_agent = pipeline.build()`                | Nothing new — it's ADK           | 0 minutes     |
| Typed state         | `class MyState(StateSchema):`                  | `StateSchema`, scope annotations | 30 minutes    |
| Cost estimation     | `estimate_cost(pipeline.to_ir(), assumptions)` | `.to_ir()`, `TrafficAssumptions` | 20 minutes    |
| Eval suite          | `FluentEvalSuite(pipeline=..., cases=[...])`   | `FluentCase`, `PrebuiltMetrics`  | 30 minutes    |
| Custom middleware   | `class MyMiddleware:` (13-hook protocol)       | Middleware protocol              | 30 minutes    |

**The break-even point:** If you're building a single agent with tools, use ADK directly. If you're composing 3+ agents with state passing, routing, or loops, adk-fluent starts paying for itself. If you need cost estimation, contract checking, or eval authoring, adk-fluent has no ADK equivalent.

______________________________________________________________________

## Question 12: Where are the real contradictions?

Let's not shy away from these.

**Contradiction 1: "Fluent" vs "IR-centric."** The marketing says "fluent builder API" — easy, friendly, beginner-approachable. The technical core is an intermediate representation with graph analysis. These appeal to different audiences. The resolution is progressive disclosure (Level 0 is fluent, Level 3+ is IR), but the project needs to be honest that the deeper value requires understanding the IR's existence.

**Contradiction 2: "100% ADK compatible" vs "better primitives."** Every fluent pipeline produces ADK agents. But `Route`, `gate`, `map_over`, `S.*` create custom `BaseAgent` subclasses that ADK's tooling doesn't special-case. The web UI shows a `_RouteAgent` as a generic agent, not a diamond-shaped router. ADK's introspection sees sub-agents but not the routing predicates. The fluent layer is fully compatible at the runtime level but partially opaque to ADK's development tooling.

**Contradiction 3: "Codegen keeps up with ADK" vs "hand-written IR is fragile."** The generated builders auto-track ADK releases. The hand-written IR (`_ir.py`), the backend compiler (`backends/adk.py`), the state transforms, the routing — these don't auto-update. When ADK changes its `BaseAgent` internals or its event model, the hand-written layer may break. The codegen pipeline solves the easy maintenance problem; the hard maintenance problem remains.

**Contradiction 4: "Typed state prevents bugs" vs "schema adoption is optional."** If StateSchema is optional, untyped agents remain the common case, and contract checking catches nothing. The feature's value is proportional to adoption, but adoption requires effort. The resolution — making IDE autocomplete the incentive, not checking — is plausible but unproven.

**Contradiction 5: "Zero-cost transforms" vs "every >> creates a SequentialAgent."** `S.rename(a="b")` is a zero-cost function, but wrapping it in `>>` creates a `_FnStep` agent inside a `SequentialAgent`. At the ADK runtime level, this means an additional agent invocation with context creation, event emission, and callback lifecycle — for a dict key rename. The overhead is small but nonzero, and it's an artifact of expressing everything as agent composition. A native ADK callback on the next agent would be truly zero-cost at runtime, at the expense of discoverability and composability.

______________________________________________________________________

## Question 13: What would failure look like?

If in a year adk-fluent hasn't succeeded, the symptoms would be:

1. **Users build single agents with the fluent builders but never use `>>`.** They got a thinner ADK wrapper, not a composition system. The builders are the least valuable part.

1. **Nobody adopts `StateSchema`.** Typed state remains aspirational. Contract checking has nothing to check. The IR analysis story collapses.

1. **The IR path is unused.** Everyone calls `.build()` directly, no one calls `.to_ir()`, and the cost estimator, contract checker, and eval harness have zero users. The hand-written layer is dead weight.

1. **ADK changes its internals and the hand-written layer breaks.** A major ADK release changes the `BaseAgent._run_async_impl` signature, the `Event` structure, or the plugin protocol. The generated builders auto-adapt; the hand-written IR, backend, and middleware break and require weeks of repair.

1. **The fluent syntax becomes a debugging liability.** Users can't figure out what `(a >> b | c) * until(pred)` compiled to, the auto-generated names are confusing, and the web UI shows an alien agent tree.

**Prevention:** Make the IR invisible (Question 1). Make checking default (Question 3). Make `StateSchema` feel like Pydantic — a natural progression, not an imposition. Invest in `.explain()` and debuggability. Test against ADK's main branch weekly.

______________________________________________________________________

## The Bottom Line

adk-fluent v5 is worth building if:

- The composition operators (`>>`, `|`, `*`, `Route`, `S.*`, `until`, `map_over`, `gate`) become the standard way to assemble multi-agent ADK pipelines — because they make topology visible and primitives composable.
- The IR becomes the invisible substrate that powers default contract checking, cost estimation, and eval targeting — without users needing to know it exists.
- `StateSchema` achieves Pydantic-like adoption through IDE autocomplete and type safety, pulling contract checking into relevance as a side effect.
- The hand-written layer stays maintainable against ADK's release cadence through aggressive integration testing.

It's not worth building if it becomes a thin wrapper library where the composition features are used by 5% of users and the rest just wanted `.instruct()` instead of `instruction=`.

The mission — better primitives for composing agent systems — is sound. The risk is building too much before the primitives achieve adoption. Start with what's undeniably valuable (operators, transforms, routing, default checking), prove adoption, then layer cost, eval, and replay on top of a foundation people are already using.
