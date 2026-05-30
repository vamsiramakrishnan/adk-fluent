"""Concrete ``ModelProvider`` implementations.

These adapt third-party LLM SDKs to the :class:`~adk_fluent.compute._protocol.ModelProvider`
protocol so that non-ADK backends (asyncio, Temporal, …) can talk to real
models. Each provider conforms structurally to the Protocol:

- ``model_id`` / ``supports_tools`` / ``supports_structured_output`` properties
- ``async generate(messages, tools=None, config=None) -> GenerateResult``
- ``async generate_stream(messages, tools=None, config=None) -> AsyncIterator[Chunk]``

Optional SDK dependencies (``openai``, ``anthropic``) are imported lazily
inside ``__init__`` so that importing this module never fails. When an SDK is
missing, a clear ``ImportError`` with a ``pip install`` hint is raised — the
same pattern used by ``adk_fluent._guards._DLPDetector``.

The ``GeminiProvider`` uses ``google-genai`` which is already a core
dependency. ``OllamaProvider`` talks to a local Ollama server over HTTP via
``httpx``.

Use :func:`provider_from_model` to pick a provider automatically from a model
name prefix::

    provider = provider_from_model("gemini-2.5-flash")   # -> GeminiProvider
    provider = provider_from_model("gpt-4o")             # -> OpenAIProvider
    provider = provider_from_model("claude-3-5-sonnet")  # -> AnthropicProvider
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from adk_fluent.compute._protocol import (
    Chunk,
    GenerateConfig,
    GenerateResult,
    Message,
    ToolDef,
)

__all__ = [
    "GeminiProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "OllamaProvider",
    "provider_from_model",
]


# ======================================================================
# Helpers
# ======================================================================


def _config(config: GenerateConfig | None) -> GenerateConfig:
    """Return ``config`` or an empty default."""
    return config if config is not None else GenerateConfig()


def _split_system(messages: list[Message]) -> tuple[str, list[Message]]:
    """Split out leading/system messages from the conversation.

    Returns ``(system_text, non_system_messages)``. System messages are
    concatenated with newlines — most chat APIs expect a single system prompt.
    """
    system_parts: list[str] = []
    rest: list[Message] = []
    for m in messages:
        if m.role == "system":
            system_parts.append(m.content)
        else:
            rest.append(m)
    return "\n\n".join(system_parts), rest


# ======================================================================
# Gemini — google-genai (core dependency)
# ======================================================================


class GeminiProvider:
    """``ModelProvider`` backed by Google's ``google-genai`` SDK.

    ``google-genai`` is a core dependency of adk-fluent, so this provider is
    always importable. A ``genai.Client`` is created lazily on first use to
    avoid requiring credentials at construction time.
    """

    def __init__(self, model: str = "gemini-2.5-flash", *, client: Any = None) -> None:
        self._model = model
        self._client = client

    @property
    def model_id(self) -> str:
        return self._model

    @property
    def supports_tools(self) -> bool:
        return True

    @property
    def supports_structured_output(self) -> bool:
        return True

    def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                from google import genai  # type: ignore[attr-defined]
            except ImportError as exc:  # pragma: no cover - core dependency
                msg = (
                    "google-genai is required for GeminiProvider. "
                    "Install it with: pip install google-genai"
                )
                raise ImportError(msg) from exc
            self._client = genai.Client()
        return self._client

    def _build_config(self, config: GenerateConfig, system: str) -> Any:
        from google.genai import types  # type: ignore[attr-defined]

        kwargs: dict[str, Any] = {}
        if config.temperature is not None:
            kwargs["temperature"] = config.temperature
        if config.top_p is not None:
            kwargs["top_p"] = config.top_p
        if config.max_tokens is not None:
            kwargs["max_output_tokens"] = config.max_tokens
        if config.stop_sequences:
            kwargs["stop_sequences"] = list(config.stop_sequences)
        if system:
            kwargs["system_instruction"] = system
        if not kwargs:
            return None
        return types.GenerateContentConfig(**kwargs)

    def _to_contents(self, messages: list[Message]) -> tuple[str, list[Any]]:
        """Convert messages to (system_instruction, list[types.Content])."""
        from google.genai import types  # type: ignore[attr-defined]

        system, rest = _split_system(messages)
        contents: list[Any] = []
        for m in rest:
            # Gemini uses "model" for assistant turns.
            role = "model" if m.role == "assistant" else "user"
            contents.append(types.Content(role=role, parts=[types.Part(text=m.content)]))
        return system, contents

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
        config: GenerateConfig | None = None,
    ) -> GenerateResult:
        cfg = _config(config)
        client = self._ensure_client()
        system, contents = self._to_contents(messages)
        gen_config = self._build_config(cfg, system)

        response = await client.aio.models.generate_content(
            model=self._model,
            contents=contents,
            config=gen_config,
        )
        text = getattr(response, "text", None) or ""
        usage: dict[str, int] = {}
        meta = getattr(response, "usage_metadata", None)
        if meta is not None:
            usage = {
                "prompt_tokens": getattr(meta, "prompt_token_count", 0) or 0,
                "completion_tokens": getattr(meta, "candidates_token_count", 0) or 0,
            }
        return GenerateResult(text=text, usage=usage)

    async def generate_stream(
        self,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
        config: GenerateConfig | None = None,
    ) -> AsyncIterator[Chunk]:
        cfg = _config(config)
        client = self._ensure_client()
        system, contents = self._to_contents(messages)
        gen_config = self._build_config(cfg, system)

        stream = await client.aio.models.generate_content_stream(
            model=self._model,
            contents=contents,
            config=gen_config,
        )
        async for event in stream:
            yield Chunk(text=getattr(event, "text", None) or "")
        yield Chunk(is_final=True)


# ======================================================================
# OpenAI — optional dependency
# ======================================================================


class OpenAIProvider:
    """``ModelProvider`` backed by the ``openai`` SDK (optional dependency).

    Requires ``pip install openai``. The async client is created lazily so
    constructing the provider only requires the SDK to be importable, not
    valid credentials.
    """

    def __init__(self, model: str = "gpt-4o", *, client: Any = None, **client_kwargs: Any) -> None:
        self._model = model
        self._client = client
        if client is None:
            try:
                from openai import AsyncOpenAI  # type: ignore[import-not-found]
            except ImportError as exc:
                msg = (
                    "The 'openai' package is required for OpenAIProvider. "
                    "Install it with: pip install openai"
                )
                raise ImportError(msg) from exc
            self._client = AsyncOpenAI(**client_kwargs)

    @property
    def model_id(self) -> str:
        return self._model

    @property
    def supports_tools(self) -> bool:
        return True

    @property
    def supports_structured_output(self) -> bool:
        return True

    def _to_messages(self, messages: list[Message]) -> list[dict[str, str]]:
        return [{"role": m.role, "content": m.content} for m in messages]

    def _tool_params(self, tools: list[ToolDef] | None) -> dict[str, Any]:
        if not tools:
            return {}
        return {
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters or {"type": "object", "properties": {}},
                    },
                }
                for t in tools
            ]
        }

    def _completion_kwargs(
        self, messages: list[Message], tools: list[ToolDef] | None, config: GenerateConfig
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": self._to_messages(messages),
        }
        if config.temperature is not None:
            kwargs["temperature"] = config.temperature
        if config.top_p is not None:
            kwargs["top_p"] = config.top_p
        if config.max_tokens is not None:
            kwargs["max_tokens"] = config.max_tokens
        if config.stop_sequences:
            kwargs["stop"] = list(config.stop_sequences)
        kwargs.update(self._tool_params(tools))
        return kwargs

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
        config: GenerateConfig | None = None,
    ) -> GenerateResult:
        cfg = _config(config)
        kwargs = self._completion_kwargs(messages, tools, cfg)
        response = await self._client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        text = choice.message.content or ""
        tool_calls: list[dict[str, Any]] = []
        for tc in choice.message.tool_calls or []:
            tool_calls.append(
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                }
            )
        usage: dict[str, int] = {}
        if response.usage is not None:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
            }
        return GenerateResult(
            text=text,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
        )

    async def generate_stream(
        self,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
        config: GenerateConfig | None = None,
    ) -> AsyncIterator[Chunk]:
        cfg = _config(config)
        kwargs = self._completion_kwargs(messages, tools, cfg)
        kwargs["stream"] = True
        stream = await self._client.chat.completions.create(**kwargs)
        async for event in stream:
            delta = event.choices[0].delta if event.choices else None
            text = getattr(delta, "content", None) or "" if delta else ""
            if text:
                yield Chunk(text=text)
        yield Chunk(is_final=True)


# ======================================================================
# Anthropic — optional dependency
# ======================================================================


class AnthropicProvider:
    """``ModelProvider`` backed by the ``anthropic`` SDK (optional dependency).

    Requires ``pip install anthropic``. The async client is created lazily.
    Anthropic requires ``max_tokens``; a default of 4096 is used when none is
    supplied via :class:`GenerateConfig`.
    """

    DEFAULT_MAX_TOKENS = 4096

    def __init__(
        self, model: str = "claude-3-5-sonnet-latest", *, client: Any = None, **client_kwargs: Any
    ) -> None:
        self._model = model
        self._client = client
        if client is None:
            try:
                from anthropic import AsyncAnthropic  # type: ignore[import-not-found]
            except ImportError as exc:
                msg = (
                    "The 'anthropic' package is required for AnthropicProvider. "
                    "Install it with: pip install anthropic"
                )
                raise ImportError(msg) from exc
            self._client = AsyncAnthropic(**client_kwargs)

    @property
    def model_id(self) -> str:
        return self._model

    @property
    def supports_tools(self) -> bool:
        return True

    @property
    def supports_structured_output(self) -> bool:
        return False

    def _message_kwargs(
        self, messages: list[Message], tools: list[ToolDef] | None, config: GenerateConfig
    ) -> dict[str, Any]:
        system, rest = _split_system(messages)
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": config.max_tokens or self.DEFAULT_MAX_TOKENS,
            "messages": [
                {
                    "role": "assistant" if m.role == "assistant" else "user",
                    "content": m.content,
                }
                for m in rest
            ],
        }
        if system:
            kwargs["system"] = system
        if config.temperature is not None:
            kwargs["temperature"] = config.temperature
        if config.top_p is not None:
            kwargs["top_p"] = config.top_p
        if config.stop_sequences:
            kwargs["stop_sequences"] = list(config.stop_sequences)
        if tools:
            kwargs["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.parameters or {"type": "object", "properties": {}},
                }
                for t in tools
            ]
        return kwargs

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
        config: GenerateConfig | None = None,
    ) -> GenerateResult:
        cfg = _config(config)
        kwargs = self._message_kwargs(messages, tools, cfg)
        response = await self._client.messages.create(**kwargs)

        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        for block in response.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                text_parts.append(getattr(block, "text", ""))
            elif btype == "tool_use":
                tool_calls.append(
                    {
                        "id": getattr(block, "id", ""),
                        "name": getattr(block, "name", ""),
                        "arguments": getattr(block, "input", {}),
                    }
                )
        usage: dict[str, int] = {}
        if getattr(response, "usage", None) is not None:
            usage = {
                "prompt_tokens": getattr(response.usage, "input_tokens", 0),
                "completion_tokens": getattr(response.usage, "output_tokens", 0),
            }
        return GenerateResult(
            text="".join(text_parts),
            tool_calls=tool_calls,
            finish_reason=getattr(response, "stop_reason", None) or "stop",
            usage=usage,
        )

    async def generate_stream(
        self,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
        config: GenerateConfig | None = None,
    ) -> AsyncIterator[Chunk]:
        cfg = _config(config)
        kwargs = self._message_kwargs(messages, tools, cfg)
        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                if text:
                    yield Chunk(text=text)
        yield Chunk(is_final=True)


# ======================================================================
# Ollama — local HTTP server via httpx
# ======================================================================


class OllamaProvider:
    """``ModelProvider`` for a local `Ollama <https://ollama.com>`_ server.

    Talks to the Ollama HTTP API (default ``http://localhost:11434``) using
    ``httpx``. ``httpx`` is imported lazily; install it with
    ``pip install httpx`` if missing.
    """

    def __init__(
        self,
        model: str = "llama3",
        *,
        host: str = "http://localhost:11434",
        client: Any = None,
    ) -> None:
        self._model = model
        self._host = host.rstrip("/")
        self._client = client
        if client is None:
            try:
                import httpx  # type: ignore[import-not-found]  # noqa: F401
            except ImportError as exc:
                msg = (
                    "The 'httpx' package is required for OllamaProvider. "
                    "Install it with: pip install httpx"
                )
                raise ImportError(msg) from exc

    @property
    def model_id(self) -> str:
        return self._model

    @property
    def supports_tools(self) -> bool:
        return True

    @property
    def supports_structured_output(self) -> bool:
        return True

    def _payload(self, messages: list[Message], config: GenerateConfig) -> dict[str, Any]:
        options: dict[str, Any] = {}
        if config.temperature is not None:
            options["temperature"] = config.temperature
        if config.top_p is not None:
            options["top_p"] = config.top_p
        if config.max_tokens is not None:
            options["num_predict"] = config.max_tokens
        if config.stop_sequences:
            options["stop"] = list(config.stop_sequences)
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if options:
            payload["options"] = options
        return payload

    def _new_client(self) -> Any:
        import httpx  # type: ignore[import-not-found]

        return httpx.AsyncClient(base_url=self._host, timeout=120.0)

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
        config: GenerateConfig | None = None,
    ) -> GenerateResult:
        cfg = _config(config)
        payload = self._payload(messages, cfg)
        payload["stream"] = False
        client = self._client or self._new_client()
        try:
            response = await client.post("/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
        finally:
            if self._client is None:
                await client.aclose()
        text = (data.get("message") or {}).get("content", "")
        usage = {
            "prompt_tokens": data.get("prompt_eval_count", 0),
            "completion_tokens": data.get("eval_count", 0),
        }
        return GenerateResult(text=text, usage=usage)

    async def generate_stream(
        self,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
        config: GenerateConfig | None = None,
    ) -> AsyncIterator[Chunk]:
        import json

        cfg = _config(config)
        payload = self._payload(messages, cfg)
        payload["stream"] = True
        client = self._client or self._new_client()
        try:
            async with client.stream("POST", "/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    text = (data.get("message") or {}).get("content", "")
                    if text:
                        yield Chunk(text=text)
                    if data.get("done"):
                        yield Chunk(is_final=True)
                        return
        finally:
            if self._client is None:
                await client.aclose()
        yield Chunk(is_final=True)


# ======================================================================
# Factory
# ======================================================================

# Ordered (prefix, provider) routing table. First matching prefix wins.
_PREFIX_ROUTES: tuple[tuple[tuple[str, ...], type], ...] = (
    (("gemini", "models/gemini"), GeminiProvider),
    (("gpt", "o1", "o3", "o4", "chatgpt"), OpenAIProvider),
    (("claude",), AnthropicProvider),
)


def provider_from_model(model: str, **kwargs: Any) -> Any:
    """Pick a :class:`ModelProvider` from a model-name prefix.

    Routing (case-insensitive):

    - ``gemini-*`` / ``models/gemini-*`` -> :class:`GeminiProvider`
    - ``gpt-*`` / ``o1*`` / ``o3*`` / ``o4*`` / ``chatgpt*`` -> :class:`OpenAIProvider`
    - ``claude-*`` -> :class:`AnthropicProvider`

    Any other name (e.g. ``llama3``, ``mistral``, ``qwen2``) is treated as an
    Ollama model and routed to :class:`OllamaProvider`. To force a specific
    provider, construct it directly.

    Extra keyword arguments are forwarded to the chosen provider's
    constructor. Note that for the optional providers this may raise
    :class:`ImportError` if the backing SDK is not installed.
    """
    lowered = model.lower()
    for prefixes, provider_cls in _PREFIX_ROUTES:
        if any(lowered.startswith(p) for p in prefixes):
            return provider_cls(model, **kwargs)
    # Default: treat as a local Ollama model.
    return OllamaProvider(model, **kwargs)
