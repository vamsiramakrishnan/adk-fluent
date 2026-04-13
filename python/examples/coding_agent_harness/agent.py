"""Gemini CLI / Claude Code Clone — Production Coding Agent Harness

Full 5-layer coding agent with skills, workspace, web, git, processes,
permissions, budget monitoring, event bus, and task management.

Converted from cookbook example: 79_coding_agent_harness.py

Usage:
    cd examples
    adk web coding_agent_harness
    adk run coding_agent_harness
"""

import os

from dotenv import load_dotenv

from adk_fluent import Agent, H
from adk_fluent._context import C
from adk_fluent._harness._interrupt import make_cancellation_callback

load_dotenv()

PROJECT_ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", ".."))

# --- Layer 4: Observability ---
bus = H.event_bus(max_buffer=1000)
tape = bus.tape()

token = H.cancellation_token()
monitor = (
    H.budget_monitor(200_000)
    .on_threshold(0.7, lambda m: None)
    .on_threshold(0.9, lambda m: None)
    .with_bus(bus)
)
policy = (
    H.tool_policy()
    .retry("bash", max_attempts=3, backoff=1.0)
    .retry("web_fetch", max_attempts=2, backoff=0.5)
    .skip("glob_search", fallback="No matching files found.")
    .with_bus(bus)
)

# --- Layer 5: Runtime ---
ledger = H.task_ledger().with_bus(bus)

root_agent = (
    Agent("coder", "gemini-2.5-pro")
    # Layer 1: Intelligence
    .use_skill("examples/skills/code_reviewer/")
    .instruct(
        "You are a coding assistant for the adk-fluent project. "
        "This is a Python library — explore it using your tools.\n\n"
        "When asked about any concept, namespace, class, or feature:\n"
        "1. Start by reading CLAUDE.md at the workspace root — it has the full API reference.\n"
        "2. Use grep_search to find implementations in src/adk_fluent/.\n"
        "3. Read the actual source files to give precise answers.\n"
        "4. Check examples/cookbook/ for usage examples.\n\n"
        "Never say you don't know something — search the codebase first. "
        "Key entry points: CLAUDE.md (API docs), src/adk_fluent/__init__.py (exports), "
        "src/adk_fluent/_base.py (core builder), src/adk_fluent/_harness/ (H namespace).\n\n"
        "After making edits, verify with: uv run pytest tests/ -x --tb=short -q"
    )
    .context(C.rolling(n=20, summarize=True))
    # Layer 2: Tools
    .tools(
        H.workspace(PROJECT_ROOT, diff_mode=True, multimodal=True)
        + H.web()
        + H.git_tools(PROJECT_ROOT)
        + H.processes(PROJECT_ROOT)
        + ledger.tools()
    )
    # Layer 3: Safety
    .harness(
        permissions=(
            H.auto_allow("read_file", "glob_search", "grep_search", "list_dir")
            .merge(H.ask_before("edit_file", "apply_edit", "write_file", "bash"))
            .merge(H.deny("rm_rf"))
        ),
        sandbox=H.workspace_only(PROJECT_ROOT),
        memory=H.memory(os.path.join(PROJECT_ROOT, ".agent-memory.md")),
        on_error=H.on_error(retry={"bash", "web_fetch"}, skip={"glob_search"}),
    )
    # Layer 4: Observability hooks
    .before_tool(bus.before_tool_hook())
    .before_tool(make_cancellation_callback(token))
    .after_tool(bus.after_tool_hook())
    .after_tool(policy.after_tool_hook())
    .after_model(bus.after_model_hook())
    .after_model(monitor.after_model_hook())
    .build()
)
