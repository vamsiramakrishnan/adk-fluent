"""Tests for concrete ModelProvider implementations.

Covers:
- GeminiProvider conforms to the ModelProvider Protocol (structural).
- provider_from_model routes model-name prefixes to the right provider.
- Optional providers (OpenAI, Anthropic) raise a clean ImportError when their
  SDK is missing, or instantiate when it is present.
- GeminiProvider.generate works against an injected fake genai client
  (no real network calls).

Optional SDKs (openai, anthropic) are dependency-gated: their full behaviour
is exercised only via injected fake clients, never live APIs.
"""

from __future__ import annotations

import importlib.util
import sys

import pytest

from adk_fluent.compute import (
    AnthropicProvider,
    GeminiProvider,
    OllamaProvider,
    OpenAIProvider,
    provider_from_model,
)
from adk_fluent.compute._protocol import (
    Chunk,
    GenerateConfig,
    GenerateResult,
    Message,
    ModelProvider,
)


def _sdk_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


# ----------------------------------------------------------------------
# Protocol conformance
# ----------------------------------------------------------------------


def test_gemini_provider_is_model_provider():
    provider = GeminiProvider("gemini-2.5-flash")
    assert isinstance(provider, ModelProvider)
    assert provider.model_id == "gemini-2.5-flash"
    assert provider.supports_tools is True
    assert provider.supports_structured_output is True


def test_ollama_provider_structural_conformance():
    # httpx is a core dependency, so this constructs without a fake client.
    provider = OllamaProvider("llama3")
    assert isinstance(provider, ModelProvider)
    assert provider.model_id == "llama3"
    assert hasattr(provider, "generate")
    assert hasattr(provider, "generate_stream")


def test_all_providers_have_required_members():
    for cls in (GeminiProvider, OpenAIProvider, AnthropicProvider, OllamaProvider):
        for member in ("model_id", "supports_tools", "supports_structured_output", "generate", "generate_stream"):
            assert hasattr(cls, member), f"{cls.__name__} missing {member}"


# ----------------------------------------------------------------------
# Factory routing
# ----------------------------------------------------------------------


def test_provider_from_model_routes_gemini():
    assert isinstance(provider_from_model("gemini-2.5-flash"), GeminiProvider)
    assert isinstance(provider_from_model("gemini-1.5-pro"), GeminiProvider)
    assert isinstance(provider_from_model("models/gemini-2.0-flash"), GeminiProvider)


def test_provider_from_model_routes_ollama_default():
    # Unknown prefixes fall through to Ollama (httpx is available).
    assert isinstance(provider_from_model("llama3"), OllamaProvider)
    assert isinstance(provider_from_model("mistral"), OllamaProvider)
    assert isinstance(provider_from_model("qwen2.5"), OllamaProvider)


def test_provider_from_model_case_insensitive():
    assert isinstance(provider_from_model("GEMINI-2.5-FLASH"), GeminiProvider)


@pytest.mark.skipif(_sdk_available("openai"), reason="openai installed")
def test_provider_from_model_openai_importerror_when_missing():
    with pytest.raises(ImportError, match="pip install openai"):
        provider_from_model("gpt-4o")
    with pytest.raises(ImportError, match="pip install openai"):
        provider_from_model("o3-mini")


@pytest.mark.skipif(_sdk_available("anthropic"), reason="anthropic installed")
def test_provider_from_model_anthropic_importerror_when_missing():
    with pytest.raises(ImportError, match="pip install anthropic"):
        provider_from_model("claude-3-5-sonnet-latest")


@pytest.mark.skipif(not _sdk_available("openai"), reason="openai not installed")
def test_provider_from_model_openai_instantiates_when_present():
    assert isinstance(provider_from_model("gpt-4o"), OpenAIProvider)


@pytest.mark.skipif(not _sdk_available("anthropic"), reason="anthropic not installed")
def test_provider_from_model_anthropic_instantiates_when_present():
    assert isinstance(provider_from_model("claude-3-5-sonnet-latest"), AnthropicProvider)


# ----------------------------------------------------------------------
# Optional-provider ImportError contract (direct construction)
# ----------------------------------------------------------------------


@pytest.mark.skipif(_sdk_available("openai"), reason="openai installed")
def test_openai_provider_importerror():
    with pytest.raises(ImportError, match="openai"):
        OpenAIProvider("gpt-4o")


@pytest.mark.skipif(_sdk_available("anthropic"), reason="anthropic installed")
def test_anthropic_provider_importerror():
    with pytest.raises(ImportError, match="anthropic"):
        AnthropicProvider("claude-3-5-sonnet-latest")


def test_optional_providers_accept_injected_client():
    # An injected client bypasses the lazy SDK import entirely.
    op = OpenAIProvider("gpt-4o", client=object())
    assert op.model_id == "gpt-4o"
    ap = AnthropicProvider("claude-3-5-sonnet-latest", client=object())
    assert ap.model_id == "claude-3-5-sonnet-latest"
    assert ap.supports_structured_output is False


# ----------------------------------------------------------------------
# GeminiProvider.generate via a fake client (no network)
# ----------------------------------------------------------------------


class _FakeUsage:
    prompt_token_count = 11
    candidates_token_count = 7


class _FakeResponse:
    text = "hello from gemini"
    usage_metadata = _FakeUsage()


class _FakeModels:
    def __init__(self):
        self.last_call = None

    async def generate_content(self, *, model, contents, config):
        self.last_call = {"model": model, "contents": contents, "config": config}
        return _FakeResponse()


class _FakeAio:
    def __init__(self):
        self.models = _FakeModels()


class _FakeGenaiClient:
    def __init__(self):
        self.aio = _FakeAio()


@pytest.mark.asyncio
async def test_gemini_generate_with_fake_client():
    fake = _FakeGenaiClient()
    provider = GeminiProvider("gemini-2.5-flash", client=fake)
    result = await provider.generate(
        [Message(role="system", content="Be terse."), Message(role="user", content="Hi")],
        config=GenerateConfig(temperature=0.3, max_tokens=64),
    )
    assert isinstance(result, GenerateResult)
    assert result.text == "hello from gemini"
    assert result.usage == {"prompt_tokens": 11, "completion_tokens": 7}
    # System message routed to system_instruction; only the user turn is in contents.
    call = fake.aio.models.last_call
    assert call["model"] == "gemini-2.5-flash"
    assert len(call["contents"]) == 1


# ----------------------------------------------------------------------
# OllamaProvider.generate via an injected fake httpx client (no network)
# ----------------------------------------------------------------------


class _FakeHttpResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "message": {"role": "assistant", "content": "ollama says hi"},
            "prompt_eval_count": 5,
            "eval_count": 9,
        }


class _FakeHttpxClient:
    def __init__(self):
        self.posted = None

    async def post(self, url, json):  # noqa: A002 - mirror httpx signature
        self.posted = {"url": url, "json": json}
        return _FakeHttpResponse()


@pytest.mark.asyncio
async def test_ollama_generate_with_fake_client():
    fake = _FakeHttpxClient()
    provider = OllamaProvider("llama3", client=fake)
    result = await provider.generate(
        [Message(role="user", content="Hi")],
        config=GenerateConfig(temperature=0.1),
    )
    assert isinstance(result, GenerateResult)
    assert result.text == "ollama says hi"
    assert result.usage == {"prompt_tokens": 5, "completion_tokens": 9}
    assert fake.posted["url"] == "/api/chat"
    assert fake.posted["json"]["stream"] is False
    assert fake.posted["json"]["options"]["temperature"] == 0.1


# ----------------------------------------------------------------------
# Chunk type sanity (streaming contract returns Chunk objects)
# ----------------------------------------------------------------------


def test_chunk_dataclass_defaults():
    c = Chunk()
    assert c.text == ""
    assert c.is_final is False


def test_provider_from_model_forwards_kwargs_to_ollama():
    provider = provider_from_model("llama3", host="http://example:1234")
    assert isinstance(provider, OllamaProvider)
    assert provider._host == "http://example:1234"


def test_module_purely_importable_without_optional_sdks():
    # Importing the providers module must never require optional SDKs.
    assert "adk_fluent.compute.providers" in sys.modules
