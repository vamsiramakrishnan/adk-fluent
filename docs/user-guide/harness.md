# Building Harnesses -- From Agent to Autonomous Runtime

## The Fork in the Road

Every framework reaches a point where single-purpose agent building diverges from autonomous runtime building. This is that fork.

```
                    adk-fluent
                        │
          ┌─────────────┼─────────────┐
          │             │             │
    Single Agent    Workflow      Harness
    Agent("x")     A >> B >> C   H.workspace()
    .instruct()    .step()       H.event_bus()
    .tool(fn)      .branch()     H.budget_monitor()
    .ask(prompt)   .build()      H.repl()
          │             │             │
     One question   Multi-step   Autonomous
     one answer     pipeline     coding runtime
```

Building a single agent is **declarative** — you describe what the agent is. Building a harness is **imperative** — you wire up how it runs. The core framework (`Agent`, `Pipeline`, `FanOut`, `Loop`) handles the first path. The `H` namespace handles the second.

A **harness** is what turns a single-purpose agent into an autonomous coding runtime — the kind of thing Claude Code, Gemini CLI, or Cursor's agent mode is built on. It's the difference between "an LLM that can answer questions" and "an LLM that can read your codebase, edit files, run tests, and self-correct."

adk-fluent doesn't ship a harness. It ships the building blocks so you can build *your* harness, tuned to your domain, your security model, your tools.

## The Five Layers

Every production harness has five layers. Skip one and your harness will be fragile in a specific, predictable way.

```
┌──────────────────────────────────────────────────────┐
│  5. RUNTIME         REPL, event loop, rendering      │
│  4. OBSERVABILITY   EventBus, tape, hooks, renderer  │
│  3. SAFETY          Permissions, sandbox, budgets     │
│  2. TOOLS           Workspace, web, MCP, git, tasks   │
│  1. INTELLIGENCE    Agent + skills + manifold         │
└──────────────────────────────────────────────────────┘
```

| Layer | What it does | What breaks without it |
|---|---|---|
| **Intelligence** | LLM + expertise + capability discovery | Agent doesn't know how to do the task |
| **Tools** | File I/O, shell, search, web, git | Agent can think but can't act |
| **Safety** | Permissions, sandboxing, token budgets | Agent can act but might destroy things |
| **Observability** | Events, logging, hooks, replay | You can't debug when things go wrong |
| **Runtime** | REPL, streaming, compression, interrupts | No way to interact with the agent |

## Harness sub-packages (the short tour)

The `H` namespace is a thin façade. Every concern lives in its own
self-contained sub-package with frozen value types, mutable state
containers, and an ADK `BasePlugin` for session-scoped installation.
Each package has a dedicated user-guide page with the full cookbook:

| Package | Guide | What it is |
|---|---|---|
| `adk_fluent._hooks` | [hooks](hooks.md) | 12-event registry with `HookDecision` allow/deny/modify/replace/ask/inject and shell-command hooks |
| `adk_fluent._permissions` | [permissions](permissions.md) | 5-mode `PermissionPolicy` (default/accept_edits/plan/bypass/dont_ask), `ApprovalMemory`, `PermissionPlugin` |
| `adk_fluent._plan_mode` | [plan-mode](plan-mode.md) | `PlanMode` latch + `enter_plan_mode`/`exit_plan_mode` tool pair + `PlanModePolicy` + `PlanModePlugin` |
| `adk_fluent._session` | [session](session.md) · [durable-events](durable-events.md) | `SessionTape` with seq/cursor/async `tail()`, pluggable `TapeBackend` (JSONL/InMemory/Null/Chain), `ForkManager`, `SessionStore`, `SessionSnapshot`, `SessionPlugin`, `stream_from_cursor`, workflow lifecycle events |
| `adk_fluent._reactor` | [reactor](reactor.md) | `Signal` + `SignalPredicate` + `Reactor` -- reactive state cells over the tape with priority scheduling, preemption, and per-agent `AgentToken` / `TokenRegistry` |
| `adk_fluent._subagents` | [subagents](subagents.md) | Runtime-decided specialist dispatch — `SubagentSpec`/`Registry`/`Runner` and `make_task_tool` |
| `adk_fluent._usage` | [usage](usage.md) | `TurnUsage`/`AgentUsage`/`UsageTracker` with a frozen `CostTable` + `UsagePlugin` |
| `adk_fluent._budget` | [budget](budget.md) | `BudgetPolicy` + `BudgetMonitor` + `Threshold` + `BudgetPlugin` |
| `adk_fluent._compression` | [compression](compression.md) | `ContextCompressor` + `CompressionStrategy` with `pre_compact` hook integration |
| `adk_fluent._fs` | [fs](fs.md) | `FsBackend` Protocol + `LocalBackend`/`MemoryBackend`/`SandboxedBackend` + `workspace_tools_with_backend` -- retargetable, sandbox-safe filesystem layer behind every workspace tool |

All types are re-exported at the top level so you never have to reach
into a private module:

```python
from adk_fluent import (
    H,                                              # façade
    HookEvent, HookDecision, HookRegistry,          # _hooks
    PermissionMode, PermissionPolicy,               # _permissions
    SessionTape, SessionStore, ForkManager,         # _session
    SubagentSpec, SubagentRegistry, make_task_tool, # _subagents
    UsageTracker, CostTable,                        # _usage
    BudgetMonitor, BudgetPolicy, Threshold,         # _budget
    ContextCompressor, CompressionStrategy,         # _compression
    FsBackend, LocalBackend, MemoryBackend,         # _fs
)
```

Each sub-package ships its own ADK `BasePlugin`. Install them on the
root `App` or `Runner` so the policy/tape/tracker/budget/compression
layer applies to every agent in the invocation tree — including
subagent specialists spawned at runtime:

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import App, H

app = (
    App("coder-harness")
    .plugin(H.hooks("/project").plugin())
    .plugin(H.permission_plugin(policy=permissions, handler=ask_user))
    .plugin(H.plan_mode_plugin())
    .plugin(H.session_plugin())
    .plugin(H.usage_plugin(tracker))
    .plugin(H.budget_plugin(monitor))
    .build()
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { App, H } from "adk-fluent-ts";

const app = new App("coder-harness")
  .plugin(H.hooks("/project").plugin())
  .plugin(H.permissionPlugin({ policy: permissions, handler: askUser }))
  .plugin(H.planModePlugin())
  .plugin(H.sessionPlugin())
  .plugin(H.usagePlugin(tracker))
  .plugin(H.budgetPlugin(monitor))
  .build();
```
:::
::::

## Layer 1: Intelligence

Start with an agent that has domain expertise. Skills load from SKILL.md files — they're cached in `static_instruction` and never re-sent to the LLM on every turn.

```python
from adk_fluent import Agent, H

agent = (
    Agent("coder", "gemini-2.5-pro")
    .use_skill("skills/code_review/")
    .use_skill("skills/python_best_practices/")
    .instruct("You are an expert coding assistant. Help the user.")
)
```

For dynamic capability discovery (the manifold pattern), see [Manifold Guide](manifold.md).

## Layer 2: Tools

The `H` namespace provides sandboxed tool factories. Combine them with `+`:

```python
tools = (
    H.workspace("/project", diff_mode=True, multimodal=True)
    + H.web()
    + H.git_tools("/project")
    + H.processes("/project")
    + H.notebook("/project")
)

agent = agent.tools(tools)
```

### What each tool set provides

| Factory | Tools | Purpose |
|---|---|---|
| `H.workspace(path)` | read, edit, write, glob, grep, bash, ls | Core file/shell operations |
| `H.web()` | web_fetch, web_search | URL fetching and search |
| `H.git_tools(path)` | git_status, git_diff, git_log, git_commit, git_branch | Version control |
| `H.processes(path)` | start_process, check_process, stop_process | Background dev servers |
| `H.notebook(path)` | read_notebook, edit_notebook_cell | Jupyter notebooks |
| `H.mcp(servers)` | (dynamic) | MCP server tools |

### Workspace options

```python
H.workspace(
    "/project",
    allow_shell=True,      # Enable bash tool
    allow_network=True,    # Allow network from shell
    read_only=False,       # Disable edit/write
    streaming=True,        # PTY-based streaming bash
    diff_mode=True,        # Preview edits as diffs before applying
    multimodal=True,       # Read images/PDFs as base64
    max_output_bytes=100_000,
)
```

## Layer 3: Safety

Three concerns: **who can call what** (permissions), **where can they write** (sandbox), and **how much can they spend** (budgets).

### Permissions

Compose policies with `.merge()`. Deny wins over ask wins over allow.

```python
permissions = (
    H.auto_allow("read_file", "glob_search", "grep_search", "list_dir")
    .merge(H.ask_before("edit_file", "write_file", "bash"))
    .merge(H.deny("rm_rf"))
)
```

Pattern-based rules for large tool sets:

```python
permissions = (
    H.allow_patterns("read_*", "list_*", "grep_*")
    .merge(H.deny_patterns("*_delete", "*_destroy"))
)
```

### Sandbox

Confines file operations to the workspace directory. Symlink-safe — resolves real paths before checking containment.

```python
sandbox = H.sandbox(
    workspace="/project",
    allow_shell=True,
    allow_network=True,
    read_paths=["/usr/share/dict"],   # Additional readable paths
    write_paths=["/tmp/agent-work"],  # Additional writable paths
)
```

### Token budgets

`BudgetMonitor` tracks cumulative tokens and fires callbacks at thresholds. It does NOT compress — it triggers your handler, which decides what to do.

```python
def on_budget_warning(monitor):
    print(f"Warning: {monitor.utilization:.0%} budget used, "
          f"~{monitor.estimated_turns_remaining} turns remaining")

def on_budget_critical(monitor):
    # Switch to aggressive compression
    print(f"Critical: compressing context")
    monitor.adjust(monitor.current_tokens // 2)

monitor = (
    H.budget_monitor(200_000)
    .on_threshold(0.7, on_budget_warning)
    .on_threshold(0.9, on_budget_critical)
)

agent = agent.after_model(monitor.after_model_hook())
```

### Wiring safety with `.harness()`

The `.harness()` method bundles all safety concerns and wires the callbacks:

```python
agent = agent.harness(
    permissions=permissions,
    sandbox=H.workspace_only("/project"),
    usage=H.usage(cost_per_million_input=2.50, cost_per_million_output=10.0),
    memory=H.memory("/project/.agent-memory.md"),
    on_error=H.on_error(retry={"bash", "web_fetch"}, skip={"glob_search"}),
)
```

## Layer 4: Observability

The `EventBus` is the backbone. Everything subscribes to it instead of building its own observation layer.

```python
bus = H.event_bus()

# SessionTape records everything to JSONL
tape = bus.tape()

# Hooks intercept the agent's execution at ADK lifecycle points. See
# docs/user-guide/hooks.md for the full decision protocol and cookbook.
from adk_fluent._hooks import HookDecision, HookEvent, HookMatcher

hooks = (
    H.hooks("/project")
    .shell(
        HookEvent.POST_TOOL_USE,
        "ruff check {tool_input[file_path]}",
        match=HookMatcher.for_tool(
            HookEvent.POST_TOOL_USE, "edit_file", file_path="*.py"
        ),
    )
    .on(
        HookEvent.TOOL_ERROR,
        lambda ctx: HookDecision.inject(
            f"Tool {ctx.tool_name} failed: {ctx.error}. Consider rolling back."
        ),
    )
)
# Install the registry as an ADK plugin on your App/Runner:
#     Runner(app=App(...), plugins=[hooks.as_plugin()])

# Wire the bus into agent callbacks
agent = (
    agent
    .before_tool(bus.before_tool_hook())
    .after_tool(bus.after_tool_hook())
    .after_model(bus.after_model_hook())
)
```

### Per-tool error recovery

`ToolPolicy` gives each tool its own error handling — retries with backoff for transient failures, graceful skips for non-critical tools, user escalation for dangerous operations:

```python
policy = (
    H.tool_policy()
    .retry("bash", max_attempts=3, backoff=1.0)
    .retry("web_fetch", max_attempts=2, backoff=0.5)
    .skip("glob_search", fallback="No matching files found.")
    .ask("edit_file", handler=user_approval_fn)
    .with_bus(bus)  # Emits error events
)

agent = agent.after_tool(policy.after_tool_hook())
```

### Rendering events

Renderers convert events to display strings. They don't handle I/O — you write to your output:

```python
renderer = H.renderer("rich", show_timing=True, show_args=False)

# In your event loop:
for event in events:
    line = renderer.render(event)
    if line:
        print(line)
```

## Layer 5: Runtime

### Interactive REPL

```python
repl = H.repl(
    agent.build(),
    dispatcher=H.dispatcher(bus=bus),
    compressor=H.compressor(threshold=100_000),
    config=ReplConfig(
        prompt_prefix="coder> ",
        welcome_message="Ready. Type /help for commands.",
        auto_checkpoint=True,  # Git checkpoint before destructive tools
    ),
)
# Hooks install at the App/Runner layer, not on the REPL — see docs/user-guide/hooks.md

await repl.run()
```

### Slash commands

```python
cmds = H.commands()
cmds.register("clear", lambda args: "Context cleared.", description="Clear context")
cmds.register("model", lambda args: set_model(args), description="Switch model")
cmds.register("undo", lambda args: git_checkpoint.restore(), description="Undo last change")
cmds.register("compact", lambda args: compress(), description="Compress context")
```

### Interrupt and resume

Cooperative cancellation — the token is checked before each tool call:

```python
from adk_fluent._harness import make_cancellation_callback

token = H.cancellation_token()
agent = agent.before_tool(make_cancellation_callback(token))

# In your UI thread:
token.cancel()               # Interrupt
snapshot = token.snapshot     # Mid-turn state
resume_prompt = snapshot.resume_prompt()  # "Resuming: Fix the bug..."
token.reset()                # Ready for next turn
```

### Conversation forking

Branch session state for parallel exploration:

```python
forks = H.forks()

# Save current state
forks.fork("conservative", current_state)
forks.fork("aggressive", current_state)

# Compare approaches
diff = forks.diff("conservative", "aggressive")

# Merge: take conservative approach but include aggressive findings
merged = forks.merge("conservative", "aggressive", strategy="prefer", prefer="conservative")
```

### Background tasks

`TaskLedger` bridges `dispatch()`/`join()` to LLM-callable tools:

```python
ledger = H.task_ledger().with_bus(bus)
agent = agent.tools(ledger.tools())  # [launch_task, check_task, list_tasks, cancel_task]
```

## Putting It All Together

Here's a complete Claude-Code-class harness in ~50 lines:

```python
from adk_fluent import Agent, H, C
from adk_fluent._harness import ReplConfig, make_cancellation_callback

project = "/path/to/project"

# --- EventBus backbone ---
bus = H.event_bus()
tape = bus.tape()

# --- Intelligence ---
agent = (
    Agent("coder", "gemini-2.5-pro")
    .use_skill("skills/code_review/")
    .use_skill("skills/python_best_practices/")
    .instruct("You are an expert coding assistant.")
    .context(C.rolling(n=20, summarize=True))
)

# --- Tools ---
agent = agent.tools(
    H.workspace(project, diff_mode=True, multimodal=True)
    + H.web()
    + H.git_tools(project)
    + H.processes(project)
    + H.task_ledger().with_bus(bus).tools()
)

# --- Safety ---
agent = agent.harness(
    permissions=(
        H.auto_allow("read_file", "glob_search", "grep_search", "list_dir")
        .merge(H.ask_before("edit_file", "write_file", "bash"))
    ),
    sandbox=H.workspace_only(project),
    usage=H.usage(cost_per_million_input=2.50, cost_per_million_output=10.0),
    memory=H.memory(f"{project}/.agent-memory.md"),
    on_error=H.on_error(retry={"bash"}, skip={"glob_search"}),
)

# --- Observability ---
token = H.cancellation_token()
monitor = H.budget_monitor(200_000).on_threshold(0.9, lambda m: print("Compressing...")).with_bus(bus)

agent = (
    agent
    .before_tool(bus.before_tool_hook())
    .before_tool(make_cancellation_callback(token))
    .after_tool(bus.after_tool_hook())
    .after_model(bus.after_model_hook())
    .after_model(monitor.after_model_hook())
)

# --- Runtime ---
repl = H.repl(
    agent.build(),
    compressor=H.compressor(100_000),
)
# Install a HookRegistry as an ADK plugin alongside the repl's runner.
# See docs/user-guide/hooks.md for the hook cookbook.

await repl.run()
```

## Design Philosophy

### Why not a `HarnessAgent` class?

Because every harness is different. A code review harness needs diff-mode editing and git tools but no web access. A research harness needs web tools but no file editing. A DevOps harness needs process management and MCP servers but no notebook support.

A monolithic `HarnessAgent` would either:
1. Include everything (slow, insecure, wasteful)
2. Include nothing (then it's just an Agent)
3. Make you disable features (negative configuration — worse DX than assembling what you need)

The `H` namespace gives you building blocks. You compose what you need. The composition is the configuration.

### Why separate EventBus, ToolPolicy, BudgetMonitor, TaskLedger?

These are the **four foundations** that prevent the common pitfall of reinventing framework capabilities at the harness level:

| Foundation | What it prevents | Composes with |
|---|---|---|
| `EventBus` | Building separate observation layers in each module | SessionTape, HookRegistry, Renderer |
| `ToolPolicy` | Reimplementing per-tool retry/fallback logic | `M.retry()`, ErrorStrategy |
| `BudgetMonitor` | Reimplementing token tracking outside `C.budget()` | `C.rolling()`, ContextCompressor |
| `TaskLedger` | Reimplementing task tracking outside `dispatch()`/`join()` | Core dispatch primitives |

They exist because the core framework (S, C, M, T, G) is **declarative and agent-scoped** — perfect for building agents, but harness building needs **imperative, session-scoped** control. These four primitives bridge that gap.

### When to take the harness fork

You need a harness when your agent needs to:

- **Persist across turns** — multi-turn conversation with memory, not one-shot Q&A
- **Use dangerous tools** — file editing, shell execution, git operations require permissions and sandboxing
- **Self-correct** — read errors, retry, adjust approach without human intervention
- **Stay within bounds** — token budgets, cost limits, time constraints
- **Be observable** — you need to know what happened, replay sessions, fire hooks

If your agent just answers questions or runs a pipeline, stick with `Agent` + workflows. The moment it needs to *act autonomously in the world* — reading codebases, editing files, running tests, managing processes — that's when you cross the fork into harness territory.

### The cookbook proof

See `examples/cookbook/79_coding_agent_harness.py` for a complete, tested, runnable Claude-Code-class harness built entirely from these building blocks. 27 tests, all 5 layers, all 4 foundation primitives wired together.
