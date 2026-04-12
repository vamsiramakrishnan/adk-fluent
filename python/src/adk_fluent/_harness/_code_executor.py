"""Polyglot code executor — run snippets of Python, Node, TypeScript, or
Bash inside a :class:`SandboxPolicy`. Mirrors the TypeScript
``CodeExecutor`` in ``ts/src/namespaces/harness/code-executor.ts``.

The runner is the missing primitive that turns the harness into a
"Claude Code" style agent loop: rather than ask the model to author whole
files for every task, hand it a small ``run_code`` tool and let it batch
primitive operations in its native language.

Design goals
------------
* **Polyglot** — one tool surface for python/node/ts/bash. The harness
  author doesn't have to author four different tool wrappers.
* **Sandboxed** — every spawn inherits ``sandbox.workspace`` as cwd and
  refuses to start if ``sandbox.allow_shell`` is false.
* **Stateless** — no persistent REPL state across calls (this is *not*
  Jupyter). For session-scoped state the agent should write to a file.
* **Tool-shaped** — :meth:`CodeExecutor.tools` returns LLM-callable
  ``run_code`` and ``which_languages`` functions ready for ``T.fn(...)``.

The Python implementation deliberately uses ``subprocess.run`` (not
``asyncio.create_subprocess_exec``) to keep the surface synchronous —
ADK ``FunctionTool`` wrapping is friendlier with sync callables and the
extra concurrency from async barely matters for code-execution tools
since they're naturally serialized by the LLM event loop anyway.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from adk_fluent._harness._sandbox import SandboxPolicy

__all__ = ["CodeExecutor", "CodeRunResult", "CodeLanguage"]

CodeLanguage = Literal["python", "node", "typescript", "bash", "shell"]

_DEFAULT_INTERPRETERS: dict[str, list[str]] = {
    "python": ["python3"],
    "node": ["node"],
    # tsx is the standard "run a .ts file" runner. Defaults to npx-loaded
    # so common installs work out of the box.
    "typescript": ["npx", "-y", "tsx"],
    "bash": ["bash"],
    "shell": ["bash"],
}


@dataclass
class CodeRunResult:
    """Captured output from a single ``CodeExecutor.run`` call."""

    language: str
    stdout: str
    stderr: str
    exit_code: int
    truncated: bool
    duration_ms: int


@dataclass
class CodeExecutor:
    """Polyglot code runner.

    Parameters
    ----------
    sandbox
        Required :class:`SandboxPolicy`. Provides ``workspace`` (cwd),
        ``allow_shell`` (kill switch), and ``max_output_bytes`` (capture
        cap).
    interpreters
        Optional override map. Each value can be a single binary name
        (``"python3.12"``) or a full argv prefix
        (``["uv", "run", "python"]``). Missing entries fall back to the
        defaults in :data:`_DEFAULT_INTERPRETERS`.
    default_timeout_ms
        Wall clock for any ``run`` call that doesn't override
        ``timeout_ms``. Defaults to 60 s.
    disable
        Languages to forbid even when their interpreter is on $PATH.
    """

    sandbox: SandboxPolicy
    interpreters: dict[str, list[str]] = field(default_factory=dict)
    default_timeout_ms: int = 60_000
    disable: frozenset[str] = field(default_factory=frozenset)
    _detected: dict[str, bool] | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        merged: dict[str, list[str]] = dict(_DEFAULT_INTERPRETERS)
        for lang, bin_ in self.interpreters.items():
            merged[lang] = bin_ if isinstance(bin_, list) else [bin_]
        self.interpreters = merged

    # ─── core API ────────────────────────────────────────────────────────

    def run(
        self,
        language: CodeLanguage,
        source: str,
        *,
        timeout_ms: int | None = None,
        stdin: str | None = None,
    ) -> CodeRunResult:
        """Run ``source`` under the chosen language interpreter."""
        if not self.sandbox.allow_shell:
            raise RuntimeError(f"CodeExecutor: sandbox forbids shell — cannot run {language}")
        if language in self.disable:
            raise RuntimeError(f"CodeExecutor: language '{language}' is disabled")
        argv = self.interpreters.get(language)
        if not argv:
            raise RuntimeError(f"CodeExecutor: unknown language '{language}'")

        cwd = self.sandbox.workspace or os.getcwd()
        timeout_s = (timeout_ms or self.default_timeout_ms) / 1000.0
        cap = self.sandbox.max_output_bytes
        started = time.monotonic()

        cmd, cleanup = self._materialize(language, argv, source)
        try:
            proc = subprocess.run(  # noqa: S603 — sandboxed cwd
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                input=stdin,
                timeout=timeout_s,
                check=False,
            )
            stdout = proc.stdout
            stderr = proc.stderr
            exit_code = proc.returncode
            killed = False
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = (exc.stderr or "") + f"\n[killed after {int(timeout_s * 1000)}ms]"
            exit_code = -1
            killed = True
        finally:
            if cleanup is not None:
                with contextlib.suppress(OSError):
                    cleanup()

        truncated = False
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf8", errors="replace")
        if len(stdout) > cap:
            stdout = stdout[:cap]
            truncated = True
        if len(stderr) > cap:
            stderr = stderr[:cap]
            truncated = True

        return CodeRunResult(
            language=language,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code if not killed else -1,
            truncated=truncated,
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    def detect(self) -> dict[str, bool]:
        """Return ``{language: bool}`` showing which interpreters resolve."""
        if self._detected is not None:
            return self._detected
        out: dict[str, bool] = {}
        for lang, argv in self.interpreters.items():
            if lang in self.disable:
                out[lang] = False
                continue
            out[lang] = shutil.which(argv[0]) is not None
        self._detected = out
        return out

    # ─── tool factory ────────────────────────────────────────────────────

    def tools(self) -> list[Callable]:
        """Return LLM-callable tools for ``run_code`` and ``which_languages``."""
        executor = self  # capture for closure

        def run_code(language: str, source: str, timeout_ms: int = 60_000) -> dict:
            """Run a snippet of code in the chosen language.

            Args:
                language: One of ``python``, ``node``, ``typescript``, ``bash``.
                source: Source code to run as-is. No shell escaping needed.
                timeout_ms: Hard wall clock in milliseconds (default 60s).
            """
            r = executor.run(language, source, timeout_ms=timeout_ms)  # type: ignore[arg-type]
            return {
                "stdout": r.stdout,
                "stderr": r.stderr,
                "exit_code": r.exit_code,
                "truncated": r.truncated,
                "duration_ms": r.duration_ms,
            }

        def which_languages() -> dict:
            """Probe which language interpreters are available on this host."""
            return executor.detect()

        run_code.__name__ = "run_code"
        which_languages.__name__ = "which_languages"
        return [run_code, which_languages]

    # ─── interpreter materialization ─────────────────────────────────────

    def _materialize(self, language: str, argv: list[str], source: str) -> tuple[list[str], Callable[[], None] | None]:
        if language == "python":
            return [*argv, "-c", source], None
        if language == "node":
            return [*argv, "-e", source], None
        if language in ("bash", "shell"):
            return [*argv, "-c", source], None
        if language == "typescript":
            tmp_dir = Path(tempfile.mkdtemp(prefix="harness-tsx-"))
            tmp_file = tmp_dir / "snippet.ts"
            tmp_file.write_text(source, encoding="utf8")

            def cleanup() -> None:
                try:
                    tmp_file.unlink(missing_ok=True)
                    tmp_dir.rmdir()
                except OSError:
                    pass

            return [*argv, str(tmp_file)], cleanup
        raise RuntimeError(f"CodeExecutor: unsupported language '{language}'")
