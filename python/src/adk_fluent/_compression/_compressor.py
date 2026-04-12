"""ContextCompressor — monitor context size and compress on demand.

Real harnesses (Claude Code, Gemini CLI) automatically compress older
conversation history when the context window fills up. This module
provides the trigger mechanism and the compression strategies.

The compressor is deliberately **sync-first** — message rewriting is
CPU-bound and does not need an event loop. The async variant
(:meth:`ContextCompressor.compress_messages_async`) is only there to
accommodate LLM-backed summarisation.

Integration with :mod:`adk_fluent._hooks`: a compressor can be wired
with a :class:`HookRegistry`. When compression runs, the compressor
dispatches a :data:`HookEvent.PRE_COMPACT` event before rewriting
messages. Hook entries can:

- allow (the default) — compression proceeds.
- deny — compression is cancelled and the original messages are returned.
- replace — the hook supplies a custom compressed message list, which
  the compressor uses instead of running its own strategy.
- modify — the hook rewrites the message list in place, after which the
  configured strategy runs on the rewritten input.

This mirrors the Claude Agent SDK's ``PreCompact`` hook surface.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from adk_fluent._compression._strategy import CompressionStrategy

if TYPE_CHECKING:
    from adk_fluent._hooks._registry import HookRegistry

__all__ = ["ContextCompressor"]


class ContextCompressor:
    """Monitor context size and trigger compression when needed.

    Args:
        threshold: Token count threshold to trigger compression.
        strategy: How to compress (default: ``keep_recent(10)``).
        on_compress: Callback fired when compression runs. Receives the
            pre-compression token estimate.
        hook_registry: Optional :class:`HookRegistry` — when set, the
            compressor dispatches a ``pre_compact`` hook event before
            rewriting messages.
    """

    def __init__(
        self,
        threshold: int = 100_000,
        strategy: CompressionStrategy | None = None,
        on_compress: Callable[[int], None] | None = None,
        *,
        hook_registry: HookRegistry | None = None,
    ) -> None:
        self.threshold = threshold
        self.strategy = strategy or CompressionStrategy.keep_recent()
        self.on_compress = on_compress
        self._hook_registry = hook_registry
        self._compression_count = 0

    # ------------------------------------------------------------------
    # Threshold check + token estimation
    # ------------------------------------------------------------------

    def should_compress(self, current_tokens: int) -> bool:
        """Return True if ``current_tokens`` meets or exceeds the threshold."""
        return current_tokens >= self.threshold

    def estimate_tokens(self, messages: list[dict[str, Any]]) -> int:
        """Rough token estimate from a message list.

        Uses a ~4 chars-per-token heuristic. Cheap; for precise counting
        plug in a real tokenizer at the caller.
        """
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += len(content) // 4
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and "text" in part:
                        total += len(part["text"]) // 4
        return total

    # ------------------------------------------------------------------
    # Sync compression
    # ------------------------------------------------------------------

    def compress_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Compress a message list according to the strategy.

        For the ``summarize`` strategy this sync variant falls back to
        ``keep_recent`` because LLM summarisation is async. Use
        :meth:`compress_messages_async` when you need real summaries.

        Fires ``pre_compact`` hooks if a :class:`HookRegistry` is wired.
        The hook can deny, replace, or modify the message list.

        Args:
            messages: List of message dicts with ``role`` and ``content``.

        Returns:
            Compressed message list.
        """
        if not messages:
            return messages

        hook_result = self._run_pre_compact_sync(messages)
        if hook_result is _PreCompactSkip:
            return messages
        if isinstance(hook_result, list):
            return hook_result

        return self._apply_strategy(messages)

    async def compress_messages_async(
        self,
        messages: list[dict[str, Any]],
        *,
        summarizer: Callable[..., Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Async compression with optional LLM summarisation.

        When strategy is ``summarize`` and a ``summarizer`` callable is
        provided, old messages are replaced with a single summary
        message. The summariser receives a plain text block and returns
        a summary string (sync or async).

        Fires ``pre_compact`` hooks before compression runs.

        Args:
            messages: List of message dicts.
            summarizer: Callable ``(text: str) -> str`` (sync or async).

        Returns:
            Compressed message list.
        """
        if not messages:
            return messages

        hook_result = await self._run_pre_compact_async(messages)
        if hook_result is _PreCompactSkip:
            return messages
        if isinstance(hook_result, list):
            return hook_result

        strategy = self.strategy
        if strategy.method != "summarize" or summarizer is None:
            return self._apply_strategy(messages)

        self._compression_count += 1
        if self.on_compress:
            self.on_compress(self.estimate_tokens(messages))

        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]
        keep_count = strategy.keep_turns * 2
        if len(non_system) <= keep_count:
            return messages

        old_msgs = non_system[:-keep_count]
        recent_msgs = non_system[-keep_count:]
        old_text = "\n".join(f"{m.get('role', 'unknown')}: {m.get('content', '')}" for m in old_msgs)

        if asyncio.iscoroutinefunction(summarizer):
            summary = await summarizer(old_text)
        else:
            summary = summarizer(old_text)

        summary_msg = {
            "role": "user",
            "content": f"[Summary of earlier conversation]\n{summary}",
        }
        return system_msgs + [summary_msg] + recent_msgs

    # ------------------------------------------------------------------
    # Pre-compact hook dispatch
    # ------------------------------------------------------------------

    def _run_pre_compact_sync(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]] | None | type:
        if self._hook_registry is None:
            return None
        try:
            return asyncio.run(self._dispatch_pre_compact(messages))
        except RuntimeError:
            # Already inside a loop — skip the hook in sync path.
            return None

    async def _run_pre_compact_async(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]] | None | type:
        if self._hook_registry is None:
            return None
        return await self._dispatch_pre_compact(messages)

    async def _dispatch_pre_compact(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]] | None | type:
        from adk_fluent._hooks._events import HookContext, HookEvent

        registry = self._hook_registry
        if registry is None:
            return None
        ctx = HookContext(
            event=HookEvent.PRE_COMPACT,
            extra={
                "messages": list(messages),
                "token_count": self.estimate_tokens(messages),
                "strategy": self.strategy.method,
            },
        )
        decision = await registry.dispatch(ctx)
        if decision.is_allow:
            return None
        if decision.action == "deny":
            return _PreCompactSkip
        if decision.action == "replace":
            replaced = decision.output
            if isinstance(replaced, list):
                self._compression_count += 1
                if self.on_compress:
                    self.on_compress(self.estimate_tokens(messages))
                return replaced
            return None
        if decision.action == "modify":
            modified = ctx.extra.get("messages")
            if isinstance(modified, list):
                return self._apply_strategy(modified)
            return None
        return None

    # ------------------------------------------------------------------
    # Strategy application
    # ------------------------------------------------------------------

    def _apply_strategy(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        strategy = self.strategy
        self._compression_count += 1
        if self.on_compress:
            self.on_compress(self.estimate_tokens(messages))

        if strategy.method == "drop_old":
            return self._drop_old(messages, strategy.keep_turns)
        if strategy.method == "keep_recent":
            return self._keep_recent(messages, strategy.keep_turns)
        # summarize falls back to keep_recent in sync context
        return self._keep_recent(messages, strategy.keep_turns)

    # ------------------------------------------------------------------
    # Properties & helpers
    # ------------------------------------------------------------------

    @property
    def compression_count(self) -> int:
        """Number of times compression has run."""
        return self._compression_count

    @property
    def hook_registry(self) -> HookRegistry | None:
        """Return the wired hook registry, if any."""
        return self._hook_registry

    def with_hooks(self, registry: HookRegistry) -> ContextCompressor:
        """Return a new compressor wired to ``registry`` (pure)."""
        return ContextCompressor(
            threshold=self.threshold,
            strategy=self.strategy,
            on_compress=self.on_compress,
            hook_registry=registry,
        )

    def to_monitor(self) -> Any:
        """Return a :class:`BudgetMonitor` wired to this compressor.

        Bridges session-level monitoring (``BudgetMonitor``) with
        message-level compression. The monitor fires at 95% of
        ``threshold`` and delegates back to ``on_compress``.
        """
        from adk_fluent._budget import BudgetMonitor

        compressor = self

        def _compress_on_threshold(monitor: Any) -> None:
            if compressor.on_compress:
                compressor.on_compress(monitor.current_tokens)

        monitor = BudgetMonitor(max_tokens=self.threshold)
        monitor.on_threshold(0.95, _compress_on_threshold)
        return monitor

    @staticmethod
    def _drop_old(messages: list[dict[str, Any]], keep: int) -> list[dict[str, Any]]:
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]
        keep_count = keep * 2
        recent = non_system[-keep_count:] if len(non_system) > keep_count else non_system
        return system_msgs + recent

    @staticmethod
    def _keep_recent(messages: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]
        keep_count = n * 2
        recent = non_system[-keep_count:] if len(non_system) > keep_count else non_system
        return system_msgs + recent


class _PreCompactSkip:
    """Sentinel indicating pre_compact hooks cancelled compression."""
