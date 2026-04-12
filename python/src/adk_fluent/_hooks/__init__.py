"""adk_fluent._hooks — unified hook foundation.

This package provides the session-scoped, subagent-inherited hook layer that
the harness ``H`` namespace builds on. The four core pieces are:

- :class:`HookEvent` / :class:`HookContext` — event taxonomy and normalized
  context passed to every hook callable.
- :class:`HookDecision` — structured return protocol (allow / deny / modify /
  replace / ask / inject).
- :class:`HookMatcher` — event + tool-name regex + arg-glob filter.
- :class:`SystemMessageChannel` — transient system-message queue drained
  before every LLM call.
- :class:`HookRegistry` — user-facing registry of hook callables and shell
  commands; produces a :class:`HookPlugin` for installation onto
  ``App`` / ``Runner``.
- :class:`HookPlugin` — ADK ``BasePlugin`` subclass that dispatches registry
  entries to ADK's 12 plugin callbacks.

Most users interact with the foundation indirectly via ``H.hooks()``. Import
symbols from this package directly when building harness extensions.
"""

from adk_fluent._hooks._channel import (
    SYSTEM_MESSAGE_STATE_KEY,
    SystemMessageChannel,
)
from adk_fluent._hooks._decision import HookAction, HookDecision
from adk_fluent._hooks._events import ALL_EVENTS, HookContext, HookEvent
from adk_fluent._hooks._matcher import HookMatcher
from adk_fluent._hooks._plugin import HookPlugin
from adk_fluent._hooks._registry import HookEntry, HookRegistry

__all__ = [
    "ALL_EVENTS",
    "HookAction",
    "HookContext",
    "HookDecision",
    "HookEntry",
    "HookEvent",
    "HookMatcher",
    "HookPlugin",
    "HookRegistry",
    "SYSTEM_MESSAGE_STATE_KEY",
    "SystemMessageChannel",
]
