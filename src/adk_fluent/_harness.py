"""Harness namespace (H) — runtime primitives for building AI coding harnesses.

A harness is a CodAct agent runtime: an interactive REPL loop with sandboxed
tools, a permission system, streaming output, and context compression.

The ``H`` namespace provides composable building blocks so that building a
skill-powered coding harness takes ~10 lines instead of thousands::

    from adk_fluent import Agent, H

    harness = (
        Agent("coder", "gemini-2.5-pro")
        .skill("skills/python-best-practices/")
        .tools(H.workspace("/path/to/project"))
        .harness(
            permissions=H.ask_before("bash", "edit"),
            sandbox=H.workspace_only(),
        )
    )

    await harness.repl()

The module provides:

- ``H.workspace(path)`` — sandboxed file/shell tool kit
- ``H.ask_before(*tools)`` / ``H.auto_allow(*tools)`` — permission policies
- ``H.workspace_only()`` — sandbox policy
- ``H.auto_compress(threshold)`` — context compression policy
- ``HarnessConfig`` — unified config for ``.harness()``
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["H", "HarnessConfig", "HarnessEvent", "PermissionPolicy", "SandboxPolicy"]


# ======================================================================
# Events — structured output from the harness runtime
# ======================================================================


@dataclass(frozen=True, slots=True)
class HarnessEvent:
    """Base class for structured harness events."""

    kind: str = ""


@dataclass(frozen=True, slots=True)
class TextChunk(HarnessEvent):
    """A chunk of streamed text from the LLM."""

    text: str = ""
    kind: str = "text"


@dataclass(frozen=True, slots=True)
class ToolCallStart(HarnessEvent):
    """A tool call is about to execute."""

    tool_name: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    kind: str = "tool_call_start"


@dataclass(frozen=True, slots=True)
class ToolCallEnd(HarnessEvent):
    """A tool call has completed."""

    tool_name: str = ""
    result: str = ""
    kind: str = "tool_call_end"


@dataclass(frozen=True, slots=True)
class PermissionRequest(HarnessEvent):
    """The harness is requesting permission to execute a tool."""

    tool_name: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    kind: str = "permission_request"


@dataclass(frozen=True, slots=True)
class TurnComplete(HarnessEvent):
    """The agent turn has completed."""

    response: str = ""
    kind: str = "turn_complete"


# ======================================================================
# Permission policies
# ======================================================================


@dataclass(frozen=True, slots=True)
class PermissionPolicy:
    """Declares which tools need approval and which are auto-allowed.

    Tools not mentioned in either list default to ``ask``.
    """

    ask: frozenset[str] = frozenset()
    allow: frozenset[str] = frozenset()
    deny: frozenset[str] = frozenset()

    def check(self, tool_name: str) -> str:
        """Return ``'allow'``, ``'ask'``, or ``'deny'`` for a tool."""
        if tool_name in self.deny:
            return "deny"
        if tool_name in self.allow:
            return "allow"
        if tool_name in self.ask:
            return "ask"
        # Default: if allow list is non-empty, unlisted tools need asking
        # If allow list is empty and ask list is non-empty, unlisted are allowed
        return "ask"

    def merge(self, other: PermissionPolicy) -> PermissionPolicy:
        """Merge two policies. Deny wins over ask wins over allow."""
        return PermissionPolicy(
            ask=self.ask | other.ask,
            allow=(self.allow | other.allow) - other.ask - other.deny,
            deny=self.deny | other.deny,
        )


# ======================================================================
# Sandbox policies
# ======================================================================


@dataclass(frozen=True, slots=True)
class SandboxPolicy:
    """Filesystem and network constraints for tool execution."""

    workspace: str | None = None
    read_paths: frozenset[str] = frozenset()
    write_paths: frozenset[str] = frozenset()
    allow_network: bool = True
    allow_shell: bool = True
    max_output_bytes: int = 100_000

    def validate_path(self, path: str, *, write: bool = False) -> bool:
        """Check if a path is allowed under this policy."""
        resolved = os.path.realpath(path)
        if self.workspace:
            ws = os.path.realpath(self.workspace)
            if resolved.startswith(ws):
                return True
        allowed = self.write_paths if write else (self.read_paths | self.write_paths)
        return any(resolved.startswith(os.path.realpath(p)) for p in allowed)


# ======================================================================
# Harness config — unified configuration for .harness()
# ======================================================================


@dataclass(slots=True)
class HarnessConfig:
    """Configuration for an agent harness runtime."""

    permissions: PermissionPolicy = field(default_factory=PermissionPolicy)
    sandbox: SandboxPolicy = field(default_factory=SandboxPolicy)
    auto_compress_threshold: int = 100_000
    approval_handler: Callable[[str, dict], bool] | None = None


# ======================================================================
# Workspace tools — sandboxed file/shell tool kit
# ======================================================================


def _make_read_file(sandbox: SandboxPolicy | None = None) -> Callable:
    """Create a sandboxed file-read tool."""

    def read_file(path: str, offset: int = 0, limit: int = 2000) -> str:
        """Read a file with line numbers. Returns up to `limit` lines starting from `offset`.

        Args:
            path: Absolute or workspace-relative file path.
            offset: Line number to start from (0-based).
            limit: Maximum number of lines to return.
        """
        if sandbox and sandbox.workspace and not os.path.isabs(path):
            path = os.path.join(sandbox.workspace, path)
        if sandbox and not sandbox.validate_path(path, write=False):
            return f"Error: path '{path}' is outside the allowed workspace."
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            selected = lines[offset : offset + limit]
            numbered = [f"{offset + i + 1}\t{line}" for i, line in enumerate(selected)]
            return "".join(numbered)
        except FileNotFoundError:
            return f"Error: file not found: {path}"
        except Exception as e:
            return f"Error reading file: {e}"

    return read_file


def _make_edit_file(sandbox: SandboxPolicy | None = None) -> Callable:
    """Create a sandboxed file-edit tool (search-and-replace)."""

    def edit_file(path: str, old_string: str, new_string: str) -> str:
        """Replace an exact string in a file. The old_string must appear exactly once.

        Args:
            path: Absolute or workspace-relative file path.
            old_string: The exact text to find and replace.
            new_string: The replacement text.
        """
        if sandbox and sandbox.workspace and not os.path.isabs(path):
            path = os.path.join(sandbox.workspace, path)
        if sandbox and not sandbox.validate_path(path, write=True):
            return f"Error: path '{path}' is outside the allowed workspace."
        try:
            content = Path(path).read_text(encoding="utf-8")
            count = content.count(old_string)
            if count == 0:
                return f"Error: old_string not found in {path}"
            if count > 1:
                return f"Error: old_string appears {count} times in {path}. Must be unique."
            new_content = content.replace(old_string, new_string, 1)
            Path(path).write_text(new_content, encoding="utf-8")
            return f"Successfully edited {path}"
        except Exception as e:
            return f"Error editing file: {e}"

    return edit_file


def _make_write_file(sandbox: SandboxPolicy | None = None) -> Callable:
    """Create a sandboxed file-write tool."""

    def write_file(path: str, content: str) -> str:
        """Write content to a file, creating it if it doesn't exist.

        Args:
            path: Absolute or workspace-relative file path.
            content: The full file content to write.
        """
        if sandbox and sandbox.workspace and not os.path.isabs(path):
            path = os.path.join(sandbox.workspace, path)
        if sandbox and not sandbox.validate_path(path, write=True):
            return f"Error: path '{path}' is outside the allowed workspace."
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(content, encoding="utf-8")
            return f"Successfully wrote {path}"
        except Exception as e:
            return f"Error writing file: {e}"

    return write_file


def _make_glob_search(sandbox: SandboxPolicy | None = None) -> Callable:
    """Create a workspace-aware glob search tool."""

    def glob_search(pattern: str) -> str:
        """Find files matching a glob pattern in the workspace.

        Args:
            pattern: Glob pattern (e.g., '**/*.py', 'src/**/*.ts').
        """
        root = Path(sandbox.workspace) if sandbox and sandbox.workspace else Path(".")
        matches = sorted(root.glob(pattern))[:100]  # Cap at 100 results
        if not matches:
            return "No files found matching the pattern."
        return "\n".join(str(m.relative_to(root)) for m in matches)

    return glob_search


def _make_grep_search(sandbox: SandboxPolicy | None = None) -> Callable:
    """Create a workspace-aware grep search tool."""

    def grep_search(pattern: str, glob: str = "**/*", max_results: int = 50) -> str:
        """Search file contents for a regex pattern.

        Args:
            pattern: Regular expression to search for.
            glob: File glob to limit search scope (default: all files).
            max_results: Maximum number of matching lines to return.
        """
        import re

        root = Path(sandbox.workspace) if sandbox and sandbox.workspace else Path(".")
        results: list[str] = []
        try:
            regex = re.compile(pattern)
        except re.error as e:
            return f"Invalid regex: {e}"
        for filepath in sorted(root.glob(glob)):
            if not filepath.is_file():
                continue
            try:
                text = filepath.read_text(encoding="utf-8", errors="replace")
                for i, line in enumerate(text.splitlines(), 1):
                    if regex.search(line):
                        rel = filepath.relative_to(root)
                        results.append(f"{rel}:{i}: {line.rstrip()}")
                        if len(results) >= max_results:
                            return "\n".join(results)
            except Exception:
                continue
        if not results:
            return "No matches found."
        return "\n".join(results)

    return grep_search


def _make_bash(sandbox: SandboxPolicy | None = None) -> Callable:
    """Create a sandboxed shell execution tool."""

    def bash(command: str, timeout: int = 120) -> str:
        """Execute a shell command and return its output.

        Args:
            command: The shell command to execute.
            timeout: Maximum execution time in seconds (default: 120).
        """
        if sandbox and not sandbox.allow_shell:
            return "Error: shell execution is disabled by sandbox policy."
        cwd = sandbox.workspace if sandbox and sandbox.workspace else None
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
            )
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"
            if result.returncode != 0:
                output += f"\nExit code: {result.returncode}"
            max_bytes = sandbox.max_output_bytes if sandbox else 100_000
            if len(output) > max_bytes:
                output = output[:max_bytes] + f"\n... (truncated to {max_bytes} bytes)"
            return output or "(no output)"
        except subprocess.TimeoutExpired:
            return f"Error: command timed out after {timeout}s"
        except Exception as e:
            return f"Error executing command: {e}"

    return bash


def _make_list_dir(sandbox: SandboxPolicy | None = None) -> Callable:
    """Create a workspace-aware directory listing tool."""

    def list_dir(path: str = ".") -> str:
        """List files and directories at the given path.

        Args:
            path: Directory path (default: workspace root).
        """
        if sandbox and sandbox.workspace and not os.path.isabs(path):
            path = os.path.join(sandbox.workspace, path)
        if sandbox and not sandbox.validate_path(path, write=False):
            return f"Error: path '{path}' is outside the allowed workspace."
        try:
            entries = sorted(Path(path).iterdir())
            lines = []
            for e in entries[:200]:
                prefix = "d " if e.is_dir() else "f "
                lines.append(f"{prefix}{e.name}")
            return "\n".join(lines) or "(empty directory)"
        except FileNotFoundError:
            return f"Error: directory not found: {path}"
        except Exception as e:
            return f"Error listing directory: {e}"

    return list_dir


# ======================================================================
# Permission callback — wires into .before_tool()
# ======================================================================


def _make_permission_callback(
    policy: PermissionPolicy,
    handler: Callable[[str, dict], bool] | None = None,
) -> Callable:
    """Create a before_tool callback that enforces permission policy.

    The callback inspects the tool name, checks the policy, and either
    allows, denies, or asks the user for approval.
    """

    def permission_check(callback_context: Any, tool: Any, args: dict, tool_context: Any) -> Any | None:
        """Before-tool callback for permission enforcement."""
        tool_name = getattr(tool, "name", str(tool))

        decision = policy.check(tool_name)

        if decision == "allow":
            return None  # Proceed
        if decision == "deny":
            # Return a dict to short-circuit the tool call
            return {"error": f"Tool '{tool_name}' is denied by permission policy."}

        # decision == "ask"
        if handler is not None:
            approved = handler(tool_name, args)
            if not approved:
                return {"error": f"Tool '{tool_name}' was denied by user."}
            return None

        # No handler — default allow (harness without interactive approval)
        return None

    return permission_check


# ======================================================================
# Skill loading — .skill() implementation
# ======================================================================


@dataclass(frozen=True, slots=True)
class SkillSpec:
    """Parsed skill specification for attachment to an agent.

    This is the L1 (expertise) layer: knowledge loaded from a SKILL.md
    file and injected into the agent's instruction context.
    """

    name: str
    description: str
    body: str
    allowed_tools: list[str]
    path: Path | None = None

    @staticmethod
    def from_path(path: str | Path) -> SkillSpec:
        """Parse a SKILL.md file into a SkillSpec."""
        from adk_fluent._skill_parser import parse_skill_file

        sd = parse_skill_file(path)
        return SkillSpec(
            name=sd.name,
            description=sd.description,
            body=sd.body,
            allowed_tools=sd.allowed_tools,
            path=sd.path,
        )


def _compile_skills_to_static(skills: list[SkillSpec]) -> str:
    """Compile a list of SkillSpecs into a single static instruction block.

    Skills map to ``static_instruction`` (cacheable, stable content).
    The agent's ``.instruct()`` remains the per-task instruction.

    Structure::

        <skills>
        <skill name="research-methodology">
        [skill body content]
        </skill>
        <skill name="citation-standards">
        [skill body content]
        </skill>
        </skills>
    """
    if not skills:
        return ""
    parts = ["<skills>"]
    for skill in skills:
        parts.append(f'<skill name="{skill.name}">')
        parts.append(skill.body.strip())
        parts.append("</skill>")
    parts.append("</skills>")
    return "\n".join(parts)


# ======================================================================
# H namespace — public API
# ======================================================================


class H:
    """Harness namespace — runtime primitives for AI coding harnesses.

    Provides composable building blocks for constructing interactive
    agent runtimes with sandboxed tools and permission systems.
    """

    # --- Tool kits ---

    @staticmethod
    def workspace(
        path: str | Path,
        *,
        allow_shell: bool = True,
        allow_network: bool = True,
        read_only: bool = False,
        max_output_bytes: int = 100_000,
    ) -> list[Callable]:
        """Create a sandboxed workspace tool kit.

        Returns a list of tool functions (read, edit, write, glob, grep,
        bash, ls) scoped to the given workspace directory.

        Args:
            path: Root directory for the workspace.
            allow_shell: Enable bash tool (default True).
            allow_network: Allow network access from shell (default True).
            read_only: If True, disable edit/write tools.
            max_output_bytes: Max output from bash commands.

        Usage::

            agent = Agent("coder").tools(H.workspace("/path/to/project"))
        """
        sandbox = SandboxPolicy(
            workspace=str(Path(path).resolve()),
            allow_shell=allow_shell,
            allow_network=allow_network,
            max_output_bytes=max_output_bytes,
        )
        tools: list[Callable] = [
            _make_read_file(sandbox),
            _make_glob_search(sandbox),
            _make_grep_search(sandbox),
            _make_list_dir(sandbox),
        ]
        if not read_only:
            tools.append(_make_edit_file(sandbox))
            tools.append(_make_write_file(sandbox))
        if allow_shell:
            tools.append(_make_bash(sandbox))
        return tools

    # --- Permission policies ---

    @staticmethod
    def ask_before(*tool_names: str) -> PermissionPolicy:
        """Require user approval before running these tools.

        Usage::

            H.ask_before("bash", "edit_file", "write_file")
        """
        return PermissionPolicy(ask=frozenset(tool_names))

    @staticmethod
    def auto_allow(*tool_names: str) -> PermissionPolicy:
        """Auto-approve these tools without asking.

        Usage::

            H.auto_allow("read_file", "glob_search", "grep_search")
        """
        return PermissionPolicy(allow=frozenset(tool_names))

    @staticmethod
    def deny(*tool_names: str) -> PermissionPolicy:
        """Block these tools entirely.

        Usage::

            H.deny("bash")  # No shell access
        """
        return PermissionPolicy(deny=frozenset(tool_names))

    # --- Sandbox policies ---

    @staticmethod
    def workspace_only(path: str | Path | None = None) -> SandboxPolicy:
        """Restrict all file operations to the workspace directory.

        Args:
            path: Workspace root. If None, uses the path from H.workspace().
        """
        return SandboxPolicy(
            workspace=str(Path(path).resolve()) if path else None,
        )

    @staticmethod
    def sandbox(
        *,
        workspace: str | Path | None = None,
        allow_shell: bool = True,
        allow_network: bool = True,
        read_paths: list[str] | None = None,
        write_paths: list[str] | None = None,
    ) -> SandboxPolicy:
        """Create a custom sandbox policy.

        Usage::

            H.sandbox(workspace="/project", allow_shell=False)
        """
        return SandboxPolicy(
            workspace=str(Path(workspace).resolve()) if workspace else None,
            allow_shell=allow_shell,
            allow_network=allow_network,
            read_paths=frozenset(read_paths or []),
            write_paths=frozenset(write_paths or []),
        )

    # --- Compression policies ---

    @staticmethod
    def auto_compress(threshold: int = 100_000) -> int:
        """Set token threshold for automatic context compression.

        When the conversation exceeds this token count, older turns
        are compressed automatically.

        Usage::

            .harness(auto_compress=H.auto_compress(50_000))
        """
        return threshold

    # --- Unified config builder ---

    @staticmethod
    def config(
        *,
        permissions: PermissionPolicy | None = None,
        sandbox: SandboxPolicy | None = None,
        auto_compress_threshold: int = 100_000,
        approval_handler: Callable[[str, dict], bool] | None = None,
    ) -> HarnessConfig:
        """Create a unified harness configuration.

        Usage::

            cfg = H.config(
                permissions=H.ask_before("bash") .merge(H.auto_allow("read_file")),
                sandbox=H.workspace_only("/project"),
            )
        """
        return HarnessConfig(
            permissions=permissions or PermissionPolicy(),
            sandbox=sandbox or SandboxPolicy(),
            auto_compress_threshold=auto_compress_threshold,
            approval_handler=approval_handler,
        )
