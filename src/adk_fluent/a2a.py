"""A2A (Agent-to-Agent) protocol builders for adk-fluent.

Provides fluent builder APIs for:
- ``RemoteAgent``: Consume a remote A2A agent as a first-class builder.
- ``A2AServer``: Publish a local agent as an A2A server.
- ``AgentRegistry``: Discover agents from a central registry.

Both are experimental — the underlying ADK A2A support is marked
``@a2a_experimental`` and subject to breaking changes.

Usage::

    from adk_fluent import Agent, RemoteAgent, A2AServer

    # Consume a remote agent
    remote = RemoteAgent("helper", "http://helper:8001")
    pipeline = Agent("coordinator", "gemini-2.5-flash") >> remote

    # Discover via well-known URL
    remote = RemoteAgent.discover("helper", "helper.agents.acme.com")

    # Discover via environment variable
    remote = RemoteAgent("helper", env="HELPER_AGENT_URL")

    # Publish a local agent with health checks
    app = A2AServer(agent).port(8001).health_check().build()
"""

from __future__ import annotations

import logging
import os
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
    "AgentRegistry",
    "RemoteAgent",
    "SkillDeclaration",
]

_log = logging.getLogger(__name__)

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
# State bridging callbacks
# ---------------------------------------------------------------------------


def _build_state_bridge_callbacks(
    *,
    sends_keys: list[str],
    receives_keys: list[str],
    persistent_context: bool,
    context_state_key: str,
) -> dict[str, Callable | None]:
    """Build before/after agent callbacks for A2A state bridging.

    Returns a dict with ``"before"`` and ``"after"`` callbacks (or None).
    """
    before_cb: Callable | None = None
    after_cb: Callable | None = None

    if sends_keys or persistent_context:

        async def _before_agent(ctx: Any) -> None:
            """Inject state keys into the agent context before A2A call."""
            session = getattr(ctx, "session", None)
            if session is None:
                return
            state = getattr(session, "state", {})

            # Serialize sends_keys into the context for the remote agent
            if sends_keys:
                bridged = {}
                for key in sends_keys:
                    if key in state:
                        bridged[key] = state[key]
                if bridged:
                    state["_a2a_bridged_sends"] = bridged

            # Restore persistent contextId
            if persistent_context:
                stored_ctx_id = state.get(context_state_key)
                if stored_ctx_id:
                    state["_a2a_reuse_context_id"] = stored_ctx_id

        before_cb = _before_agent

    if receives_keys or persistent_context:

        async def _after_agent(ctx: Any) -> None:
            """Extract state keys from the A2A response after call."""
            session = getattr(ctx, "session", None)
            if session is None:
                return
            state = getattr(session, "state", {})

            # Deserialize receives_keys from response
            if receives_keys:
                bridged = state.get("_a2a_bridged_receives", {})
                for key in receives_keys:
                    if key in bridged:
                        state[key] = bridged[key]
                state.pop("_a2a_bridged_receives", None)

            # Store persistent contextId
            if persistent_context:
                ctx_id = state.get("_a2a_last_context_id")
                if ctx_id:
                    state[context_state_key] = ctx_id

        after_cb = _after_agent

    return {"before": before_cb, "after": after_cb}


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

    def __init__(
        self,
        name: str,
        agent_card: str | Any | None = None,
        *,
        env: str | None = None,
    ) -> None:
        """Create a RemoteAgent builder.

        Args:
            name: Unique agent name.
            agent_card: URL string (base URL or full card URL),
                        AgentCard object, or file path to card JSON.
            env: Environment variable name containing the agent URL.
                 Read at init time; raises ``ValueError`` if the var
                 is set but empty.
        """
        _warn_experimental()
        self._config: dict[str, Any] = {"name": name}
        self._callbacks: dict[str, list[Callable]] = defaultdict(list)
        self._lists: dict[str, list] = defaultdict(list)
        self._frozen = False

        # Resolve agent_card source: explicit > env > None
        if agent_card is not None:
            self._config["agent_card"] = agent_card
        elif env is not None:
            url = os.environ.get(env)
            if url is not None:
                if not url.strip():
                    raise ValueError(f"Environment variable {env!r} is set but empty")
                self._config["agent_card"] = url.strip()
            else:
                _log.warning("Environment variable %r not set for RemoteAgent %r", env, name)

    # --- Class-level discovery ---

    @classmethod
    def discover(
        cls,
        name: str,
        domain: str,
        *,
        protocol: str = "https",
        path: str = "/.well-known/agent.json",
    ) -> RemoteAgent:
        """Create a RemoteAgent by discovering its card via well-known URL.

        Constructs ``{protocol}://{domain}{path}`` and uses it as the
        ``agent_card`` URL. The underlying ADK ``RemoteA2aAgent`` resolves
        the card lazily on first invocation.

        Args:
            name: Unique agent name.
            domain: Agent domain (e.g., ``"helper.agents.acme.com"``).
            protocol: URL scheme (default ``"https"``).
            path: Well-known path (default ``"/.well-known/agent.json"``).

        Returns:
            A configured ``RemoteAgent`` builder.

        Example::

            remote = RemoteAgent.discover("helper", "helper.agents.acme.com")
            pipeline = Agent("coordinator") >> remote
        """
        card_url = f"{protocol}://{domain}{path}"
        return cls(name, card_url)

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

    # --- State bridging ---

    def sends(self, *keys: str) -> Self:
        """Declare state keys to serialize into outbound A2A messages.

        When this remote agent is invoked, the named state keys are
        extracted from the local session state and injected as structured
        ``Part`` objects in the A2A ``Message`` sent to the remote agent.

        This bridges the local ``session.state`` → A2A ``Message`` gap.

        Example::

            remote = (
                RemoteAgent("reviewer", "http://reviewer:8001")
                .sends("draft", "context")
            )
        """
        self = self._maybe_fork_for_mutation()
        existing = list(self._config.get("_sends_keys", []))
        existing.extend(keys)
        self._config["_sends_keys"] = existing
        return self

    def receives(self, *keys: str) -> Self:
        """Declare state keys to deserialize from inbound A2A responses.

        When the remote agent responds, named keys are extracted from
        the A2A response artifacts/parts and written back into the local
        ``session.state``.

        This bridges the A2A ``Message`` → local ``session.state`` gap.

        Example::

            remote = (
                RemoteAgent("reviewer", "http://reviewer:8001")
                .receives("feedback", "score")
            )
        """
        self = self._maybe_fork_for_mutation()
        existing = list(self._config.get("_receives_keys", []))
        existing.extend(keys)
        self._config["_receives_keys"] = existing
        return self

    def persistent_context(self, enabled: bool = True) -> Self:
        """Maintain A2A ``contextId`` across calls within the same session.

        When enabled, the builder stores the remote agent's ``contextId``
        in session state and reuses it for subsequent calls, enabling
        multi-turn conversations across A2A boundaries.

        The contextId is stored under ``_a2a_context_{agent_name}``.
        """
        self = self._maybe_fork_for_mutation()
        self._config["_persistent_context"] = enabled
        return self

    def context_key(self, key: str) -> Self:
        """Override the state key used to store the A2A contextId.

        Default: ``_a2a_context_{agent_name}``.
        """
        self = self._maybe_fork_for_mutation()
        self._config["_context_key"] = key
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

        # Extract state bridging config before stripping internal keys
        sends_keys = config.pop("_sends_keys", [])
        receives_keys = config.pop("_receives_keys", [])
        persistent_ctx = config.pop("_persistent_context", False)
        context_key = config.pop("_context_key", None)

        # Strip internal keys
        config.pop("_streaming", None)

        # Remove keys not accepted by RemoteA2aAgent
        internal_keys = [k for k in config if k.startswith("_")]
        for k in internal_keys:
            config.pop(k)

        # Inject state-bridging callbacks if configured
        if sends_keys or receives_keys or persistent_ctx:
            agent_name = config["name"]
            ctx_state_key = context_key or f"_a2a_context_{agent_name}"
            bridging_cbs = _build_state_bridge_callbacks(
                sends_keys=sends_keys,
                receives_keys=receives_keys,
                persistent_context=persistent_ctx,
                context_state_key=ctx_state_key,
            )
            if bridging_cbs.get("before"):
                self._callbacks["before_agent_callback"].insert(0, bridging_cbs["before"])
            if bridging_cbs.get("after"):
                self._callbacks["after_agent_callback"].append(bridging_cbs["after"])

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
        self._health_path: str | None = None
        self._health_ready: bool = True
        self._shutdown_timeout: float | None = None

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

    def health_check(
        self,
        path: str = "/health",
        *,
        include_ready: bool = True,
    ) -> A2AServer:
        """Add health check endpoints to the server.

        Adds:
        - ``GET {path}`` — liveness probe (always 200)
        - ``GET {path}/ready`` — readiness probe (200 when agent is ready)
          (only if ``include_ready=True``)

        Args:
            path: Base path for health endpoints (default ``"/health"``).
            include_ready: Include a readiness endpoint (default ``True``).

        Example::

            app = A2AServer(agent).health_check().build()
            # GET /health → {"status": "ok"}
            # GET /health/ready → {"status": "ready", "agent": "my_agent"}
        """
        self._health_path = path
        self._health_ready = include_ready
        return self

    def graceful_shutdown(self, timeout: float = 30) -> A2AServer:
        """Enable graceful shutdown with task draining.

        On SIGTERM/SIGINT, the server stops accepting new requests and
        waits up to ``timeout`` seconds for in-flight tasks to complete.

        Args:
            timeout: Maximum seconds to wait for drain (default 30).
        """
        self._shutdown_timeout = timeout
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

        app = to_a2a(**kwargs)

        # Wire health check endpoints
        if self._health_path is not None:
            app = _add_health_routes(
                app,
                built_agent,
                path=self._health_path,
                include_ready=self._health_ready,
            )

        # Wire graceful shutdown
        if self._shutdown_timeout is not None:
            app = _add_graceful_shutdown(app, timeout=self._shutdown_timeout)

        return app

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


# ---------------------------------------------------------------------------
# Health check and lifecycle helpers
# ---------------------------------------------------------------------------


def _add_health_routes(
    app: Any,
    agent: Any,
    *,
    path: str = "/health",
    include_ready: bool = True,
) -> Any:
    """Add health check routes to a Starlette app.

    - ``GET {path}`` — liveness (always 200)
    - ``GET {path}/ready`` — readiness (200 if agent is resolved)
    """
    try:
        from starlette.responses import JSONResponse
        from starlette.routing import Route
    except ImportError:
        _log.warning("starlette not installed — skipping health check routes")
        return app

    agent_name = getattr(agent, "name", "agent")

    async def _liveness(request: Any) -> JSONResponse:
        return JSONResponse({"status": "ok", "agent": agent_name})

    routes = [Route(path, _liveness, methods=["GET"])]

    if include_ready:

        async def _readiness(request: Any) -> JSONResponse:
            # Check basic readiness — agent exists and has a name
            is_ready = agent is not None and hasattr(agent, "name")
            if is_ready:
                return JSONResponse({"status": "ready", "agent": agent_name})
            return JSONResponse({"status": "not_ready", "agent": agent_name}, status_code=503)

        routes.append(Route(f"{path}/ready", _readiness, methods=["GET"]))

    # Prepend health routes to the app's routes
    if hasattr(app, "routes"):
        app.routes = routes + list(app.routes)
    return app


def _add_graceful_shutdown(app: Any, *, timeout: float = 30) -> Any:
    """Wire graceful shutdown into a Starlette app.

    Registers a shutdown handler that waits up to ``timeout`` seconds
    for in-flight work to complete.
    """
    import asyncio

    _shutting_down = {"value": False}
    _in_flight = {"count": 0}

    original_on_shutdown = list(getattr(app, "on_shutdown", []))

    async def _shutdown_handler() -> None:
        _shutting_down["value"] = True
        _log.info("Graceful shutdown initiated, draining tasks (timeout=%ss)...", timeout)

        elapsed = 0.0
        poll_interval = 0.5
        while _in_flight["count"] > 0 and elapsed < timeout:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        if _in_flight["count"] > 0:
            _log.warning(
                "Shutdown timeout reached with %d in-flight tasks",
                _in_flight["count"],
            )
        else:
            _log.info("All tasks drained, shutting down cleanly")

        # Run original shutdown handlers
        for handler in original_on_shutdown:
            await handler()

    if hasattr(app, "on_shutdown"):
        app.on_shutdown = [_shutdown_handler]

    # Store refs for introspection/testing
    app._a2a_shutdown_state = _shutting_down
    app._a2a_in_flight = _in_flight

    return app


# ---------------------------------------------------------------------------
# AgentRegistry — central registry client
# ---------------------------------------------------------------------------


class AgentRegistry:
    """Client for discovering A2A agents from a central registry.

    Provides a fluent interface for querying a registry service that
    indexes agent cards by skill, tag, and metadata.

    The registry protocol is not standardized by A2A — this client
    supports a simple REST-based convention:

    - ``GET {base_url}/agents`` — list all agents
    - ``GET {base_url}/agents?skill={skill}`` — filter by skill
    - ``GET {base_url}/agents?tag={tag}`` — filter by tag
    - ``GET {base_url}/agents/{name}`` — get agent card by name

    Usage::

        registry = AgentRegistry("http://registry.internal:9000")

        # Find by skill
        remote = registry.find("research", skill="academic-research")

        # Find by tag
        remote = registry.find("coder", tag="python")

        # List all agents
        agents = await registry.list_agents()
    """

    def __init__(self, base_url: str, *, timeout: float = 30) -> None:
        """Create a registry client.

        Args:
            base_url: Base URL of the registry service.
            timeout: HTTP timeout in seconds (default 30).
        """
        _warn_experimental()
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def find(
        self,
        name: str,
        *,
        skill: str | None = None,
        tag: str | None = None,
    ) -> RemoteAgent:
        """Find an agent by name, optionally filtered by skill or tag.

        Constructs a ``RemoteAgent`` pointing to the registry's agent
        card URL. The card is resolved lazily on first invocation.

        Args:
            name: Name for the RemoteAgent builder.
            skill: Filter by skill ID.
            tag: Filter by tag.

        Returns:
            A ``RemoteAgent`` builder configured with the registry URL.
        """
        # Build registry query URL
        params = []
        if skill:
            params.append(f"skill={skill}")
        if tag:
            params.append(f"tag={tag}")
        query = f"?{'&'.join(params)}" if params else ""
        card_url = f"{self._base_url}/agents/{name}{query}"
        return RemoteAgent(name, card_url).timeout(self._timeout)

    async def list_agents(self) -> list[dict[str, Any]]:
        """List all agents registered in the registry.

        Returns:
            A list of agent card metadata dicts.

        Raises:
            ImportError: If ``httpx`` is not installed.
            RuntimeError: If the registry is unreachable.
        """
        try:
            import httpx
        except ImportError as exc:
            raise ImportError("AgentRegistry requires httpx. Install with: pip install httpx") from exc

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(f"{self._base_url}/agents")
                response.raise_for_status()
                return response.json()
        except Exception as exc:
            raise RuntimeError(f"Failed to list agents from registry at {self._base_url}: {exc}") from exc

    def __repr__(self) -> str:
        return f"AgentRegistry({self._base_url!r})"
