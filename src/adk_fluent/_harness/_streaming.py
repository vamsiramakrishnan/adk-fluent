"""Streaming bash — PTY-based shell with real-time output.

Unlike the blocking ``bash`` tool that waits for completion, the streaming
bash tool yields output chunks as they arrive. This is essential for
long-running commands (builds, tests, installs) where the LLM or user
needs progressive feedback.

Usage::

    streamer = StreamingBash(sandbox)
    async for chunk in streamer.run("npm test"):
        print(chunk, end="")

    # Or use as a tool that returns full output but streams to a callback
    bash_tool = make_streaming_bash(sandbox, on_output=print)
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable

from adk_fluent._harness._sandbox import SandboxPolicy

__all__ = ["StreamingBash", "make_streaming_bash"]


class StreamingBash:
    """PTY-based streaming shell execution.

    Uses ``asyncio.create_subprocess_shell`` with pipe-based streaming.
    Falls back to blocking subprocess if async loop is not available.
    """

    def __init__(self, sandbox: SandboxPolicy) -> None:
        self.sandbox = sandbox

    async def run(
        self,
        command: str,
        *,
        timeout: int = 120,
        on_output: Callable[[str], None] | None = None,
    ) -> AsyncIterator[str]:
        """Execute a command and yield output chunks as they arrive.

        Args:
            command: Shell command to execute.
            timeout: Maximum execution time in seconds.
            on_output: Optional callback for each output chunk.

        Yields:
            Output chunks as strings.
        """
        if not self.sandbox.allow_shell:
            yield "Error: shell execution is disabled by sandbox policy."
            return

        cwd = self.sandbox.workspace or None
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=cwd,
            )

            total_bytes = 0
            max_bytes = self.sandbox.max_output_bytes

            async def _read_with_timeout():
                try:
                    return await asyncio.wait_for(
                        proc.stdout.read(4096),
                        timeout=timeout,
                    )
                except TimeoutError:
                    proc.kill()
                    return None

            while True:
                data = await _read_with_timeout()
                if data is None:
                    yield f"\nError: command timed out after {timeout}s"
                    break
                if not data:
                    break

                chunk = data.decode("utf-8", errors="replace")
                total_bytes += len(data)

                if total_bytes > max_bytes:
                    yield f"\n... (truncated to {max_bytes} bytes)"
                    proc.kill()
                    break

                if on_output:
                    on_output(chunk)
                yield chunk

            await proc.wait()
            if proc.returncode and proc.returncode != 0:
                yield f"\nExit code: {proc.returncode}"

        except Exception as e:
            yield f"Error executing command: {e}"

    async def run_collected(
        self,
        command: str,
        *,
        timeout: int = 120,
        on_output: Callable[[str], None] | None = None,
    ) -> str:
        """Execute a command and return the full output as a string.

        Like ``run()`` but collects all chunks. If ``on_output`` is provided,
        it also streams chunks to the callback as they arrive.
        """
        parts: list[str] = []
        async for chunk in self.run(command, timeout=timeout, on_output=on_output):
            parts.append(chunk)
        return "".join(parts)


def make_streaming_bash(
    sandbox: SandboxPolicy,
    on_output: Callable[[str], None] | None = None,
) -> Callable:
    """Create a streaming-aware bash tool.

    The tool itself is synchronous (ADK requirement) but internally uses
    async streaming. If an ``on_output`` callback is provided, output
    chunks are streamed to it as they arrive.

    Args:
        sandbox: Sandbox policy.
        on_output: Optional callback for real-time output chunks.
    """
    streamer = StreamingBash(sandbox)

    def bash(command: str, timeout: int = 120) -> str:
        """Execute a shell command with streaming output.

        Args:
            command: The shell command to execute.
            timeout: Maximum execution time in seconds (default: 120).
        """
        if not sandbox.allow_shell:
            return "Error: shell execution is disabled by sandbox policy."

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # We're inside an async context — use a thread
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    asyncio.run,
                    streamer.run_collected(command, timeout=timeout, on_output=on_output),
                )
                return future.result(timeout=timeout + 5)
        else:
            return asyncio.run(streamer.run_collected(command, timeout=timeout, on_output=on_output))

    return bash
