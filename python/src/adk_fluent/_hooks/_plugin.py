"""HookPlugin — ADK ``BasePlugin`` subclass that dispatches a HookRegistry.

A single ``HookPlugin`` is installed onto an ADK ``App`` / ``Runner`` and
intercepts every tool call, model call, agent run, and session lifecycle event
regardless of depth. This is the **only** ADK plugin adk-fluent ships that
implements hook dispatch; because ADK plugins are already session-scoped and
subagent-inherited, we do not need a tree-walker to install agent callbacks
on every descendant.

The plugin is a thin adapter. For each ADK callback point it:

1. Builds a :class:`HookContext` from the ADK callback arguments.
2. Awaits ``registry.dispatch(ctx)`` and receives a single folded decision.
3. Drains any pending ``inject`` side-effects into the session's
   :class:`SystemMessageChannel`.
4. Translates the decision back to ADK's expected return type for that
   callback point (``dict`` / ``LlmResponse`` / ``Content`` / ``None``).

The plugin also implements the built-in "drain system messages" behaviour: on
every ``before_model_callback`` it drains the session state channel and
prepends the drained strings to ``llm_request.contents`` as a user-role turn
labelled with a ``[system]`` prefix. ADK has no formal "system role" beyond
the model's system instruction, so system messages are injected as a user
turn with a well-known prefix — this is the same approach Claude Code uses
for transient out-of-band instructions.
"""

from __future__ import annotations

from typing import Any, Optional

from google.adk.plugins.base_plugin import BasePlugin
from google.adk.models.llm_response import LlmResponse
from google.genai import types as genai_types

from adk_fluent._hooks._channel import SystemMessageChannel
from adk_fluent._hooks._decision import HookAction, HookDecision
from adk_fluent._hooks._events import HookContext, HookEvent
from adk_fluent._hooks._registry import HookRegistry

__all__ = ["HookPlugin", "HookAsk"]


class HookAsk(Exception):
    """Raised when a hook returns :meth:`HookDecision.ask`.

    The harness runtime (REPL / dispatcher) may catch this and surface the
    prompt to the user. When uncaught, ADK will propagate it as a tool error
    which terminates the current call cleanly.
    """

    def __init__(self, prompt: str) -> None:
        super().__init__(prompt)
        self.prompt = prompt


class HookPlugin(BasePlugin):
    """ADK ``BasePlugin`` that dispatches a :class:`HookRegistry`.

    Not constructed directly by user code — use ``HookRegistry.as_plugin()``.
    """

    def __init__(self, registry: HookRegistry, *, name: str = "adkf_hook_plugin") -> None:
        super().__init__(name=name)
        self._registry = registry

    @property
    def registry(self) -> HookRegistry:
        return self._registry

    # -------------------------------------------------------------------
    # Context builders
    # -------------------------------------------------------------------

    def _tool_ctx(
        self,
        event: str,
        tool: Any,
        tool_args: dict[str, Any],
        tool_context: Any,
    ) -> HookContext:
        inv = getattr(tool_context, "_invocation_context", None)
        session = getattr(inv, "session", None)
        agent = getattr(inv, "agent", None)
        return HookContext(
            event=event,
            session_id=getattr(session, "id", None),
            invocation_id=getattr(inv, "invocation_id", None),
            agent_name=getattr(agent, "name", None),
            tool_name=getattr(tool, "name", None),
            tool_input=tool_args,
        )

    def _model_ctx(
        self,
        event: str,
        callback_context: Any,
        llm_request: Any = None,
        llm_response: Any = None,
    ) -> HookContext:
        inv = getattr(callback_context, "_invocation_context", None)
        session = getattr(inv, "session", None)
        return HookContext(
            event=event,
            session_id=getattr(session, "id", None),
            invocation_id=getattr(callback_context, "invocation_id", None),
            agent_name=getattr(callback_context, "agent_name", None),
            model=getattr(llm_request, "model", None),
            request=llm_request,
            response=llm_response,
        )

    def _agent_ctx(self, event: str, agent: Any, callback_context: Any) -> HookContext:
        inv = getattr(callback_context, "_invocation_context", None)
        session = getattr(inv, "session", None)
        return HookContext(
            event=event,
            session_id=getattr(session, "id", None),
            invocation_id=getattr(callback_context, "invocation_id", None),
            agent_name=getattr(agent, "name", None),
        )

    def _session_ctx(self, event: str, invocation_context: Any) -> HookContext:
        session = getattr(invocation_context, "session", None)
        agent = getattr(invocation_context, "agent", None)
        return HookContext(
            event=event,
            session_id=getattr(session, "id", None),
            invocation_id=getattr(invocation_context, "invocation_id", None),
            agent_name=getattr(agent, "name", None),
        )

    # -------------------------------------------------------------------
    # Inject draining
    # -------------------------------------------------------------------

    def _drain_injects(self, decision: HookDecision, state: Any) -> None:
        pending: list[str] = list(decision.metadata.get("pending_injects", []))
        if decision.action == HookAction.INJECT and decision.system_message:
            pending.append(decision.system_message)
        if not pending or state is None:
            return
        channel = SystemMessageChannel(state)
        for message in pending:
            channel.append(message)

    # -------------------------------------------------------------------
    # Tool lifecycle
    # -------------------------------------------------------------------

    async def before_tool_callback(
        self,
        *,
        tool: Any,
        tool_args: dict[str, Any],
        tool_context: Any,
    ) -> Optional[dict]:
        ctx = self._tool_ctx(HookEvent.PRE_TOOL_USE, tool, tool_args, tool_context)
        decision = await self._registry.dispatch(ctx)
        self._drain_injects(decision, _state_from_tool_context(tool_context))
        return _tool_decision_to_adk(decision)

    async def after_tool_callback(
        self,
        *,
        tool: Any,
        tool_args: dict[str, Any],
        tool_context: Any,
        result: dict,
    ) -> Optional[dict]:
        ctx = self._tool_ctx(HookEvent.POST_TOOL_USE, tool, tool_args, tool_context)
        ctx.tool_output = result
        decision = await self._registry.dispatch(ctx)
        self._drain_injects(decision, _state_from_tool_context(tool_context))
        return _tool_decision_to_adk(decision)

    async def on_tool_error_callback(
        self,
        *,
        tool: Any,
        tool_args: dict[str, Any],
        tool_context: Any,
        error: Exception,
    ) -> Optional[dict]:
        ctx = self._tool_ctx(HookEvent.TOOL_ERROR, tool, tool_args, tool_context)
        ctx.error = error
        decision = await self._registry.dispatch(ctx)
        self._drain_injects(decision, _state_from_tool_context(tool_context))
        return _tool_decision_to_adk(decision)

    # -------------------------------------------------------------------
    # Model lifecycle
    # -------------------------------------------------------------------

    async def before_model_callback(
        self,
        *,
        callback_context: Any,
        llm_request: Any,
    ) -> Optional[LlmResponse]:
        state = _state_from_callback_context(callback_context)
        # Drain any pending system messages into the outgoing request BEFORE
        # dispatching user hooks — guarantees earlier-turn injects attach to
        # the next model call.
        _inject_system_messages_into_request(state, llm_request)

        ctx = self._model_ctx(HookEvent.PRE_MODEL, callback_context, llm_request=llm_request)
        decision = await self._registry.dispatch(ctx)
        self._drain_injects(decision, state)
        return _model_decision_to_adk(decision)

    async def after_model_callback(
        self,
        *,
        callback_context: Any,
        llm_response: LlmResponse,
    ) -> Optional[LlmResponse]:
        ctx = self._model_ctx(
            HookEvent.POST_MODEL, callback_context, llm_response=llm_response
        )
        decision = await self._registry.dispatch(ctx)
        self._drain_injects(decision, _state_from_callback_context(callback_context))
        return _model_decision_to_adk(decision)

    async def on_model_error_callback(
        self,
        *,
        callback_context: Any,
        llm_request: Any,
        error: Exception,
    ) -> Optional[LlmResponse]:
        ctx = self._model_ctx(
            HookEvent.MODEL_ERROR, callback_context, llm_request=llm_request
        )
        ctx.error = error
        decision = await self._registry.dispatch(ctx)
        self._drain_injects(decision, _state_from_callback_context(callback_context))
        return _model_decision_to_adk(decision)

    # -------------------------------------------------------------------
    # Agent lifecycle
    # -------------------------------------------------------------------

    async def before_agent_callback(
        self,
        *,
        agent: Any,
        callback_context: Any,
    ) -> Optional[genai_types.Content]:
        ctx = self._agent_ctx(HookEvent.PRE_AGENT, agent, callback_context)
        decision = await self._registry.dispatch(ctx)
        self._drain_injects(decision, _state_from_callback_context(callback_context))
        return _content_decision_to_adk(decision)

    async def after_agent_callback(
        self,
        *,
        agent: Any,
        callback_context: Any,
    ) -> Optional[genai_types.Content]:
        ctx = self._agent_ctx(HookEvent.POST_AGENT, agent, callback_context)
        decision = await self._registry.dispatch(ctx)
        self._drain_injects(decision, _state_from_callback_context(callback_context))
        return _content_decision_to_adk(decision)

    # -------------------------------------------------------------------
    # Session lifecycle
    # -------------------------------------------------------------------

    async def on_user_message_callback(
        self,
        *,
        invocation_context: Any,
        user_message: Any,
    ) -> Optional[genai_types.Content]:
        ctx = self._session_ctx(HookEvent.USER_PROMPT_SUBMIT, invocation_context)
        ctx.user_message = _content_to_text(user_message)
        decision = await self._registry.dispatch(ctx)
        self._drain_injects(decision, _state_from_invocation_context(invocation_context))
        return _content_decision_to_adk(decision)

    async def before_run_callback(
        self,
        *,
        invocation_context: Any,
    ) -> Optional[genai_types.Content]:
        ctx = self._session_ctx(HookEvent.SESSION_START, invocation_context)
        decision = await self._registry.dispatch(ctx)
        self._drain_injects(decision, _state_from_invocation_context(invocation_context))
        return _content_decision_to_adk(decision)

    async def after_run_callback(self, *, invocation_context: Any) -> None:
        ctx = self._session_ctx(HookEvent.SESSION_END, invocation_context)
        await self._registry.dispatch(ctx)

    async def on_event_callback(
        self,
        *,
        invocation_context: Any,
        event: Any,
    ) -> Optional[Any]:
        ctx = self._session_ctx(HookEvent.ON_EVENT, invocation_context)
        ctx.extra["event"] = event
        decision = await self._registry.dispatch(ctx)
        self._drain_injects(decision, _state_from_invocation_context(invocation_context))
        if decision.action == HookAction.REPLACE:
            return decision.output
        return None


# ---------------------------------------------------------------------------
# Decision → ADK return translators
# ---------------------------------------------------------------------------


def _tool_decision_to_adk(decision: HookDecision) -> Optional[dict]:
    if decision.action in (HookAction.ALLOW, HookAction.MODIFY, HookAction.INJECT):
        return None
    if decision.action == HookAction.DENY:
        return {"error": decision.reason or "Denied by hook"}
    if decision.action == HookAction.REPLACE:
        output = decision.output
        if isinstance(output, dict):
            return output
        return {"result": output}
    if decision.action == HookAction.ASK:
        raise HookAsk(decision.prompt)
    return None


def _model_decision_to_adk(decision: HookDecision) -> Optional[LlmResponse]:
    if decision.action in (HookAction.ALLOW, HookAction.MODIFY, HookAction.INJECT):
        return None
    if decision.action == HookAction.ASK:
        raise HookAsk(decision.prompt)
    if decision.action == HookAction.DENY:
        return LlmResponse(error_message=decision.reason or "Denied by hook")
    if decision.action == HookAction.REPLACE:
        output = decision.output
        if isinstance(output, LlmResponse):
            return output
        return LlmResponse(
            content=genai_types.Content(
                role="model",
                parts=[genai_types.Part(text=str(output))],
            )
        )
    return None


def _content_decision_to_adk(decision: HookDecision) -> Optional[genai_types.Content]:
    if decision.action in (HookAction.ALLOW, HookAction.INJECT, HookAction.MODIFY):
        return None
    if decision.action == HookAction.ASK:
        raise HookAsk(decision.prompt)
    if decision.action == HookAction.DENY:
        return genai_types.Content(
            role="model",
            parts=[genai_types.Part(text=decision.reason or "Denied by hook")],
        )
    if decision.action == HookAction.REPLACE:
        output = decision.output
        if isinstance(output, genai_types.Content):
            return output
        return genai_types.Content(
            role="model", parts=[genai_types.Part(text=str(output))]
        )
    return None


# ---------------------------------------------------------------------------
# State / request helpers
# ---------------------------------------------------------------------------


def _state_from_tool_context(tool_context: Any) -> Any:
    try:
        return tool_context.state
    except Exception:
        return None


def _state_from_callback_context(callback_context: Any) -> Any:
    try:
        return callback_context.state
    except Exception:
        return None


def _state_from_invocation_context(invocation_context: Any) -> Any:
    try:
        return invocation_context.session.state
    except Exception:
        return None


def _content_to_text(content: Any) -> str:
    if content is None:
        return ""
    parts = getattr(content, "parts", None) or []
    out: list[str] = []
    for part in parts:
        text = getattr(part, "text", None)
        if text:
            out.append(text)
    return "\n".join(out)


def _inject_system_messages_into_request(state: Any, llm_request: Any) -> None:
    """Drain pending system messages and prepend them to ``llm_request.contents``."""
    if state is None or llm_request is None:
        return
    channel = SystemMessageChannel(state)
    messages = channel.drain()
    if not messages:
        return
    prefix_text = "\n\n".join(f"[system] {m}" for m in messages)
    injected = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=prefix_text)],
    )
    existing = list(getattr(llm_request, "contents", []) or [])
    try:
        llm_request.contents = [injected, *existing]
    except Exception:  # pragma: no cover
        pass
