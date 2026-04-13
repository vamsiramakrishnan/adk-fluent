"""Skill-Powered Harness — Building a CodAct Coding Agent

Demonstrates a coding assistant with skills, workspace tools, and permissions.

Converted from cookbook example: 78_harness_and_skills.py

Usage:
    cd examples
    adk web harness_and_skills
    adk run harness_and_skills
"""

import os

from dotenv import load_dotenv

from adk_fluent import Agent, H
from adk_fluent._context import C

load_dotenv()

PROJECT_ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", ".."))

root_agent = (
    Agent("coder", "gemini-2.5-flash")
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
        "src/adk_fluent/_base.py (core builder), src/adk_fluent/_harness/ (H namespace)."
    )
    .context(C.rolling(n=20))
    .tools(H.workspace(PROJECT_ROOT))
    .harness(
        permissions=(
            H.auto_allow("read_file", "glob_search", "grep_search", "list_dir").merge(
                H.ask_before("edit_file", "write_file", "bash")
            )
        ),
        sandbox=H.workspace_only(PROJECT_ROOT),
    )
    .build()
)
