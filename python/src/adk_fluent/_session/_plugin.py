"""SessionPlugin — session-scoped ADK plugin that feeds a SessionStore.

ADK ``BasePlugin`` instances live for the duration of a session and are
inherited across every sub-agent in the invocation tree. Wrapping a
:class:`SessionStore` in a plugin therefore gives you
whole-invocation-tree coverage with a single install — no need to
attach per-agent callbacks to every specialist in a coordinator tree.

The plugin hooks ``after_agent_callback`` to auto-fork state into a
uniquely-named branch on every agent completion. Event recording still
happens via ``SessionStore.record_event`` (pass it to
``EventDispatcher.subscribe``); the plugin does not reach into the
event stream directly because harness events flow through a different
surface from ADK plugin callbacks.
"""

from __future__ import annotations

from typing import Any

from google.adk.plugins.base_plugin import BasePlugin

from adk_fluent._session._store import SessionStore

__all__ = ["SessionPlugin"]


class SessionPlugin(BasePlugin):
    """ADK ``BasePlugin`` that wires a :class:`SessionStore` into session lifecycle.

    Args:
        store: The :class:`SessionStore` to feed. A fresh store is
            created if omitted.
        auto_fork: If True (default), create a named branch after every
            agent completion. The branch name is built from
            ``fork_prefix`` + the agent name.
        fork_prefix: Prefix for auto-generated branch names.
        name: ADK plugin display name.
    """

    def __init__(
        self,
        store: SessionStore | None = None,
        *,
        auto_fork: bool = True,
        fork_prefix: str = "auto",
        name: str = "adkf_session_plugin",
    ) -> None:
        super().__init__(name=name)
        self._store = store or SessionStore()
        self._auto_fork = auto_fork
        self._fork_prefix = fork_prefix

    @property
    def store(self) -> SessionStore:
        return self._store

    async def after_agent_callback(
        self,
        *,
        agent: Any = None,
        callback_context: Any,
    ) -> Any:
        if not self._auto_fork:
            return None
        agent_name = getattr(callback_context, "agent_name", "") or "anon"
        state = getattr(callback_context, "state", None)
        if state is None:
            return None
        try:
            state_dict = dict(state) if hasattr(state, "items") else {}
        except Exception:
            state_dict = {}
        branch_name = f"{self._fork_prefix}:{agent_name}"
        self._store.fork(branch_name, state_dict)
        return None
