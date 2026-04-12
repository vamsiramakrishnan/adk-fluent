"""Gemini CLI / Claude Code Clone — Production Coding Agent Harness

Builds a fully-functional autonomous coding runtime using adk-fluent's
harness primitives. This is the proof: the same framework that builds
single-purpose agents can build a Claude-Code-class system.

Architecture (5 layers):

    ┌──────────────────────────────────────────────────────────┐
    │  5. RUNTIME         REPL, slash commands, interrupt      │
    │  4. OBSERVABILITY   EventBus, tape, hooks, renderer      │
    │  3. SAFETY          Permissions, sandbox, budgets         │
    │  2. TOOLS           Workspace, web, git, processes, MCP   │
    │  1. INTELLIGENCE    Agent + skills + manifold             │
    └──────────────────────────────────────────────────────────┘

Every test builds a real, wirable harness component. Together they
compose into the complete system shown in test_full_coding_agent().

Run: uv run pytest examples/cookbook/79_coding_agent_harness.py -v
"""

import os
import tempfile

import pytest

from adk_fluent import Agent, H
from adk_fluent._context import C
from adk_fluent._harness import (
    BudgetMonitor,
    EventBus,
    TaskLedger,
    ToolPolicy,
)
from adk_fluent._harness._commands import CommandRegistry
from adk_fluent._harness._events import (
    ErrorOccurred,
    ToolCallEnd,
    ToolCallStart,
    UsageUpdate,
)
from adk_fluent._harness._interrupt import (
    CancellationToken,
    make_cancellation_callback,
)
from adk_fluent._harness._repl import HarnessRepl, ReplConfig


# ======================================================================
# Layer 1: Intelligence — Agent + Skills + Context Engineering
# ======================================================================


def test_intelligence_layer():
    """Agent with domain expertise from skills + rolling context."""
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
    assert "code_reviewer" in (built.static_instruction or "")
    # Per-task instruction is separate
    assert built.instruction is not None


# ======================================================================
# Layer 2: Tools — Workspace + Web + Git + Processes
# ======================================================================


def test_workspace_tools():
    """Sandboxed workspace with diff-mode editing and multimodal reads."""
    with tempfile.TemporaryDirectory() as project:
        tools = H.workspace(project, diff_mode=True, multimodal=True)
        names = [t.__name__ for t in tools]

        # diff_mode adds apply_edit alongside edit_file
        assert "apply_edit" in names
        assert "edit_file" in names

        # multimodal replaces read_file with multimodal version
        assert "read_file" in names

        # Core tools always present
        assert "glob_search" in names
        assert "grep_search" in names
        assert "bash" in names


def test_tool_composition():
    """Combine tool sets with + operator."""
    with tempfile.TemporaryDirectory() as project:
        tools = H.workspace(project) + H.web() + H.git_tools(project) + H.processes(project)
        names = [t.__name__ if hasattr(t, "__name__") else str(t) for t in tools]

        # Workspace: read, edit, write, glob, grep, bash, ls = 7
        assert "read_file" in names
        assert "bash" in names

        # Git: status, diff, log, commit, branch = 5
        assert "git_status" in names
        assert "git_commit" in names

        # Processes: start, check, stop = 3
        assert "start_process" in names

        # Web: fetch + search = 2
        assert len(tools) >= 15  # at least 15 tools


def test_streaming_workspace():
    """PTY-based streaming bash for long-running commands."""
    with tempfile.TemporaryDirectory() as project:
        chunks = []
        tools = H.workspace(
            project,
            streaming=True,
            on_output=lambda chunk: chunks.append(chunk),
        )
        names = [t.__name__ for t in tools]
        # Streaming replaces blocking bash
        assert "bash" in names


# ======================================================================
# Layer 3: Safety — Permissions + Sandbox + Budget + Error Recovery
# ======================================================================


def test_permission_policies():
    """Compose permission layers: allow, ask, deny."""
    permissions = (
        H.auto_allow("read_file", "glob_search", "grep_search", "list_dir")
        .merge(H.ask_before("edit_file", "write_file", "bash"))
        .merge(H.deny("rm_rf"))
    )
    # Deny wins over ask wins over allow
    assert "rm_rf" in permissions.deny
    assert "bash" in permissions.ask
    assert "read_file" in permissions.allow


def test_pattern_permissions():
    """Pattern-based permissions for large tool sets."""
    permissions = H.allow_patterns("read_*", "list_*", "grep_*").merge(H.deny_patterns("*_delete", "*_destroy"))
    assert permissions.allow_patterns is not None
    assert permissions.deny_patterns is not None


def test_sandbox_policy():
    """File operations confined to workspace."""
    with tempfile.TemporaryDirectory() as project:
        sandbox = H.sandbox(
            workspace=project,
            allow_shell=True,
            allow_network=True,
            read_paths=["/usr/share/dict"],
            write_paths=["/tmp/agent-work"],
        )
        assert sandbox.workspace == str(os.path.realpath(project))
        assert sandbox.allow_shell is True
        assert "/usr/share/dict" in sandbox.read_paths


def test_budget_monitor():
    """Token budget lifecycle with threshold callbacks."""
    warnings = []
    compressions = []

    monitor = (
        H.budget_monitor(200_000)
        .on_threshold(0.7, lambda m: warnings.append(m.utilization))
        .on_threshold(0.9, lambda m: compressions.append(m.utilization))
    )

    # Simulate 5 turns of usage
    for _ in range(5):
        monitor.record_usage(input_tokens=20_000, output_tokens=10_000)

    # At 150k/200k = 75%, warning should have fired
    assert len(warnings) == 1
    assert warnings[0] == pytest.approx(0.75, abs=0.01)
    assert monitor.estimated_turns_remaining > 0

    # Hit 90% threshold
    monitor.record_usage(input_tokens=20_000, output_tokens=10_000)
    assert len(compressions) == 1

    # After compression, adjust and thresholds reset
    monitor.adjust(50_000)
    assert monitor.utilization == pytest.approx(0.25, abs=0.01)


def test_tool_policy():
    """Per-tool error recovery with backoff."""
    policy = (
        H.tool_policy()
        .retry("bash", max_attempts=3, backoff=1.0)
        .retry("web_fetch", max_attempts=2, backoff=0.5)
        .skip("glob_search", fallback="No matching files found.")
        .ask("edit_file", handler=lambda name, args, err: True)
    )

    assert policy.rule_for("bash").action == "retry"
    assert policy.rule_for("bash").max_attempts == 3
    assert policy.rule_for("bash").backoff == 1.0
    assert policy.rule_for("glob_search").action == "skip"
    assert policy.rule_for("edit_file").action == "ask"
    assert policy.rule_for("unknown_tool").action == "propagate"


def test_tool_policy_merge():
    """Merge policies from different sources."""
    base = H.tool_policy().retry("bash", max_attempts=2).skip("glob_search")
    override = (
        H.tool_policy()
        .retry("bash", max_attempts=5)  # override base
        .retry("web_fetch", max_attempts=3)  # new rule
    )
    merged = base.merge(override)

    assert merged.rule_for("bash").max_attempts == 5  # override wins
    assert merged.rule_for("glob_search").action == "skip"  # kept
    assert merged.rule_for("web_fetch").action == "retry"  # added


# ======================================================================
# Layer 4: Observability — EventBus + Tape + Hooks + Renderer
# ======================================================================


def test_event_bus_backbone():
    """EventBus as the single observer backbone."""
    bus = H.event_bus(max_buffer=100)
    events = []

    # Subscribe by kind
    bus.on("tool_call_start", lambda e: events.append(("start", e.tool_name)))
    bus.on("tool_call_end", lambda e: events.append(("end", e.tool_name)))

    # Emit events (as ADK callbacks would)
    bus.emit(ToolCallStart(tool_name="read_file", args={"path": "main.py"}))
    bus.emit(ToolCallEnd(tool_name="read_file", result="...", duration_ms=42.0))

    assert events == [("start", "read_file"), ("end", "read_file")]
    assert len(bus.buffer) == 2  # buffered for late subscribers


def test_event_bus_error_isolation():
    """One failing subscriber never blocks others."""
    bus = H.event_bus()
    results = []

    def bad_handler(e):
        raise RuntimeError("observer crashed")

    def good_handler(e):
        results.append(e.tool_name)

    bus.on("tool_call_start", bad_handler)
    bus.on("tool_call_start", good_handler)

    # Good handler runs despite bad handler crashing
    bus.emit(ToolCallStart(tool_name="bash"))
    assert results == ["bash"]


def test_session_tape():
    """Record all events to a replayable tape."""
    bus = H.event_bus()
    tape = bus.tape(max_events=1000)

    bus.emit(ToolCallStart(tool_name="read_file"))
    bus.emit(ToolCallEnd(tool_name="read_file", duration_ms=15.0))
    bus.emit(UsageUpdate(input_tokens=1000, output_tokens=500))

    assert tape.size == 3
    assert tape.events[0]["kind"] == "tool_call_start"
    assert tape.events[2]["kind"] == "usage_update"


def test_hooks_integration():
    """User-defined hooks fire on events."""
    with tempfile.TemporaryDirectory() as project:
        hooks = (
            H.hooks(project)
            .on_edit("echo 'linting {file_path}'")
            .on_error("echo 'error: {error}'")
            .on("turn_complete", "echo 'turn done'")
        )
        # Hooks registered by trigger
        assert len(hooks.registered_events) >= 3


def test_renderer():
    """Event renderer converts events to display strings."""
    renderer = H.renderer("plain", show_timing=True, show_args=True)

    text = renderer.render(
        ToolCallStart(
            tool_name="edit_file",
            args={"path": "main.py"},
        )
    )
    assert "edit_file" in text

    text = renderer.render(
        ToolCallEnd(
            tool_name="edit_file",
            duration_ms=150.0,
        )
    )
    assert "edit_file" in text
    assert "150" in text


def test_bus_wires_everything():
    """EventBus composes with ToolPolicy, BudgetMonitor, and TaskLedger."""
    bus = H.event_bus()
    errors = []
    bus.on("error", lambda e: errors.append(e))

    # ToolPolicy emits errors through the bus
    policy = H.tool_policy().retry("bash", max_attempts=1).with_bus(bus)
    assert policy._event_bus is bus

    # BudgetMonitor emits compression triggers through the bus
    monitor = H.budget_monitor(100).with_bus(bus)
    assert monitor._event_bus is bus

    # TaskLedger emits lifecycle events through the bus
    ledger = H.task_ledger().with_bus(bus)
    assert ledger._event_bus is bus


# ======================================================================
# Layer 5: Runtime — REPL + Commands + Interrupt + Tasks
# ======================================================================


def test_slash_commands():
    """Slash command registry for the REPL."""
    state = {"model": "gemini-2.5-pro", "context_cleared": False}

    cmds = H.commands()
    cmds.register(
        "model",
        lambda args: f"Model: {args}" if args else f"Current: {state['model']}",
        description="Show or switch model",
    )
    cmds.register(
        "clear",
        lambda args: "Context cleared.",
        description="Clear conversation context",
    )
    cmds.register(
        "compact",
        lambda args: "Context compacted.",
        description="Compress context to save tokens",
    )
    cmds.register(
        "help",
        lambda args: cmds.help_text(),
        description="Show available commands",
    )

    assert cmds.is_command("/model")
    assert cmds.dispatch("/model gemini-2.5-flash") == "Model: gemini-2.5-flash"
    assert cmds.dispatch("/clear") == "Context cleared."
    assert "Unknown command" in cmds.dispatch("/nonexistent")

    help_text = cmds.dispatch("/help")
    assert "/model" in help_text
    assert "/clear" in help_text


def test_cancellation_token():
    """Cooperative interrupt and resume."""
    token = H.cancellation_token()
    assert not token.is_cancelled

    # Simulate a turn
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

    # Resume prompt includes context
    resume = snapshot.resume_prompt()
    assert "Resuming" in resume
    assert "read_file" in resume
    assert "grep_search" in resume

    # Reset for next turn
    token.reset()
    assert not token.is_cancelled


def test_cancellation_callback():
    """Before-tool callback blocks tools when cancelled."""
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


def test_task_ledger():
    """LLM-callable task management tools."""
    bus = H.event_bus()
    events = []
    bus.on("task_event", lambda e: events.append(e))

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


def test_git_checkpoint():
    """Git checkpointer for undo support."""
    with tempfile.TemporaryDirectory() as project:
        cp = H.git(project)
        # GitCheckpointer wraps git stash/tag operations
        assert cp is not None
        assert hasattr(cp, "create")
        assert hasattr(cp, "restore")


def test_repl_config():
    """REPL configuration for the runtime loop."""
    config = ReplConfig(
        prompt_prefix="coder> ",
        welcome_message="Ready. Type /help for commands.",
        max_turns=100,
        auto_checkpoint=True,
    )
    assert config.prompt_prefix == "coder> "
    assert "/exit" in config.exit_commands


def test_context_compressor():
    """Auto-compression when context exceeds threshold."""
    compressor = H.compressor(threshold=100_000)
    assert compressor.should_compress(150_000) is True
    assert compressor.should_compress(50_000) is False


# ======================================================================
# Full Assembly: The Complete Coding Agent
# ======================================================================


def test_full_coding_agent():
    """Complete Claude-Code-class harness — all 5 layers wired together.

    This is the proof that adk-fluent can build a production coding
    runtime. Every component is a real, tested building block.
    """
    with tempfile.TemporaryDirectory() as project:
        # Create test files
        with open(os.path.join(project, "main.py"), "w") as f:
            f.write("def greet(name):\n    return f'Hello, {name}!'\n")
        with open(os.path.join(project, "test_main.py"), "w") as f:
            f.write("from main import greet\n\ndef test_greet():\n    assert greet('World') == 'Hello, World!'\n")

        # --- EventBus backbone ---
        bus = H.event_bus(max_buffer=1000)
        tape = bus.tape()  # noqa: F841 — tape records in background

        # --- Layer 1: Intelligence ---
        agent = (
            Agent("coder", "gemini-2.5-pro")
            .use_skill("examples/skills/code_reviewer/")
            .instruct(
                "You are an expert coding assistant. You can read files, "
                "edit code, run tests, and manage background tasks. "
                "Always verify changes by running tests."
            )
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
                .merge(H.ask_before("edit_file", "diff_edit_file", "apply_edit", "write_file", "bash"))
                .merge(H.deny("rm_rf"))
            ),
            sandbox=H.workspace_only(project),
            memory=H.memory(f"{project}/.agent-memory.md"),
            on_error=H.on_error(retry={"bash", "web_fetch"}, skip={"glob_search"}),
        )

        # --- Layer 4: Observability ---
        token = H.cancellation_token()
        monitor = (
            H.budget_monitor(200_000)
            .on_threshold(0.7, lambda m: None)  # warn handler
            .on_threshold(0.9, lambda m: None)  # compress handler
            .with_bus(bus)
        )
        policy = (
            H.tool_policy()
            .retry("bash", max_attempts=3, backoff=1.0)
            .retry("web_fetch", max_attempts=2, backoff=0.5)
            .skip("glob_search", fallback="No matching files found.")
            .with_bus(bus)
        )
        hooks = H.hooks(project).on_edit("echo 'lint {file_path}'").on_error("echo 'error: {error}'")
        bus.hooks(hooks)

        agent = (
            agent.before_tool(bus.before_tool_hook())
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
        cmds.register("compact", lambda a: "Compacted.", description="Compress context")
        cmds.register("undo", lambda a: "Undone.", description="Undo last change")
        cmds.register("help", lambda a: cmds.help_text(), description="Show commands")

        built = agent.build()

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
        assert isinstance(repl, HarnessRepl)
        assert repl.config.prompt_prefix == "coder> "


# ======================================================================
# Manifold: Runtime Capability Discovery (Bonus Layer)
# ======================================================================


def test_manifold_discovery():
    """Two-phase capability discovery — the 100+ tool solution.

    When you have 100+ tools but the LLM can only handle ~30 at once,
    the manifold lets the LLM discover and load what it needs.
    """

    def search_code(query: str) -> str:
        """Search codebase for a pattern."""
        return f"Results for: {query}"

    def run_tests(path: str = ".") -> str:
        """Run the test suite."""
        return "All tests passed."

    def deploy(env: str = "staging") -> str:
        """Deploy to the specified environment."""
        return f"Deployed to {env}."

    # Build a manifold from tools + skills
    manifold = H.manifold(
        tools=None,  # Would normally be a ToolRegistry
        skills="examples/skills/",
        always_loaded=["search_code"],
        max_tools=30,
    )

    # The manifold provides meta-tools for discovery
    # (search_capabilities, load_capability, finalize_capabilities)
    assert manifold is not None

    # Direct API for testing
    result = manifold.search("code review")
    assert isinstance(result, str)


# ======================================================================
# Composition Proof: Foundation Primitives Working Together
# ======================================================================


def test_foundations_compose():
    """All four foundation primitives compose through EventBus.

    EventBus is the backbone. ToolPolicy, BudgetMonitor, and TaskLedger
    all emit events through it. One subscription point, one observation
    layer, zero duplication.
    """
    bus = H.event_bus(max_buffer=100)
    all_events = []
    bus.subscribe(lambda e: all_events.append(e.kind))

    # ToolPolicy → emits errors
    _policy = H.tool_policy().retry("bash").with_bus(bus)  # noqa: F841

    # BudgetMonitor → emits compression triggers
    monitor = H.budget_monitor(100).on_threshold(0.9, lambda m: None).with_bus(bus)

    # TaskLedger → emits task lifecycle
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
