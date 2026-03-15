"""A2A (Agent-to-Agent) protocol builders for adk-fluent.

Provides fluent builder APIs for:
- ``RemoteAgent``: Consume a remote A2A agent as a first-class builder.
- ``A2AServer``: Publish a local agent as an A2A server.

Both are experimental — the underlying ADK A2A support is marked
``@a2a_experimental`` and subject to breaking changes.

Usage::

    from adk_fluent import Agent, RemoteAgent, A2AServer

    # Consume a remote agent
    remote = RemoteAgent("helper", "http://helper:8001")
    pipeline = Agent("coordinator", "gemini-2.5-flash") >> remote

    # Publish a local agent
    app = A2AServer(agent).port(8001).build()
"""

from __future__ import annotations

import warnings
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Self

from adk_fluent._base import BuilderBase

if TYPE_CHECKING:
    from google.adk.agents.base_agent import BaseAgent as _ADKBaseAgent

__all__ = [
    "A2AServer",
    "RemoteAgent",
    "SkillDeclaration",
]

_A2A_WARNING = (
    "adk-fluent A2A support is experimental. The underlying google-adk A2A "
    "APIs are marked @a2a_experimental and may change without notice."
)


def _warn_experimental() -> None:
    warnings.warn(_A2A_WARNING, stacklevel=3)


# ---------------------------------------------------------------------------
# SkillDeclaration — data object for .skill() metadata
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SkillDeclaration:
    """Metadata for a single A2A skill published in an AgentCard."""

    id: str
    name: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    input_modes: list[str] = field(default_factory=lambda: ["text/plain"])
    output_modes: list[str] = field(default_factory=lambda: ["text/plain"])


# ---------------------------------------------------------------------------
# RemoteAgent — client-side A2A consumer
# ---------------------------------------------------------------------------


class RemoteAgent(BuilderBase):
    """Fluent builder for consuming a remote A2A agent.

    Wraps ``google.adk.agents.remote_a2a_agent.RemoteA2aAgent``.
    Participates in all adk-fluent operators (``>>``, ``|``, ``*``, ``//``).

    Examples::

        # Minimal
        remote = RemoteAgent("helper", "http://helper:8001")

        # With options
        remote = (
            RemoteAgent("helper", "http://helper:8001")
            .describe("Specialized research agent")
            .timeout(300)
        )

        # In composition
        pipeline = Agent("local") >> RemoteAgent("remote", "http://r:8001")
    """

    _ALIASES: dict[str, str] = {"describe": "description"}
    _CALLBACK_ALIASES: dict[str, str] = {
        "after_agent": "after_agent_callback",
        "before_agent": "before_agent_callback",
    }
    _ADDITIVE_FIELDS: set[str] = {"after_agent_callback", "before_agent_callback"}
    # _ADK_TARGET_CLASS set lazily to avoid import-time dependency on a2a SDK

    def __init__(self, name: str, agent_card: str | Any | None = None) -> None:
        """Create a RemoteAgent builder.

        Args:
            name: Unique agent name.
            agent_card: URL string (base URL or full card URL),
                        AgentCard object, or file path to card JSON.
        """
        _warn_experimental()
        self._config: dict[str, Any] = {"name": name}
        self._callbacks: dict[str, list[Callable]] = defaultdict(list)
        self._lists: dict[str, list] = defaultdict(list)
        self._frozen = False
        if agent_card is not None:
            self._config["agent_card"] = agent_card

    # --- Core setters ---

    def describe(self, value: str) -> Self:
        """Set the agent description."""
        self = self._maybe_fork_for_mutation()
        self._config["description"] = value
        return self

    def timeout(self, seconds: float) -> Self:
        """Set the HTTP timeout for remote calls (default 600s)."""
        self = self._maybe_fork_for_mutation()
        self._config["timeout"] = seconds
        return self

    def card(self, agent_card: Any) -> Self:
        """Set an explicit AgentCard object."""
        self = self._maybe_fork_for_mutation()
        self._config["agent_card"] = agent_card
        return self

    def card_url(self, url: str) -> Self:
        """Set the agent card URL."""
        self = self._maybe_fork_for_mutation()
        self._config["agent_card"] = url
        return self

    def card_path(self, path: str) -> Self:
        """Load the agent card from a local JSON file."""
        self = self._maybe_fork_for_mutation()
        self._config["agent_card"] = path
        return self

    def streaming(self, enabled: bool = True) -> Self:
        """Prefer streaming communication with the remote agent."""
        self = self._maybe_fork_for_mutation()
        self._config["_streaming"] = enabled
        return self

    def full_history(self, enabled: bool = True) -> Self:
        """Send full conversation history to stateless remote agents."""
        self = self._maybe_fork_for_mutation()
        self._config["full_history_when_stateless"] = enabled
        return self

    # --- Callbacks ---

    def after_agent(self, *fns: Callable[..., Any]) -> Self:
        """Append callback(s) to ``after_agent_callback``."""
        self = self._maybe_fork_for_mutation()
        for fn in fns:
            self._callbacks["after_agent_callback"].append(fn)
        return self

    def before_agent(self, *fns: Callable[..., Any]) -> Self:
        """Append callback(s) to ``before_agent_callback``."""
        self = self._maybe_fork_for_mutation()
        for fn in fns:
            self._callbacks["before_agent_callback"].append(fn)
        return self

    # --- Sub-agents (for operator composition) ---

    def sub_agents(self, value: list[Any]) -> Self:
        """Set the ``sub_agents`` field."""
        self = self._maybe_fork_for_mutation()
        self._config["sub_agents"] = value
        return self

    def sub_agent(self, value: Any) -> Self:
        """Append to ``sub_agents``."""
        self = self._maybe_fork_for_mutation()
        self._lists["sub_agents"].append(value)
        return self

    # --- Build ---

    def build(self) -> _ADKBaseAgent:
        """Resolve into a native ``RemoteA2aAgent``.

        Raises:
            ImportError: If ``a2a`` SDK is not installed.
        """
        try:
            from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
        except ImportError as exc:
            raise ImportError(
                "A2A support requires the a2a SDK. "
                "Install with: pip install google-adk[a2a]"
            ) from exc

        config = dict(self._config)

        # Strip internal keys
        config.pop("_streaming", None)

        # Remove keys not accepted by RemoteA2aAgent
        internal_keys = [k for k in config if k.startswith("_")]
        for k in internal_keys:
            config.pop(k)

        # Handle callbacks
        for _cb_alias, cb_field in self._CALLBACK_ALIASES.items():
            fns = self._callbacks.get(cb_field, [])
            if fns:
                if len(fns) == 1:
                    config[cb_field] = fns[0]
                else:
                    composed = fns[0]
                    for fn in fns[1:]:
                        prev = composed

                        async def _chain(ctx, prev=prev, fn=fn):  # noqa: E731
                            await prev(ctx)
                            await fn(ctx)

                        composed = _chain
                    config[cb_field] = composed

        return RemoteA2aAgent(**config)


# ---------------------------------------------------------------------------
# A2AServer — server-side A2A publisher
# ---------------------------------------------------------------------------


class A2AServer:
    """Fluent builder for publishing a local agent as an A2A server.

    Wraps ``google.adk.a2a.utils.agent_to_a2a.to_a2a``.

    Examples::

        # Minimal
        app = A2AServer(agent).build()

        # With options
        app = (
            A2AServer(agent)
            .port(8001)
            .host("0.0.0.0")
            .version("1.0.0")
            .provider("Acme Corp", "https://acme.com")
            .streaming(True)
            .build()
        )
    """

    def __init__(self, agent: BuilderBase | _ADKBaseAgent | None = None) -> None:
        """Create an A2AServer builder.

        Args:
            agent: An adk-fluent builder or a native ADK BaseAgent to publish.
        """
        _warn_experimental()
        self._agent = agent
        self._host: str = "0.0.0.0"
        self._port: int = 8000
        self._protocol: str = "http"
        self._version: str = "1.0.0"
        self._provider_org: str | None = None
        self._provider_url: str | None = None
        self._streaming_enabled: bool = False
        self._push_notifications: bool = False
        self._card: Any = None
        self._runner: Any = None
        self._skills: list[SkillDeclaration] = []
        self._docs_url: str | None = None

    def agent(self, agent: BuilderBase | _ADKBaseAgent) -> A2AServer:
        """Set the agent to publish."""
        self._agent = agent
        return self

    def host(self, value: str) -> A2AServer:
        """Set the server host (default "0.0.0.0")."""
        self._host = value
        return self

    def port(self, value: int) -> A2AServer:
        """Set the server port (default 8000)."""
        self._port = value
        return self

    def protocol(self, value: str) -> A2AServer:
        """Set the URL protocol (default "http")."""
        self._protocol = value
        return self

    def version(self, value: str) -> A2AServer:
        """Set the agent version for the AgentCard."""
        self._version = value
        return self

    def provider(self, organization: str, url: str | None = None) -> A2AServer:
        """Set the provider info for the AgentCard."""
        self._provider_org = organization
        self._provider_url = url
        return self

    def streaming(self, enabled: bool = True) -> A2AServer:
        """Enable or disable streaming support in the AgentCard."""
        self._streaming_enabled = enabled
        return self

    def push_notifications(self, enabled: bool = True) -> A2AServer:
        """Enable or disable push notification support."""
        self._push_notifications = enabled
        return self

    def card(self, agent_card: Any) -> A2AServer:
        """Provide an explicit AgentCard (bypasses auto-generation)."""
        self._card = agent_card
        return self

    def runner(self, runner: Any) -> A2AServer:
        """Provide a custom Runner for the A2A server."""
        self._runner = runner
        return self

    def skill(
        self,
        skill_id: str,
        name: str,
        *,
        description: str = "",
        tags: list[str] | None = None,
        examples: list[str] | None = None,
        input_modes: list[str] | None = None,
        output_modes: list[str] | None = None,
    ) -> A2AServer:
        """Declare an A2A skill for the AgentCard.

        Skills declared here override auto-inferred skills from agent internals.
        """
        self._skills.append(
            SkillDeclaration(
                id=skill_id,
                name=name,
                description=description,
                tags=tags or [],
                examples=examples or [],
                input_modes=input_modes or ["text/plain"],
                output_modes=output_modes or ["text/plain"],
            )
        )
        return self

    def docs(self, url: str) -> A2AServer:
        """Set the documentation URL for the AgentCard."""
        self._docs_url = url
        return self

    def build(self) -> Any:
        """Build and return a Starlette ASGI application.

        Returns:
            A ``starlette.applications.Starlette`` app ready for ``uvicorn``.

        Raises:
            ImportError: If ``a2a`` SDK is not installed.
            ValueError: If no agent is configured.
        """
        if self._agent is None:
            raise ValueError("No agent configured. Pass an agent to A2AServer() or call .agent().")

        try:
            from google.adk.a2a.utils.agent_to_a2a import to_a2a
        except ImportError as exc:
            raise ImportError(
                "A2A support requires the a2a SDK. "
                "Install with: pip install google-adk[a2a]"
            ) from exc

        # Build the agent if it's a builder
        built_agent = self._agent
        if hasattr(built_agent, "build") and hasattr(built_agent, "_config"):
            built_agent = built_agent.build()

        # Build agent card if skills or provider are customized
        agent_card = self._card
        if agent_card is None and (self._skills or self._provider_org):
            agent_card = self._build_agent_card(built_agent)

        kwargs: dict[str, Any] = {
            "agent": built_agent,
            "host": self._host,
            "port": self._port,
            "protocol": self._protocol,
        }
        if agent_card is not None:
            kwargs["agent_card"] = agent_card
        if self._runner is not None:
            kwargs["runner"] = self._runner

        return to_a2a(**kwargs)

    def _build_agent_card(self, agent: _ADKBaseAgent) -> Any:
        """Build an AgentCard from declared skills and metadata."""
        try:
            from a2a.types import AgentCapabilities, AgentProvider, AgentSkill
            from a2a.types import AgentCard as A2AAgentCard
        except ImportError as exc:
            raise ImportError(
                "A2A card building requires the a2a SDK. "
                "Install with: pip install google-adk[a2a]"
            ) from exc

        skills = []
        for s in self._skills:
            skills.append(
                AgentSkill(
                    id=s.id,
                    name=s.name,
                    description=s.description,
                    tags=s.tags,
                    examples=s.examples,
                    inputModes=s.input_modes,
                    outputModes=s.output_modes,
                )
            )

        rpc_url = f"{self._protocol}://{self._host}:{self._port}/"

        card_kwargs: dict[str, Any] = {
            "name": getattr(agent, "name", "agent"),
            "description": getattr(agent, "description", "") or "",
            "url": rpc_url,
            "version": self._version,
            "skills": skills,
            "defaultInputModes": ["text/plain"],
            "defaultOutputModes": ["text/plain"],
            "capabilities": AgentCapabilities(
                streaming=self._streaming_enabled,
                pushNotifications=self._push_notifications,
            ),
        }

        if self._provider_org:
            card_kwargs["provider"] = AgentProvider(
                organization=self._provider_org,
                url=self._provider_url or "",
            )

        if self._docs_url:
            card_kwargs["documentationUrl"] = self._docs_url

        return A2AAgentCard(**card_kwargs)
