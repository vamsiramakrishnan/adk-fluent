"""Canonical hook event names and HookContext.

A ``HookEvent`` is a string constant identifying WHEN a hook fires. The
taxonomy maps 1:1 onto ADK ``BasePlugin`` callbacks plus a small set of
harness-level extensions.

A ``HookContext`` is a normalized frozen record describing WHAT is happening
when a hook fires. Every hook callable receives exactly one ``HookContext`` —
the plugin layer is responsible for translating each ADK callback's native
argument shape into a ``HookContext`` before dispatch. This keeps user hook
code agnostic to ADK's internal callback signatures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["HookEvent", "HookContext", "ALL_EVENTS"]


class HookEvent:
    """Namespace of canonical hook event names (string constants).

    These are the only valid values for ``HookRegistry.on(event, ...)``.
    Grouped by source:

    - **Tool lifecycle** — ``pre_tool_use``, ``post_tool_use``, ``tool_error``
    - **Model lifecycle** — ``pre_model``, ``post_model``, ``model_error``
    - **Agent lifecycle** — ``pre_agent``, ``post_agent``, ``agent_error``
    - **Session lifecycle** — ``session_start``, ``user_prompt_submit``,
      ``session_end``, ``on_event``
    - **Harness extensions** — ``pre_compact``, ``permission_request``,
      ``notification``
    """

    # Tool lifecycle
    PRE_TOOL_USE: str = "pre_tool_use"
    POST_TOOL_USE: str = "post_tool_use"
    TOOL_ERROR: str = "tool_error"

    # Model lifecycle
    PRE_MODEL: str = "pre_model"
    POST_MODEL: str = "post_model"
    MODEL_ERROR: str = "model_error"

    # Agent lifecycle
    PRE_AGENT: str = "pre_agent"
    POST_AGENT: str = "post_agent"
    AGENT_ERROR: str = "agent_error"

    # Session lifecycle (ADK App/Runner scope)
    SESSION_START: str = "session_start"
    USER_PROMPT_SUBMIT: str = "user_prompt_submit"
    SESSION_END: str = "session_end"
    ON_EVENT: str = "on_event"

    # Harness extensions
    PRE_COMPACT: str = "pre_compact"
    PERMISSION_REQUEST: str = "permission_request"
    NOTIFICATION: str = "notification"


ALL_EVENTS: frozenset[str] = frozenset(
    {
        HookEvent.PRE_TOOL_USE,
        HookEvent.POST_TOOL_USE,
        HookEvent.TOOL_ERROR,
        HookEvent.PRE_MODEL,
        HookEvent.POST_MODEL,
        HookEvent.MODEL_ERROR,
        HookEvent.PRE_AGENT,
        HookEvent.POST_AGENT,
        HookEvent.AGENT_ERROR,
        HookEvent.SESSION_START,
        HookEvent.USER_PROMPT_SUBMIT,
        HookEvent.SESSION_END,
        HookEvent.ON_EVENT,
        HookEvent.PRE_COMPACT,
        HookEvent.PERMISSION_REQUEST,
        HookEvent.NOTIFICATION,
    }
)


@dataclass(slots=True)
class HookContext:
    """Normalized context passed to every hook callable.

    Not every field is populated for every event. Consult the event taxonomy:

    - Tool events populate ``tool_name``, ``tool_input``, and (for post/error)
      ``tool_output`` / ``error``.
    - Model events populate ``model`` and (for post/error) ``response`` / ``error``.
    - Agent events populate ``agent_name`` and (for error) ``error``.
    - Session events populate ``user_message`` for user_prompt_submit.
    - All events populate ``event``, ``session_id``, and ``invocation_id`` when
      they are available from the surrounding ADK invocation context.

    The ``extra`` dict is an escape hatch for event-specific fields that do not
    deserve a top-level slot.
    """

    event: str
    session_id: str | None = None
    invocation_id: str | None = None
    agent_name: str | None = None
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    tool_output: Any = None
    model: str | None = None
    request: Any = None
    response: Any = None
    user_message: str | None = None
    error: BaseException | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Look up ``key`` on the context, falling back to ``extra``."""
        if hasattr(self, key):
            value = getattr(self, key)
            if value is not None:
                return value
        return self.extra.get(key, default)
