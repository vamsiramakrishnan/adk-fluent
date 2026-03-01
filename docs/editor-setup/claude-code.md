# Claude Code Setup

Set up [Claude Code](https://docs.anthropic.com/en/docs/claude-code) to generate idiomatic adk-fluent and Google ADK code.

## 1. Project rules — `CLAUDE.md`

Create a `CLAUDE.md` file in your project root. Claude Code reads this file automatically at the start of every session.

```bash
curl -L https://raw.githubusercontent.com/vamsiramakrishnan/adk-fluent/master/CLAUDE.md \
  --create-dirs -o CLAUDE.md
```

Or create it manually with the content below:

```{dropdown} CLAUDE.md contents
:open:

\`\`\`markdown
# adk-fluent project rules

## What is adk-fluent?

A fluent builder API for Google's Agent Development Kit (ADK).
Reduces agent creation from 22+ lines to 1-3 lines while producing identical native ADK objects.

Docs: https://vamsiramakrishnan.github.io/adk-fluent/
PyPI: https://pypi.org/project/adk-fluent/

## Core API patterns

### Imports

Always import from the top-level package:

    from adk_fluent import Agent, Pipeline, FanOut, Loop
    from adk_fluent import S, C, P, A, M, T

Never import from internal modules like `adk_fluent._base` or `adk_fluent.agent`.

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

Sub-builders passed to workflow builders are auto-built — do not call `.build()` on steps.

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

    pipeline = Agent("a") >> Agent("b")          # Sequential (>>)
    fanout   = Agent("a") | Agent("b")           # Parallel (|)
    loop     = (Agent("a") >> Agent("b")) * 3    # Loop (*)

Both styles produce identical ADK objects. Mix freely.

### Single-letter namespace modules

- `S` — State transforms: `S.transform()`, `S.rename()`, `S.merge()`
- `C` — Context scoping: `C.none()`, `C.from_state()`, `C.user_only()`
- `P` — Prompt composition: `P.system()`, `P.guidelines()`, `P.text()`
- `A` — Artifacts: `A.read_text()`, `A.write()`
- `M` — Middleware: `M.retry()`, `M.log()`, `M.latency()`
- `T` — Tool wrappers: `T.fn()`, `T.schema()`

### Key methods on Agent builder

- `.instruct(text)` — Set the instruction/system prompt
- `.model(name)` — Set the model (e.g. "gemini-2.5-flash", "gemini-2.5-pro")
- `.tool(fn)` — Add a tool function
- `.writes(key)` — Write output to state key
- `.history("none")` — Disable conversation history for this agent
- `.describe(text)` — Set agent description
- `.sub_agent(agent)` — Add a sub-agent for transfer
- `.before_model(fn)` / `.after_model(fn)` — Callbacks
- `.inject(key=value)` — Dependency injection (hidden from LLM schema)
- `.context(C.none())` — Scope context
- `.build()` — Resolve to native ADK object
- `.explain()` — Print builder state for debugging
- `.validate()` — Early error detection
- `.clone(name)` — Deep copy with new name
- `.with_(key=value)` — Immutable variant

### Best practices

1. Use deterministic routing (Route) over LLM routing when the decision is rule-based
2. Use `.inject()` for infrastructure dependencies — never expose DB clients in tool schemas
3. Use `S.transform()` or plain functions for data transforms, not custom BaseAgent subclasses
4. Use `C.none()` to hide conversation history from background/utility agents
5. Use `M.retry()` middleware instead of retry logic inside tool functions
6. Every `.build()` returns a real ADK object — fully compatible with `adk web`, `adk run`, `adk deploy`

### Testing

    uv run pytest tests/ -v --tb=short

### Linting and formatting

    uv run ruff check .
    uv run ruff format .

### Documentation build

    uv run sphinx-build -b html docs/ docs/_build/html
\`\`\`
```

## 2. MCP server — live documentation access

MCP servers give Claude Code on-demand access to the full adk-fluent documentation, including API references, cookbook recipes, and method signatures.

### Option A: adk-fluent GitMCP (free)

Uses [GitMCP](https://gitmcp.io) to serve documentation directly from the GitHub repository.

```bash
claude mcp add --transport http adk-fluent https://gitmcp.io/vamsiramakrishnan/adk-fluent
```

No authentication required. Claude Code will automatically have access to all adk-fluent documentation.

**Usage** — just ask naturally:

```
Build me a pipeline with a researcher agent that searches the web,
then a writer agent that summarizes the findings using adk-fluent.
```

### Option B: Context7 MCP

Community MCP server that provides documentation context for many libraries including adk-fluent.

::::{tab-set}
:::{tab-item} HTTP transport

```bash
claude mcp add --transport http context7 https://mcp.context7.com/mcp
```

:::
:::{tab-item} Local (stdio)

```bash
claude mcp add context7 -- npx -y @upstash/context7-mcp
```

:::
::::

**Usage** — append `use context7` to your prompt:

```
Build me a pipeline with a researcher and writer agent using adk-fluent. use context7
```

## 3. Verify the setup

After adding the `CLAUDE.md` and MCP server, test it with a prompt like:

```
Create an adk-fluent agent that classifies customer support tickets
into categories, then routes them to specialized handler agents.
Use a FanOut for parallel processing and write results to state.
```

Claude Code should:
- Import from `adk_fluent` (not internal modules)
- Use the fluent builder pattern with method chaining
- Call `.build()` to produce native ADK objects
- Use `.writes()` for state management
- Follow the project conventions from `CLAUDE.md`
