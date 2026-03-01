# adk-fluent — LLM Context

> Auto-generated from manifest.json. Do not edit manually.
> Docs: https://vamsiramakrishnan.github.io/adk-fluent/
> PyPI: https://pypi.org/project/adk-fluent/
> Repo: https://github.com/vamsiramakrishnan/adk-fluent

adk-fluent is a fluent builder API for Google's Agent Development Kit (ADK).
It reduces agent creation from 22+ lines to 1-3 lines while producing
identical native ADK objects. Every `.build()` returns a real ADK object —
fully compatible with `adk web`, `adk run`, and `adk deploy`.
## Install

    pip install adk-fluent
## Imports

Always import from the top-level package:

    from adk_fluent import Agent, Pipeline, FanOut, Loop
    from adk_fluent import S, C, P, A, M, T

Never import from internal modules like `adk_fluent._base` or `adk_fluent.agent`.
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
## Agent builder methods

Core configuration:
  .model(str)                  — set LLM model
  .instruct(str | PTransform)  — set instruction/system prompt
  .describe(str)               — set agent description
  .static(str)                 — set static instruction

Data flow:
  .writes(key)                 — store response in state[key]
  .reads(*keys)                — inject state keys into context
  .returns(Schema)             — constrain output to Pydantic model
  .accepts(Schema)             — define input schema for AgentTool usage
  .context(C.xxx())            — set context engineering spec

Tools:
  .tool(fn)                    — add a single tool function
  .tools(list | TComposite)    — set multiple tools
  .agent_tool(agent)           — wrap another agent as a callable tool

Callbacks:
  .before_agent(fn)            — run before agent executes
  .after_agent(fn)             — run after agent executes
  .before_model(fn)            — run before LLM call
  .after_model(fn)             — run after LLM call
  .before_tool(fn)             — run before tool call
  .after_tool(fn)              — run after tool call
  .guard(fn)                   — attach as both before_model and after_model

Execution:
  .build()                     — produce native ADK LlmAgent
  .ask(prompt)                 — one-shot sync execution
  .stream(prompt)              — async streaming iterator
  .session()                   — create interactive ChatSession
  .test(prompt, contains=)     — inline smoke test
  .mock(responses)             — replace LLM with canned responses

Introspection:
  .explain()                   — print builder state
  .validate()                  — early error detection
  .clone(name)                 — deep copy with new name
  .with_(**overrides)          — immutable variant
  .to_ir()                     — convert to IR tree
  .to_mermaid()                — generate Mermaid diagram
## Namespace modules (S, C, P, A, M, T)

### S — State transforms

Used with `>>` operator. Compose with `>>` (chain) or `+` (combine).

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

### C — Context engineering

Used with `.context()`. Compose with `+` (union) or `|` (pipe).

  C.none()                     — suppress all history
  C.user_only()                — only user messages
  C.window(n=5)                — last N turn-pairs
  C.from_state(*keys)          — inject state keys as context
  C.from_agents(*names)        — user + named agent outputs
  C.exclude_agents(*names)     — exclude named agents
  C.template(text)             — template with {key} placeholders
  C.truncate(max_turns=)       — hard limit
  C.budget(max_tokens=)        — token budget constraint
  C.summarize(scope=)          — LLM-powered summarization
  C.relevant(query_key=)       — semantic relevance filtering
  C.rolling(n=)                — rolling window with compaction

### P — Prompt composition

Used with `.instruct()`. Compose with `+` (union) or `|` (pipe).
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

### A — Artifacts

Used with `.artifacts()` or `>>`. Compose with `>>` (chain).

  A.publish(filename, from_key=) — state → artifact
  A.snapshot(filename, into_key=) — artifact → state
  A.save(filename, content=)    — content → artifact
  A.load(filename)              — artifact → pipeline

### M — Middleware

Used with `.middleware()`. Compose with `|` (chain).

  M.retry(max_attempts=)       — retry with exponential backoff
  M.log()                      — structured event logging
  M.cost()                     — token usage tracking
  M.latency()                  — per-agent latency tracking
  M.scope(agents, mw)          — restrict middleware to agents
  M.when(condition, mw)        — conditional middleware

### T — Tool composition

Used with `.tools()`. Compose with `|` (chain).

  T.fn(callable)               — wrap callable as FunctionTool
  T.agent(agent)               — wrap agent as AgentTool
  T.google_search()            — built-in Google Search
  T.search(registry)           — BM25-indexed dynamic loading
## Composition patterns

Higher-order constructors that accept builders and return builders:

  review_loop(worker, reviewer, quality_key=, target=, max_rounds=)
  map_reduce(mapper, reducer, items_key=, result_key=)
  cascade(agent1, agent2, ...)    — fallback chain of models
  fan_out_merge(*agents, merge_key=) — parallel + merge
  chain(*agents)                  — sequential pipeline
  conditional(pred, then_agent, else_agent=)
  supervised(worker, supervisor)
## Builder inventory

132 builders across 9 modules.

### agent module (2 builders)

BaseAgent, Agent

### config module (38 builders)

AgentConfig, BaseAgentConfig, AgentRefConfig, ArgumentConfig, CodeConfig, ContextCacheConfig, LlmAgentConfig, LoopAgentConfig, ParallelAgentConfig, RunConfig, ToolThreadPoolConfig, SequentialAgentConfig, EventsCompactionConfig, ResumabilityConfig, FeatureConfig, AudioCacheConfig, SimplePromptOptimizerConfig, BigQueryLoggerConfig, RetryConfig, GetSessionConfig, BaseGoogleCredentialsConfig, AgentSimulatorConfig, InjectionConfig, ToolSimulationConfig, AgentToolConfig, BigQueryCredentialsConfig, BigQueryToolConfig, BigtableCredentialsConfig, DataAgentToolConfig, DataAgentCredentialsConfig, ExampleToolConfig, McpToolsetConfig, PubSubToolConfig, PubSubCredentialsConfig, SpannerCredentialsConfig, BaseToolConfig, ToolArgsConfig, ToolConfig

### executor module (5 builders)

AgentEngineSandboxCodeExecutor, BaseCodeExecutor, BuiltInCodeExecutor, UnsafeLocalCodeExecutor, VertexAiCodeExecutor

### planner module (3 builders)

BasePlanner, BuiltInPlanner, PlanReActPlanner

### plugin module (12 builders)

RecordingsPlugin, ReplayPlugin, BasePlugin, BigQueryAgentAnalyticsPlugin, ContextFilterPlugin, DebugLoggingPlugin, GlobalInstructionPlugin, LoggingPlugin, MultimodalToolResultsPlugin, ReflectAndRetryToolPlugin, SaveFilesAsArtifactsPlugin, AgentSimulatorPlugin

### runtime module (3 builders)

App, InMemoryRunner, Runner

### service module (15 builders)

BaseArtifactService, FileArtifactService, GcsArtifactService, InMemoryArtifactService, PerAgentDatabaseSessionService, BaseMemoryService, InMemoryMemoryService, VertexAiMemoryBankService, VertexAiRagMemoryService, BaseSessionService, DatabaseSessionService, InMemorySessionService, SqliteSessionService, VertexAiSessionService, ForwardingArtifactService

### tool module (51 builders)

ActiveStreamingTool, AgentTool, APIHubToolset, ApplicationIntegrationToolset, IntegrationConnectorTool, BaseAuthenticatedTool, BaseTool, BaseToolset, BigQueryToolset, BigtableToolset, ComputerUseTool, ComputerUseToolset, DataAgentToolset, DiscoveryEngineSearchTool, EnterpriseWebSearchTool, ExampleTool, FunctionTool, GoogleApiTool, GoogleApiToolset, CalendarToolset, DocsToolset, GmailToolset, SheetsToolset, SlidesToolset, YoutubeToolset, GoogleMapsGroundingTool, GoogleSearchAgentTool, GoogleSearchTool, GoogleTool, LoadArtifactsTool, LoadMcpResourceTool, LoadMemoryTool, LongRunningFunctionTool, MCPTool, McpTool, MCPToolset, McpToolset, OpenAPIToolset, RestApiTool, PreloadMemoryTool, PubSubToolset, BaseRetrievalTool, SetModelResponseTool, LoadSkillResourceTool, LoadSkillTool, SkillToolset, SpannerToolset, ToolboxToolset, TransferToAgentTool, UrlContextTool, VertexAiSearchTool

### workflow module (3 builders)

Loop, FanOut, Pipeline
## Best practices

1. Use deterministic routing (Route) over LLM routing when the decision is rule-based
2. Use `.inject()` for infrastructure deps — never expose DB clients in tool schemas
3. Use S.transform() or plain functions for data transforms, not custom BaseAgent
4. Use C.none() to hide conversation history from background/utility agents
5. Use M.retry() middleware instead of retry logic inside tool functions
6. Use `.writes()` not deprecated `.save_as()` / `.output_key()`
7. Use `.returns()` not deprecated `.output_schema()`
8. Use `.context()` not deprecated `.history()` / `.include_history()`
9. All operators are immutable — sub-expressions can be safely reused
10. Every `.build()` returns a real ADK object compatible with adk web/run/deploy
## Development commands

    pip install adk-fluent                  # install
    uv run pytest tests/ -v --tb=short      # run tests
    uv run ruff check .                     # lint
    uv run ruff format .                    # format
    uv run sphinx-build -b html docs/ docs/_build/html  # build docs
