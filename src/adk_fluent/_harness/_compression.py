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
from dataclasses import dataclass, field
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
            # summarize falls back to keep_recent (LLM call would need async)
            return self._keep_recent(messages, strategy.keep_turns)

    @property
    def compression_count(self) -> int:
        """Number of times compression has been triggered."""
        return self._compression_count

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
