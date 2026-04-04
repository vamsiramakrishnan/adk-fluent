# Gemini CLI / Claude Code Clone -- Production Coding Agent Harness

:::{tip} What you'll learn
How to build a fully-functional autonomous coding runtime using adk-fluent's harness primitives -- the **Harness Path**. This is the proof that the same framework that builds single-purpose agents can build a Claude-Code-class system. Covers all 5 layers and all 4 foundation primitives.
:::

_Source: `79_coding_agent_harness.py`_ · **Pathway: Harness** · _27 tests_

## The 5-Layer Architecture

Every production harness has five layers. Skip one and your harness will be fragile in a specific, predictable way.

```
┌──────────────────────────────────────────────────────────┐
│  5. RUNTIME         REPL, slash commands, interrupt       │
│  4. OBSERVABILITY   EventBus, tape, hooks, renderer       │
│  3. SAFETY          Permissions, sandbox, budgets          │
│  2. TOOLS           Workspace, web, git, processes, MCP    │
│  1. INTELLIGENCE    Agent + skills + manifold              │
└──────────────────────────────────────────────────────────┘
```

| Layer | What it does | What breaks without it |
|---|---|---|
| **Intelligence** | LLM + expertise + capability discovery | Agent doesn't know how to do the task |
| **Tools** | File I/O, shell, search, web, git | Agent can think but can't act |
| **Safety** | Permissions, sandboxing, token budgets | Agent can act but might destroy things |
| **Observability** | Events, logging, hooks, replay | You can't debug when things go wrong |
| **Runtime** | REPL, streaming, compression, interrupts | No way to interact with the agent |

---

## Layer 1: Intelligence

Agent with domain expertise from skills and rolling context window:

```python
from adk_fluent import Agent, H
from adk_fluent._context import C

agent = (
    Agent("coder", "gemini-2.5-pro")
    .use_skill("examples/skills/code_reviewer/")
    .instruct(
        "You are an expert coding assistant. Read the codebase, "
        "edit files, run tests, and self-correct until the task is done."
    )
    .context(C.rolling(n=20, summarize=True))
)
built = agent.build()
# Skills compile to cached static_instruction (not re-sent every turn)
assert "<skills>" in (built.static_instruction or "")
```

## Layer 2: Tools

### Workspace tools with diff-mode and multimodal

```python
tools = H.workspace(project, diff_mode=True, multimodal=True)
names = [t.__name__ for t in tools]

assert "apply_edit" in names   # diff_mode adds apply_edit
assert "edit_file" in names
assert "read_file" in names    # multimodal version for images/PDFs
assert "glob_search" in names
assert "grep_search" in names
assert "bash" in names
```

### Tool composition with `+` operator

```python
tools = (
    H.workspace(project)       # read, edit, write, glob, grep, bash, ls (7)
    + H.web()                  # fetch + search (2)
    + H.git_tools(project)     # status, diff, log, commit, branch (5)
    + H.processes(project)     # start, check, stop (3)
)
assert len(tools) >= 15
```

### Streaming workspace (PTY-based)

```python
chunks = []
tools = H.workspace(
    project,
    streaming=True,
    on_output=lambda chunk: chunks.append(chunk),
)
```

## Layer 3: Safety

### Permission policies (allow / ask / deny)

```python
permissions = (
    H.auto_allow("read_file", "glob_search", "grep_search", "list_dir")
    .merge(H.ask_before("edit_file", "write_file", "bash"))
    .merge(H.deny("rm_rf"))
)
# Deny wins over ask wins over allow
assert "rm_rf" in permissions.deny
assert "bash" in permissions.ask
assert "read_file" in permissions.allow
```

### Pattern-based permissions

```python
permissions = (
    H.allow_patterns("read_*", "list_*", "grep_*")
    .merge(H.deny_patterns("*_delete", "*_destroy"))
)
```

### Sandbox policy

```python
sandbox = H.sandbox(
    workspace=project,
    allow_shell=True,
    allow_network=True,
    read_paths=["/usr/share/dict"],
    write_paths=["/tmp/agent-work"],
)
```

### Budget monitor with threshold callbacks

```python
monitor = (
    H.budget_monitor(200_000)
    .on_threshold(0.7, lambda m: print(f"Warning: {m.utilization:.0%}"))
    .on_threshold(0.9, lambda m: print("Critical: compressing..."))
)

# Simulate usage
for _ in range(5):
    monitor.record_usage(input_tokens=20_000, output_tokens=10_000)

# At 150k/200k = 75%, warning fires
assert monitor.estimated_turns_remaining > 0

# After compression, adjust resets utilization
monitor.adjust(50_000)
```

### Per-tool error recovery

```python
policy = (
    H.tool_policy()
    .retry("bash", max_attempts=3, backoff=1.0)
    .retry("web_fetch", max_attempts=2, backoff=0.5)
    .skip("glob_search", fallback="No matching files found.")
    .ask("edit_file", handler=lambda name, args, err: True)
)
assert policy.rule_for("bash").action == "retry"
assert policy.rule_for("glob_search").action == "skip"
assert policy.rule_for("unknown_tool").action == "propagate"
```

### Merging tool policies from different sources

```python
base = H.tool_policy().retry("bash", max_attempts=2).skip("glob_search")
override = (
    H.tool_policy()
    .retry("bash", max_attempts=5)    # override base
    .retry("web_fetch", max_attempts=3)  # new rule
)
merged = base.merge(override)

assert merged.rule_for("bash").max_attempts == 5   # override wins
assert merged.rule_for("glob_search").action == "skip"  # kept from base
assert merged.rule_for("web_fetch").action == "retry"   # added from override
```

## Layer 4: Observability

### EventBus backbone

Everything subscribes to the EventBus instead of building its own observation layer:

```python
bus = H.event_bus(max_buffer=100)
events = []

bus.on("tool_call_start", lambda e: events.append(("start", e.tool_name)))
bus.on("tool_call_end", lambda e: events.append(("end", e.tool_name)))

bus.emit(ToolCallStart(tool_name="read_file", args={"path": "main.py"}))
bus.emit(ToolCallEnd(tool_name="read_file", result="...", duration_ms=42.0))

assert events == [("start", "read_file"), ("end", "read_file")]
assert len(bus.buffer) == 2  # buffered for late subscribers
```

### Error isolation

One failing subscriber never blocks others:

```python
def bad_handler(e):
    raise RuntimeError("observer crashed")

def good_handler(e):
    results.append(e.tool_name)

bus.on("tool_call_start", bad_handler)
bus.on("tool_call_start", good_handler)

bus.emit(ToolCallStart(tool_name="bash"))
assert results == ["bash"]  # good handler runs despite bad handler crash
```

### Session tape (replayable recording)

```python
tape = bus.tape(max_events=1000)

bus.emit(ToolCallStart(tool_name="read_file"))
bus.emit(ToolCallEnd(tool_name="read_file", duration_ms=15.0))
bus.emit(UsageUpdate(input_tokens=1000, output_tokens=500))

assert tape.size == 3
```

### Hooks (shell commands on events)

```python
hooks = (
    H.hooks(project)
    .on_edit("ruff check {file_path}")
    .on_error("notify-send 'Agent error: {error}'")
    .on("turn_complete", "echo 'turn done'")
)
```

### Event renderer

```python
renderer = H.renderer("plain", show_timing=True, show_args=True)
text = renderer.render(ToolCallStart(tool_name="edit_file", args={"path": "main.py"}))
assert "edit_file" in text
```

### Foundation primitives compose through EventBus

```python
bus = H.event_bus()

# All four foundations emit through the single bus
policy = H.tool_policy().retry("bash").with_bus(bus)
monitor = H.budget_monitor(100).on_threshold(0.9, lambda m: None).with_bus(bus)
ledger = H.task_ledger().with_bus(bus)
```

## Layer 5: Runtime

### Slash commands

```python
cmds = H.commands()
cmds.register("model", lambda args: f"Model: {args}", description="Switch model")
cmds.register("clear", lambda args: "Context cleared.", description="Clear context")
cmds.register("compact", lambda args: "Compacted.", description="Compress context")
cmds.register("help", lambda args: cmds.help_text(), description="Show commands")

assert cmds.dispatch("/model gemini-2.5-flash") == "Model: gemini-2.5-flash"
```

### Cooperative cancellation (interrupt and resume)

```python
token = H.cancellation_token()
token.begin_turn("Fix the bug in auth.py")
token.record_tool_call("read_file", {"path": "auth.py"})
token.record_tool_call("grep_search", {"pattern": "authenticate"})

# User hits Ctrl-C
token.cancel()
assert token.is_cancelled

# Snapshot captures mid-turn state
snapshot = token.snapshot
assert snapshot is not None
assert "Fix the bug" in snapshot.prompt
assert len(snapshot.tool_calls_completed) == 2

# Resume prompt includes context of what was done
resume = snapshot.resume_prompt()
assert "Resuming" in resume
assert "read_file" in resume
assert "grep_search" in resume

# Reset for next turn
token.reset()
assert not token.is_cancelled
```

### Cancellation callback (blocks tools when cancelled)

```python
from adk_fluent._harness._interrupt import CancellationToken, make_cancellation_callback

token = CancellationToken()
callback = make_cancellation_callback(token)

# Normal operation: callback returns None (allow execution)
result = callback(None, type("T", (), {"name": "read_file"})(), {}, None)
assert result is None

# After cancellation: callback returns error dict
token.cancel()
result = callback(None, type("T", (), {"name": "bash"})(), {}, None)
assert isinstance(result, dict)
assert "cancelled" in result["error"].lower()
```

### Task ledger (LLM-callable background tasks)

```python
ledger = H.task_ledger(max_tasks=5).with_bus(bus)
tools = ledger.tools()
tool_names = [t.__name__ for t in tools]
assert tool_names == ["launch_task", "check_task", "list_tasks", "cancel_task"]

# LLM launches a task
launch, check, list_tasks, cancel = tools
result = launch("run-tests", "Execute pytest suite")
assert "registered" in result

# LLM checks status
result = check("run-tests")
assert "pending" in result

# Simulate completion
ledger.start("run-tests")
ledger.complete("run-tests", "All 47 tests passed")

result = check("run-tests")
assert "complete" in result
assert "47 tests passed" in result

# Lifecycle events emitted through bus
assert len(events) >= 3  # pending, running, complete
```

### Git checkpoint (undo support)

```python
cp = H.git(project)
# GitCheckpointer wraps git stash/tag operations
assert cp is not None
assert hasattr(cp, "create")
assert hasattr(cp, "restore")
```

### REPL configuration

```python
from adk_fluent._harness._repl import ReplConfig

config = ReplConfig(
    prompt_prefix="coder> ",
    welcome_message="Ready. Type /help for commands.",
    max_turns=100,
    auto_checkpoint=True,
)
assert config.prompt_prefix == "coder> "
assert "/exit" in config.exit_commands
```

### Context compressor

```python
compressor = H.compressor(threshold=100_000)
assert compressor.should_compress(150_000) is True
assert compressor.should_compress(50_000) is False
```

---

## Full Assembly: Complete Coding Agent (~50 lines)

All 5 layers wired together into a production-ready autonomous runtime:

```python
from adk_fluent import Agent, H
from adk_fluent._context import C
from adk_fluent._harness import make_cancellation_callback, ReplConfig

project = "/path/to/project"

# --- EventBus backbone ---
bus = H.event_bus(max_buffer=1000)
tape = bus.tape()

# --- Layer 1: Intelligence ---
agent = (
    Agent("coder", "gemini-2.5-pro")
    .use_skill("skills/code_review/")
    .instruct("You are an expert coding assistant.")
    .context(C.rolling(n=20, summarize=True))
)

# --- Layer 2: Tools ---
ledger = H.task_ledger().with_bus(bus)
agent = agent.tools(
    H.workspace(project, diff_mode=True, multimodal=True)
    + H.web()
    + H.git_tools(project)
    + H.processes(project)
    + ledger.tools()
)

# --- Layer 3: Safety ---
agent = agent.harness(
    permissions=(
        H.auto_allow("read_file", "glob_search", "grep_search", "list_dir")
        .merge(H.ask_before("edit_file", "write_file", "bash"))
        .merge(H.deny("rm_rf"))
    ),
    sandbox=H.workspace_only(project),
    memory=H.memory(f"{project}/.agent-memory.md"),
    on_error=H.on_error(retry={"bash", "web_fetch"}, skip={"glob_search"}),
)

# --- Layer 4: Observability ---
token = H.cancellation_token()
monitor = H.budget_monitor(200_000).on_threshold(0.9, lambda m: None).with_bus(bus)
policy = H.tool_policy().retry("bash", max_attempts=3).with_bus(bus)
hooks = H.hooks(project).on_edit("ruff check {file_path}")
bus.hooks(hooks)

agent = (
    agent
    .before_tool(bus.before_tool_hook())
    .before_tool(make_cancellation_callback(token))
    .after_tool(bus.after_tool_hook())
    .after_tool(policy.after_tool_hook())
    .after_model(bus.after_model_hook())
    .after_model(monitor.after_model_hook())
)

# --- Layer 5: Runtime ---
cmds = H.commands()
cmds.register("clear", lambda a: "Context cleared.", description="Clear context")
cmds.register("model", lambda a: f"Model: {a}", description="Switch model")
cmds.register("help", lambda a: cmds.help_text(), description="Show commands")

built = agent.build()

repl = H.repl(
    built,
    hooks=hooks,
    compressor=H.compressor(100_000),
    config=ReplConfig(
        prompt_prefix="coder> ",
        welcome_message="Coding agent ready. Type /help for commands.",
        auto_checkpoint=True,
    ),
)
# await repl.run()  # Start the interactive loop

# ---- Verify the complete assembly ----

# Intelligence: skills loaded
assert "<skills>" in (built.static_instruction or "")

# Tools: workspace + web + git + processes + tasks
tool_count = len(built.tools)
assert tool_count >= 20, f"Expected 20+ tools, got {tool_count}"

# Safety: permission callback wired
assert built.before_tool_callback is not None

# Observability: bus has subscribers
assert bus.subscriber_count >= 2

# Runtime: commands registered
assert cmds.size == 5
assert cmds.dispatch("/help") is not None

# Runtime: cancellation token ready
assert not token.is_cancelled

# Runtime: budget monitor tracks usage
monitor.record_usage(input_tokens=5000, output_tokens=2000)
assert monitor.current_tokens == 7000

# Runtime: task ledger functional
ledger.register("test-run", "pytest execution")
ledger.start("test-run")
assert ledger.active_count == 1

# Runtime: REPL can be constructed
assert isinstance(repl, HarnessRepl)
assert repl.config.prompt_prefix == "coder> "
```

## Manifold: Runtime Capability Discovery

When you have 100+ tools but the LLM can only handle ~30 at once:

```python
manifold = H.manifold(
    tools=None,           # ToolRegistry (BM25-indexed)
    skills="skills/",     # Skill directory
    always_loaded=["search_code"],
    max_tools=30,
)
# Provides meta-tools: search_capabilities, load_capability, finalize_capabilities
result = manifold.search("code review")
```

## Composition Proof: Foundation Primitives Working Together

All four foundation primitives compose through EventBus. One subscription point, one observation layer, zero duplication:

```python
bus = H.event_bus(max_buffer=100)
all_events = []
bus.subscribe(lambda e: all_events.append(e.kind))

# ToolPolicy -> emits errors
_policy = H.tool_policy().retry("bash").with_bus(bus)

# BudgetMonitor -> emits compression triggers
monitor = H.budget_monitor(100).on_threshold(0.9, lambda m: None).with_bus(bus)

# TaskLedger -> emits task lifecycle
ledger = H.task_ledger().with_bus(bus)

# Simulate activity
monitor.record_usage(95, 0)  # triggers 0.95 threshold
ledger.register("build", "npm run build")
ledger.start("build")
ledger.complete("build", "success")

# All events flow through the single bus
assert "compression_triggered" in all_events
assert "task_event" in all_events
assert all_events.count("task_event") == 3  # pending, running, complete
```

---

## Complete Source Code

The full source with all 26 test functions is at [`examples/cookbook/79_coding_agent_harness.py`](../../../examples/cookbook/79_coding_agent_harness.py).

Run all tests:

```bash
uv run pytest examples/cookbook/79_coding_agent_harness.py -v
```

---

## Design Philosophy

### Why composable layers, not a monolithic `HarnessAgent`?

Every harness is different:
- **Code review** needs diff-mode editing + git tools but no web access
- **Research** needs web tools but no file editing
- **DevOps** needs process management + MCP servers but no notebooks

The `H` namespace gives you building blocks. You compose what you need. The composition _is_ the configuration.

### The Four Foundation Primitives

| Primitive | What it prevents | Composes with |
|---|---|---|
| `EventBus` | Building separate observation layers | SessionTape, HookRegistry, Renderer |
| `ToolPolicy` | Reimplementing per-tool retry/fallback | `M.retry()`, ErrorStrategy |
| `BudgetMonitor` | Reimplementing token tracking | `C.rolling()`, ContextCompressor |
| `TaskLedger` | Reimplementing task tracking | Core dispatch primitives |

They exist because the core framework (S, C, M, T, G) is **declarative and agent-scoped**. Harness building needs **imperative, session-scoped** control.

:::{seealso}
- [Harness User Guide](../../user-guide/harness.md) -- full reference
- [Recipe 78: Harness + Skills](78_harness_and_skills.md) -- combining skills with harness
- [Recipe 77: Skill-Based Agents](77_skill_based_agents.md) -- pure skills patterns
- [Three Pathways](../../user-guide/index.md#three-pathways) -- how Harness fits into the bigger picture
:::
