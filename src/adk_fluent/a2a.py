"""A2A (Agent-to-Agent) protocol support for adk-fluent.

Provides two builders:

- **RemoteAgent** -- consume a remote A2A agent as if it were local.
- **A2AServer** -- publish an adk-fluent agent as an A2A-compatible server.

Both require the ``[a2a]`` extra::

    pip install adk-fluent[a2a]

Usage::

    from adk_fluent import Agent, RemoteAgent, A2AServer

    # Consume -- one line
    remote = RemoteAgent("helper", "http://remote:8001")
    pipeline = Agent("coordinator") >> remote

    # Publish -- one line
    app = Agent("researcher").instruct("...").publish(port=8001)

    # Or with full control
    app = (
        A2AServer(Agent("researcher").instruct("..."))
        .port(8001)
        .provider("Acme Corp", "https://acme.com")
        .streaming(True)
        .build()
    )
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import Any, Self

from adk_fluent._base import BuilderBase

__all__ = [
    "RemoteAgent",
    "A2AServer",
]


# ---------------------------------------------------------------------------
# Dependency guard
# ---------------------------------------------------------------------------


def _require_a2a(symbol: str = "A2A support") -> None:
    """Raise a clear error if google-adk[a2a] is not installed."""
    try:
        from google.adk.agents import remote_a2a_agent as _  # noqa: F401
    except ImportError:
        raise ImportError(f"{symbol} requires the A2A extra. Install with: pip install adk-fluent[a2a]") from None


# ---------------------------------------------------------------------------
# RemoteAgent -- client-side A2A consumption
# ---------------------------------------------------------------------------


class RemoteAgent(BuilderBase):
    """Consume a remote A2A agent as if it were local.

    Wraps ``google.adk.agents.remote_a2a_agent.RemoteA2aAgent`` with a
    fluent builder API. Inherits all operators (``>>``, ``|``, ``//``, ``*``)
    from ``BuilderBase``.

    Args:
        name: Unique identifier for this agent (used by parent LLM for delegation).
        agent_card: URL to the remote ``/.well-known/agent.json``, a file path,
            or an ``AgentCard`` object.  A base URL like ``http://host:port``
            is also accepted (``/.well-known/agent.json`` is auto-appended).

    Usage::

        from adk_fluent import Agent, RemoteAgent

        # One-liner consumption
        remote = RemoteAgent("helper", "http://remote:8001")

        # All operators work
        pipeline = Agent("coordinator") >> remote
        fanout   = remote | Agent("local")
        fallback = remote // Agent("local-fallback")

        # As a sub-agent with full config
        coordinator = (
            Agent("coordinator", "gemini-2.5-flash")
            .instruct("Delegate research tasks to helper.")
            .sub_agent(
                RemoteAgent("helper", "http://remote:8001")
                .describe("Specialized research agent")
                .timeout(300)
                .auth(bearer="token123")
            )
            .build()
        )
    """

    _ALIASES: dict[str, str] = {"describe": "description"}
    _CALLBACK_ALIASES: dict[str, str] = {}
    _ADDITIVE_FIELDS: set[str] = set()

    def __init__(self, name: str, agent_card: str | Any | None = None) -> None:
        self._config: dict[str, Any] = {"name": name}
        self._callbacks: dict[str, list[Callable]] = defaultdict(list)
        self._lists: dict[str, list] = defaultdict(list)
        self._frozen = False
        if agent_card is not None:
            self._config["agent_card"] = agent_card

    # ------------------------------------------------------------------
    # Ergonomic builder methods
    # ------------------------------------------------------------------

    def card(self, agent_card: str | Any) -> Self:
        """Set agent card -- URL, file path, or ``AgentCard`` object.

        If a base URL like ``http://host:port`` is provided,
        ``/.well-known/agent.json`` is auto-appended by ADK.
        """
        self = self._maybe_fork_for_mutation()
        self._config["agent_card"] = agent_card
        return self

    def describe(self, value: str) -> Self:
        """Set agent description (shown to parent LLM for delegation decisions)."""
        self = self._maybe_fork_for_mutation()
        self._config["description"] = value
        return self

    def timeout(self, seconds: float) -> Self:
        """HTTP request timeout in seconds (default 600)."""
        self = self._maybe_fork_for_mutation()
        self._config["timeout"] = seconds
        return self

    def full_history(self, enabled: bool = True) -> Self:
        """Send full conversation history when in stateless mode."""
        self = self._maybe_fork_for_mutation()
        self._config["full_history_when_stateless"] = enabled
        return self

    def auth(
        self,
        *,
        bearer: str | None = None,
        api_key: str | None = None,
        header: str = "Authorization",
        **kwargs: Any,
    ) -> Self:
        """Configure authentication for the remote agent.

        Creates an ``httpx.AsyncClient`` with the appropriate headers at build time.

        Args:
            bearer: Bearer token (sent as ``Authorization: Bearer <token>``).
            api_key: API key value.
            header: Header name for API key (default ``Authorization``).
            **kwargs: Additional auth configuration.

        Usage::

            remote.auth(bearer="my-token")
            remote.auth(api_key="key", header="X-API-Key")
        """
        self = self._maybe_fork_for_mutation()
        auth_config: dict[str, Any] = {}
        if bearer is not None:
            auth_config["bearer"] = bearer
        if api_key is not None:
            auth_config["api_key"] = api_key
            auth_config["api_key_header"] = header
        auth_config.update(kwargs)
        self._config["_auth_config"] = auth_config
        return self

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self) -> Any:
        """Resolve into a native ADK ``RemoteA2aAgent``.

        Returns:
            A ``google.adk.agents.remote_a2a_agent.RemoteA2aAgent`` instance
            that can be used as a sub-agent or built into a workflow.

        Raises:
            ImportError: If ``google-adk[a2a]`` is not installed.
        """
        _require_a2a("RemoteAgent.build()")
        from google.adk.agents.remote_a2a_agent import RemoteA2aAgent as _ADK_RemoteA2aAgent

        config = self._prepare_build_config()

        # Translate _auth_config into an httpx client with auth headers
        auth_config = config.pop("_auth_config", None)
        config.pop("_streaming", None)  # reserved for future use
        if auth_config:
            import httpx

            headers: dict[str, str] = {}
            if "bearer" in auth_config:
                headers["Authorization"] = f"Bearer {auth_config['bearer']}"
            if "api_key" in auth_config:
                hdr = auth_config.get("api_key_header", "X-API-Key")
                headers[hdr] = auth_config["api_key"]
            config["httpx_client"] = httpx.AsyncClient(headers=headers)

        result = _ADK_RemoteA2aAgent(**config)
        return self._apply_native_hooks(result)

    def to_ir(self) -> Any:
        """Convert to an IR node for visualization and contract checking."""
        from adk_fluent._ir import Node

        return Node(
            kind="remote_agent",
            name=self._config.get("name", ""),
            metadata={
                "agent_card": str(self._config.get("agent_card", "")),
                "timeout": self._config.get("timeout"),
                "description": self._config.get("description", ""),
            },
        )


# ---------------------------------------------------------------------------
# A2AServer -- server-side A2A publishing
# ---------------------------------------------------------------------------


class A2AServer:
    """Publish an ADK agent as an A2A-compatible server.

    Wraps ``google.adk.a2a.utils.agent_to_a2a.to_a2a()`` with a fluent
    configuration API.  The ``build()`` method returns a Starlette ASGI app
    that serves:

    - ``/.well-known/agent.json`` -- the auto-generated (or custom) AgentCard
    - ``/a2a`` -- JSON-RPC endpoint for A2A protocol methods

    Args:
        agent: An ``Agent`` builder or a built ``BaseAgent`` instance.

    Usage::

        from adk_fluent import Agent, A2AServer

        # Minimal -- auto-infer everything
        app = A2AServer(Agent("helper").instruct("...")).build()

        # Full control
        app = (
            A2AServer(Agent("helper").instruct("..."))
            .port(8001)
            .provider("Acme Corp", "https://acme.com")
            .streaming(True)
            .push_notifications(True)
            .version("2.0.0")
            .docs("https://docs.acme.com")
            .build()
        )

        # Run with: uvicorn module:app --port 8001
    """

    def __init__(self, agent: Any) -> None:
        self._agent = agent
        self._host: str = "0.0.0.0"
        self._port: int = 8000
        self._protocol: str = "http"
        self._version: str = "1.0.0"
        self._provider_org: str | None = None
        self._provider_url: str | None = None
        self._streaming: bool = False
        self._push_notifications: bool = False
        self._doc_url: str | None = None
        self._card: Any = None
        self._task_store: Any = None
        self._push_store: Any = None
        self._runner: Any = None
        self._security_schemes: dict[str, Any] = {}
        self._skills: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Fluent setters (all return self for chaining)
    # ------------------------------------------------------------------

    def host(self, value: str) -> A2AServer:
        """Bind address (default ``0.0.0.0``)."""
        self._host = value
        return self

    def port(self, value: int) -> A2AServer:
        """Port number (default ``8000``)."""
        self._port = value
        return self

    def protocol(self, value: str) -> A2AServer:
        """Protocol scheme -- ``http`` or ``https`` (default ``http``)."""
        self._protocol = value
        return self

    def version(self, value: str) -> A2AServer:
        """Agent version string for the AgentCard (default ``1.0.0``)."""
        self._version = value
        return self

    def provider(self, organization: str, url: str = "") -> A2AServer:
        """Set provider metadata for the AgentCard.

        Args:
            organization: Organization name (e.g. ``"Acme Corp"``).
            url: Organization URL (e.g. ``"https://acme.com"``).
        """
        self._provider_org = organization
        self._provider_url = url
        return self

    def streaming(self, enabled: bool = True) -> A2AServer:
        """Enable SSE streaming in the AgentCard capabilities."""
        self._streaming = enabled
        return self

    def push_notifications(self, enabled: bool = True) -> A2AServer:
        """Enable push notifications in the AgentCard capabilities."""
        self._push_notifications = enabled
        return self

    def docs(self, url: str) -> A2AServer:
        """Documentation URL for the AgentCard."""
        self._doc_url = url
        return self

    def card(self, agent_card: Any) -> A2AServer:
        """Provide an explicit ``AgentCard`` object (bypasses auto-generation)."""
        self._card = agent_card
        return self

    def task_store(self, store: Any) -> A2AServer:
        """Custom task store (default: ``InMemoryTaskStore``)."""
        self._task_store = store
        return self

    def push_store(self, store: Any) -> A2AServer:
        """Custom push notification config store."""
        self._push_store = store
        return self

    def runner(self, runner: Any) -> A2AServer:
        """Provide a pre-configured ``Runner`` instance."""
        self._runner = runner
        return self

    def auth_scheme(self, name: str, scheme: Any) -> A2AServer:
        """Add a security scheme to the AgentCard.

        Args:
            name: Scheme identifier (e.g. ``"bearer"``).
            scheme: A ``SecurityScheme`` object from the ``a2a`` package.
        """
        self._security_schemes[name] = scheme
        return self

    def skill(
        self,
        id: str,
        name: str,
        *,
        description: str = "",
        tags: list[str] | None = None,
        examples: list[str] | None = None,
    ) -> A2AServer:
        """Declare an A2A skill for the AgentCard.

        Multiple calls accumulate skills. If no skills are declared,
        ``AgentCardBuilder`` auto-infers them from the agent's tools
        and instructions.
        """
        self._skills.append(
            {
                "id": id,
                "name": name,
                "description": description,
                "tags": tags or [],
                "examples": examples or [],
            }
        )
        return self

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self) -> Any:
        """Build and return a Starlette ASGI app serving the A2A protocol.

        Returns:
            A ``starlette.applications.Starlette`` instance ready for
            ``uvicorn``.

        Raises:
            ImportError: If ``google-adk[a2a]`` is not installed.
        """
        _require_a2a("A2AServer.build()")
        from google.adk.a2a.utils.agent_to_a2a import to_a2a

        # Auto-build if the agent is a builder
        agent = self._agent
        if hasattr(agent, "build") and hasattr(agent, "_config"):
            agent = agent.build()

        # Build custom AgentCard if we have provider/skill/auth config
        card = self._card
        if card is None and self._has_custom_card_config():
            card = self._build_card(agent)

        return to_a2a(
            agent=agent,
            host=self._host,
            port=self._port,
            protocol=self._protocol,
            agent_card=card,
            push_config_store=self._push_store,
            runner=self._runner,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _has_custom_card_config(self) -> bool:
        """Check if any custom card configuration was provided."""
        return bool(
            self._provider_org
            or self._skills
            or self._security_schemes
            or self._doc_url
            or self._streaming
            or self._push_notifications
        )

    def _build_card(self, agent: Any) -> Any:
        """Build an ``AgentCardBuilder`` from accumulated config.

        The builder is passed to ``to_a2a()`` which finalizes it at startup.
        """
        from a2a.types import AgentCapabilities, AgentProvider
        from google.adk.a2a.utils.agent_card_builder import AgentCardBuilder

        capabilities = AgentCapabilities(
            streaming=self._streaming,
            pushNotifications=self._push_notifications,
        )

        provider = None
        if self._provider_org:
            provider = AgentProvider(
                organization=self._provider_org,
                url=self._provider_url or "",
            )

        rpc_url = f"{self._protocol}://localhost:{self._port}/a2a"

        builder = AgentCardBuilder(
            agent=agent,
            rpc_url=rpc_url,
            capabilities=capabilities,
            doc_url=self._doc_url,
            provider=provider,
            agent_version=self._version,
            security_schemes=self._security_schemes or None,
        )
        return builder
