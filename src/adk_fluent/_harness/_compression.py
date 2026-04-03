"""Auto-compression — trigger context compaction when approaching limits.

Real harnesses (Claude Code, Gemini CLI) automatically compress older
conversation history when the context window fills up. This module
provides the trigger mechanism and compression strategies::

    compressor = ContextCompressor(threshold=100_000)
    compressor.on_compress = my_callback

    # Check after each turn
    if compressor.should_compress(current_tokens=95_000):
        compressor.compress(session)

Compression strategies:
    - ``drop_old_turns`` — remove oldest turns (simplest)
    - ``summarize_turns`` — LLM-summarize old turns (better)
    - ``keep_recent`` — keep last N turns, drop rest
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

__all__ = ["ContextCompressor", "CompressionStrategy"]


@dataclass(frozen=True, slots=True)
class CompressionStrategy:
    """Defines how context should be compressed."""

    method: str  # "drop_old", "summarize", "keep_recent"
    keep_turns: int = 10  # For keep_recent
    keep_system: bool = True  # Always keep system messages
    summary_model: str | None = None  # For summarize strategy

    @staticmethod
    def drop_old(keep_turns: int = 5) -> CompressionStrategy:
        """Drop oldest turns, keeping the most recent N."""
        return CompressionStrategy(method="drop_old", keep_turns=keep_turns)

    @staticmethod
    def keep_recent(n: int = 10) -> CompressionStrategy:
        """Keep only the last N turn-pairs."""
        return CompressionStrategy(method="keep_recent", keep_turns=n)

    @staticmethod
    def summarize(model: str = "gemini-2.5-flash") -> CompressionStrategy:
        """Summarize old turns using an LLM."""
        return CompressionStrategy(method="summarize", summary_model=model)


class ContextCompressor:
    """Monitors context size and triggers compression when needed.

    Args:
        threshold: Token count threshold to trigger compression.
        strategy: How to compress (default: keep_recent(10)).
        on_compress: Callback when compression is triggered.
    """

    def __init__(
        self,
        threshold: int = 100_000,
        strategy: CompressionStrategy | None = None,
        on_compress: Callable[[int], None] | None = None,
    ) -> None:
        self.threshold = threshold
        self.strategy = strategy or CompressionStrategy.keep_recent()
        self.on_compress = on_compress
        self._compression_count = 0

    def should_compress(self, current_tokens: int) -> bool:
        """Check if compression should be triggered.

        Args:
            current_tokens: Current estimated token count.

        Returns:
            True if tokens exceed threshold.
        """
        return current_tokens >= self.threshold

    def estimate_tokens(self, messages: list[dict[str, Any]]) -> int:
        """Rough token estimate from message list.

        Uses ~4 chars per token heuristic. For precise counting,
        use a tokenizer.
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

    def compress_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Compress a message list according to the strategy.

        For ``summarize`` strategy, use ``compress_messages_async()``
        which can call an LLM. This sync version falls back to
        ``keep_recent`` for ``summarize``.

        Args:
            messages: List of message dicts with 'role' and 'content'.

        Returns:
            Compressed message list.
        """
        if not messages:
            return messages

        strategy = self.strategy
        self._compression_count += 1

        if self.on_compress:
            self.on_compress(self.estimate_tokens(messages))

        if strategy.method == "drop_old":
            return self._drop_old(messages, strategy.keep_turns)
        elif strategy.method == "keep_recent":
            return self._keep_recent(messages, strategy.keep_turns)
        else:
            # summarize falls back to keep_recent in sync context
            return self._keep_recent(messages, strategy.keep_turns)

    async def compress_messages_async(
        self,
        messages: list[dict[str, Any]],
        *,
        summarizer: Callable[..., Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Async compression with LLM summarization support.

        When strategy is ``summarize``, older messages are summarized
        by the ``summarizer`` callable. The summarizer receives a text
        block and returns a summary string.

        Args:
            messages: List of message dicts.
            summarizer: Async callable ``(text: str) -> str`` that
                produces a summary. If None, falls back to keep_recent.

        Returns:
            Compressed message list.
        """
        if not messages:
            return messages

        strategy = self.strategy
        self._compression_count += 1

        if self.on_compress:
            self.on_compress(self.estimate_tokens(messages))

        if strategy.method != "summarize" or summarizer is None:
            return self.compress_messages(messages)

        # Split into system + old + recent
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]

        keep_count = strategy.keep_turns * 2
        if len(non_system) <= keep_count:
            return messages  # nothing to summarize

        old_msgs = non_system[:-keep_count]
        recent_msgs = non_system[-keep_count:]

        # Build text block from old messages
        old_text = "\n".join(f"{m.get('role', 'unknown')}: {m.get('content', '')}" for m in old_msgs)

        # Call summarizer (async)
        import asyncio

        if asyncio.iscoroutinefunction(summarizer):
            summary = await summarizer(old_text)
        else:
            summary = summarizer(old_text)

        # Insert summary as a system-level context message
        summary_msg = {
            "role": "user",
            "content": f"[Summary of earlier conversation]\n{summary}",
        }

        return system_msgs + [summary_msg] + recent_msgs

    @property
    def compression_count(self) -> int:
        """Number of times compression has been triggered."""
        return self._compression_count

    def to_monitor(self) -> Any:
        """Create a ``BudgetMonitor`` wired to this compressor.

        The monitor tracks tokens at the model level and delegates
        compression to this compressor when the threshold is crossed.
        This bridges the gap between session-level monitoring
        (BudgetMonitor) and message-level compression (ContextCompressor).

        Returns:
            A ``BudgetMonitor`` pre-configured with this threshold.
        """
        from adk_fluent._harness._budget_monitor import BudgetMonitor

        compressor = self

        def _compress_on_threshold(monitor: Any) -> None:
            if compressor.on_compress:
                compressor.on_compress(monitor.current_tokens)

        monitor = BudgetMonitor(max_tokens=self.threshold)
        monitor.on_threshold(0.95, _compress_on_threshold)
        return monitor

    @staticmethod
    def _drop_old(messages: list[dict], keep: int) -> list[dict]:
        """Drop oldest messages, keeping system messages and last N."""
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]
        # Keep last `keep` turn-pairs (2 messages per pair)
        keep_count = keep * 2
        recent = non_system[-keep_count:] if len(non_system) > keep_count else non_system
        return system_msgs + recent

    @staticmethod
    def _keep_recent(messages: list[dict], n: int) -> list[dict]:
        """Keep system messages and last N turn-pairs."""
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]
        keep_count = n * 2
        recent = non_system[-keep_count:] if len(non_system) > keep_count else non_system
        return system_msgs + recent
