"""Compute layer protocols — abstractions over infrastructure concerns.

These protocols decouple WHERE work happens from HOW it's orchestrated
(backends) and WHAT the agent does (builders/IR).

Protocols:
- ``ModelProvider``: LLM API abstraction (Gemini, OpenAI, Anthropic, Ollama)
- ``StateStore``: Session/state persistence (memory, SQLite, Redis, DynamoDB)
- ``ToolRuntime``: Tool execution environment (local, sandboxed, remote)
- ``ArtifactStore``: Artifact persistence (memory, filesystem, GCS)
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "ModelProvider",
    "StateStore",
    "ToolRuntime",
    "ArtifactStore",
    "Message",
    "ToolDef",
    "GenerateConfig",
    "GenerateResult",
    "Chunk",
]


# ======================================================================
# Data types for ModelProvider
# ======================================================================


@dataclass
class Message:
    """A message in a conversation."""

    role: str  # "user", "assistant", "system", "tool"
    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolDef:
    """A tool definition for the LLM."""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)  # JSON Schema
    fn: Callable | None = None  # The actual callable (not sent to LLM)


@dataclass
class GenerateConfig:
    """Configuration for a generation request."""

    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    stop_sequences: list[str] = field(default_factory=list)
    response_format: Any = None  # JSON schema or Pydantic model
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerateResult:
    """Result of a generation request."""

    text: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)  # prompt_tokens, completion_tokens
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


@dataclass
class Chunk:
    """A streaming chunk from an LLM."""

    text: str = ""
    is_final: bool = False
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# ======================================================================
# Protocols
# ======================================================================


@runtime_checkable
class ModelProvider(Protocol):
    """Abstraction over LLM providers.

    Implementations: GeminiProvider, OpenAIProvider, AnthropicProvider,
    OllamaProvider, etc.

    The ADK backend ignores this and uses ADK's native model handling.
    Other backends (asyncio, Temporal) use it directly.
    """

    @property
    def model_id(self) -> str:
        """The model identifier (e.g., "gemini-2.5-flash")."""
        ...

    @property
    def supports_tools(self) -> bool:
        """Whether this provider supports tool/function calling."""
        ...

    @property
    def supports_structured_output(self) -> bool:
        """Whether this provider supports structured JSON output."""
        ...

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
        config: GenerateConfig | None = None,
    ) -> GenerateResult:
        """Generate a response from the model."""
        ...

    async def generate_stream(
        self,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
        config: GenerateConfig | None = None,
    ) -> AsyncIterator[Chunk]:
        """Stream chunks from the model."""
        ...


@runtime_checkable
class StateStore(Protocol):
    """Abstraction over session/state persistence.

    Implementations: InMemoryStateStore, SqliteStateStore, RedisStateStore,
    DynamoDBStateStore, etc.

    The ADK backend uses ADK's SessionService internally. Other backends
    use StateStore directly.
    """

    async def create(self, namespace: str, **initial_state: Any) -> str:
        """Create a new session. Returns session_id."""
        ...

    async def load(self, session_id: str) -> dict[str, Any]:
        """Load state for a session."""
        ...

    async def save(self, session_id: str, state: dict[str, Any]) -> None:
        """Save state for a session."""
        ...

    async def delete(self, session_id: str) -> None:
        """Delete a session."""
        ...

    async def list_sessions(self, namespace: str) -> list[str]:
        """List session IDs in a namespace."""
        ...


@runtime_checkable
class ToolRuntime(Protocol):
    """Abstraction over tool execution environments.

    Implementations: LocalToolRuntime (default), SandboxedToolRuntime,
    RemoteToolRuntime, etc.
    """

    async def execute(
        self,
        tool_name: str,
        fn: Callable,
        args: dict[str, Any],
    ) -> Any:
        """Execute a tool function with the given arguments."""
        ...


@runtime_checkable
class ArtifactStore(Protocol):
    """Abstraction over artifact persistence.

    Implementations: InMemoryArtifactStore, FileArtifactStore,
    GcsArtifactStore, etc.
    """

    async def save(
        self,
        key: str,
        data: bytes,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Save an artifact. Returns version number."""
        ...

    async def load(
        self,
        key: str,
        version: int | None = None,
    ) -> bytes:
        """Load an artifact by key and optional version."""
        ...

    async def list_versions(self, key: str) -> list[int]:
        """List available versions for an artifact."""
        ...

    async def delete(self, key: str, version: int | None = None) -> None:
        """Delete an artifact (specific version or all)."""
        ...
