"""adk_fluent._compression — message-level compression with pre_compact hook.

This package is the message-rewriting half of context management.
``C.*`` transforms shape what the LLM sees on a single turn;
:class:`ContextCompressor` rewrites the persistent message history when
it exceeds a threshold.

Pieces:

- :class:`CompressionStrategy` — frozen description of *how* to compress
  (drop_old / keep_recent / summarize).
- :class:`ContextCompressor` — the machine. Threshold check + strategy
  application + optional ``pre_compact`` hook dispatch.

Integration with :mod:`adk_fluent._hooks`: wire a :class:`HookRegistry`
and the compressor fires a ``pre_compact`` event before rewriting
messages. The hook can allow, deny, replace, or modify — mirroring the
Claude Agent SDK's ``PreCompact`` surface.

Users typically construct a compressor via :func:`H.compressor` or pair
it with :class:`BudgetMonitor` via :meth:`ContextCompressor.to_monitor`.
"""

from adk_fluent._compression._compressor import ContextCompressor
from adk_fluent._compression._strategy import CompressionStrategy

__all__ = ["CompressionStrategy", "ContextCompressor"]
