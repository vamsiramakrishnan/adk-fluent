"""CompressionStrategy — describe how to compress a message list.

The strategy is a frozen configuration value. It does not *do* the
compression — :class:`ContextCompressor` consumes a strategy and produces
the compressed message list. Separating them keeps the policy pure and
lets you swap strategies at runtime without rebuilding the compressor.

Three built-in methods:

- ``drop_old`` — drop oldest messages, keep the last ``keep_turns``
  turn-pairs plus any system messages.
- ``keep_recent`` — alias for ``drop_old`` that reads more naturally
  when the intent is "keep the last N".
- ``summarize`` — feed older messages to a summariser callable and
  replace them with a single system-level summary message.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["CompressionStrategy"]


@dataclass(frozen=True, slots=True)
class CompressionStrategy:
    """Frozen description of a compression method.

    Attributes:
        method: One of ``"drop_old"``, ``"keep_recent"``, ``"summarize"``.
        keep_turns: Number of recent turn-pairs to retain verbatim.
        keep_system: Always keep ``role == "system"`` messages.
        summary_model: Model hint for the ``summarize`` method. Consumed
            by the summariser callable; the compressor itself does not
            read it.
    """

    method: str
    keep_turns: int = 10
    keep_system: bool = True
    summary_model: str | None = None

    @staticmethod
    def drop_old(keep_turns: int = 5) -> CompressionStrategy:
        """Drop oldest turns, keeping the most recent ``keep_turns``."""
        return CompressionStrategy(method="drop_old", keep_turns=keep_turns)

    @staticmethod
    def keep_recent(n: int = 10) -> CompressionStrategy:
        """Keep only the last ``n`` turn-pairs."""
        return CompressionStrategy(method="keep_recent", keep_turns=n)

    @staticmethod
    def summarize(model: str = "gemini-2.5-flash") -> CompressionStrategy:
        """Summarise old turns using an LLM.

        The compressor will call the summariser callable with the old
        message block and insert the returned summary as a single
        system-level message.
        """
        return CompressionStrategy(method="summarize", summary_model=model)
