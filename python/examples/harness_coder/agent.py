"""Harness Coder — a live coding agent for the adk-fluent repo.

Uses the H namespace harness primitives to build a sandboxed coding
assistant with skills, permissions, and workspace tools.

Usage:
    cd examples
    adk web harness_coder
"""

import os

from dotenv import load_dotenv

from adk_fluent import Agent, H
from adk_fluent._context import C

load_dotenv()

# Point at the adk-fluent repo root
PROJECT_ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", ".."))

agent = (
    Agent("coder", "gemini-2.5-flash")
    # Domain expertise from skills (cached in static_instruction)
    .use_skill("examples/skills/code_reviewer/")
    # Per-task instruction
    .instruct(
        "You are an expert coding assistant working on the adk-fluent project. "
        "This is a fluent builder API for Google's Agent Development Kit (ADK). "
        "You can read files, search the codebase, edit code, and run commands. "
        "Always read relevant files before making changes. "
        "Run tests after edits to verify correctness: uv run pytest tests/ -x --tb=short -q"
    )
    # Rolling context window so long sessions don't blow up
    .context(C.rolling(n=20))
    # Sandboxed workspace tools
    .tools(H.workspace(PROJECT_ROOT))
    # Safety: read tools auto-allowed, write tools need approval
    .harness(
        permissions=(
            H.auto_allow("read_file", "glob_search", "grep_search", "list_dir").merge(
                H.ask_before("edit_file", "write_file", "bash")
            )
        ),
        sandbox=H.workspace_only(PROJECT_ROOT),
    )
)

root_agent = agent.build()
