"""Process manager — lifecycle management for background processes.

Claude Code can start servers, builds, and other long-running processes
in the background and check on them later. This module provides a
registry of named processes with lifecycle tools::

    proc_tools = H.processes()  # [start_process, check_process, stop_process]

    agent = Agent("coder").tools(H.workspace("/project") + proc_tools)
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass

from adk_fluent._harness._sandbox import SandboxPolicy

__all__ = ["ProcessRegistry", "make_process_tools", "process_tools"]


@dataclass
class _ProcessInfo:
    """Metadata for a managed process."""

    name: str
    command: str
    proc: subprocess.Popen[str]
    output_buffer: list[str]


class ProcessRegistry:
    """Registry of named background processes.

    Tracks running processes by name and provides start/check/stop
    operations. Processes are non-blocking.

    Args:
        sandbox: Sandbox policy (checks allow_shell, provides cwd).
        max_output_lines: Maximum lines buffered per process.
    """

    def __init__(self, sandbox: SandboxPolicy, *, max_output_lines: int = 200) -> None:
        self.sandbox = sandbox
        self.max_output_lines = max_output_lines
        self._processes: dict[str, _ProcessInfo] = {}

    def start(self, name: str, command: str) -> str:
        """Start a named background process.

        Args:
            name: Unique name for the process.
            command: Shell command to execute.

        Returns:
            Status message.
        """
        if not self.sandbox.allow_shell:
            return "Error: shell execution is disabled by sandbox policy."

        if name in self._processes:
            info = self._processes[name]
            if info.proc.poll() is None:
                return f"Error: process '{name}' is already running (PID {info.proc.pid})."
            # Previous process has ended — clean up
            del self._processes[name]

        cwd = self.sandbox.workspace or None
        try:
            proc = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=cwd,
            )
            self._processes[name] = _ProcessInfo(
                name=name,
                command=command,
                proc=proc,
                output_buffer=[],
            )
            return f"Started process '{name}' (PID {proc.pid}): {command}"
        except Exception as e:
            return f"Error starting process: {e}"

    def check(self, name: str) -> str:
        """Check status and recent output of a named process.

        Args:
            name: Process name.

        Returns:
            Status and recent output lines.
        """
        info = self._processes.get(name)
        if info is None:
            return f"Error: no process named '{name}'. Active: {', '.join(self._processes) or 'none'}"

        # Read any available output (non-blocking)
        self._drain_output(info)

        poll = info.proc.poll()
        status = "running" if poll is None else f"exited (code {poll})"
        recent = info.output_buffer[-20:]  # Last 20 lines
        output = "\n".join(recent) if recent else "(no output yet)"
        return f"Process '{name}' [{status}]:\n{output}"

    def stop(self, name: str) -> str:
        """Stop a named process.

        Args:
            name: Process name.

        Returns:
            Status message.
        """
        info = self._processes.get(name)
        if info is None:
            return f"Error: no process named '{name}'."

        if info.proc.poll() is not None:
            self._drain_output(info)
            del self._processes[name]
            return f"Process '{name}' already exited (code {info.proc.returncode})."

        try:
            info.proc.terminate()
            try:
                info.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                info.proc.kill()
                info.proc.wait(timeout=5)
            self._drain_output(info)
            del self._processes[name]
            return f"Stopped process '{name}'."
        except Exception as e:
            return f"Error stopping process: {e}"

    def list_processes(self) -> str:
        """List all managed processes."""
        if not self._processes:
            return "No active processes."
        lines = []
        for name, info in self._processes.items():
            poll = info.proc.poll()
            status = "running" if poll is None else f"exited ({poll})"
            lines.append(f"  {name}: {status} — {info.command}")
        return "Active processes:\n" + "\n".join(lines)

    def cleanup(self) -> None:
        """Stop all running processes. Call on agent teardown."""
        for info in list(self._processes.values()):
            if info.proc.poll() is None:
                info.proc.terminate()
                try:
                    info.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    info.proc.kill()
        self._processes.clear()

    def _drain_output(self, info: _ProcessInfo) -> None:
        """Read available output from process stdout (non-blocking)."""
        stdout = info.proc.stdout
        if stdout is None:
            return
        import select

        try:
            while select.select([stdout], [], [], 0.0)[0]:
                line = stdout.readline()
                if not line:
                    break
                info.output_buffer.append(line.rstrip())
                if len(info.output_buffer) > self.max_output_lines:
                    info.output_buffer = info.output_buffer[-self.max_output_lines :]
        except (ValueError, OSError):
            pass


def make_process_tools(registry: ProcessRegistry) -> tuple[Callable, Callable, Callable]:
    """Create tool closures over a ProcessRegistry.

    Returns:
        Tuple of (start_process, check_process, stop_process) functions.
    """

    def start_process(name: str, command: str) -> str:
        """Start a named background process (non-blocking).

        The process runs in the background. Use ``check_process`` to
        see its status and output, and ``stop_process`` to terminate it.

        Args:
            name: Unique name for the process (e.g., "dev_server").
            command: Shell command to execute (e.g., "npm run dev").
        """
        return registry.start(name, command)

    def check_process(name: str) -> str:
        """Check the status and recent output of a background process.

        Args:
            name: Process name given to start_process.
        """
        return registry.check(name)

    def stop_process(name: str) -> str:
        """Stop a running background process.

        Args:
            name: Process name given to start_process.
        """
        return registry.stop(name)

    return start_process, check_process, stop_process


def process_tools(sandbox: SandboxPolicy) -> list[Callable]:
    """Create the process management tool set.

    Args:
        sandbox: Sandbox policy (checks allow_shell, provides cwd).

    Returns:
        List of [start_process, check_process, stop_process] tools.
    """
    registry = ProcessRegistry(sandbox)
    start, check, stop = make_process_tools(registry)
    return [start, check, stop]
