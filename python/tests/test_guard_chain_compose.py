"""Guard-chain composition regression tests.

Previously, composing a transforming guard with a validating guard
(``G.pii("redact") | G.length()``) compiled two after_model callbacks, but
``_compose_callbacks`` short-circuited on the first non-None result — so the
redacted response was returned and every subsequent guard was skipped. Guards
now use edit-and-continue semantics: a transform threads forward and later
guards validate the transformed output.
"""

from unittest.mock import MagicMock

import pytest

from adk_fluent._base import _compose_callbacks


def _resp(text: str):
    part = MagicMock()
    part.text = text
    content = MagicMock()
    content.parts = [part]
    r = MagicMock()
    r.content = content
    return r


def _text(resp) -> str:
    return "\n".join(p.text for p in resp.content.parts)


@pytest.mark.asyncio
async def test_redact_then_length_both_run():
    """A redact guard must thread its result into the following length guard."""
    fns = [
        (
            "guard:pii",
            {
                "action": "redact",
                "detector": __import__("adk_fluent._guards", fromlist=["_RegexDetector"])._RegexDetector(),
                "threshold": 0.5,
                "replacement": "[PII]",
            },
        ),
        ("guard:length", {"min": 0, "max": 10_000}),
    ]
    composed = _compose_callbacks(fns)
    resp = _resp("My SSN is 123-45-6789")
    out = await composed(callback_context=MagicMock(), llm_response=resp)
    # The chain did not short-circuit: a transformed response is returned,
    # and it carries the redacted text (the length guard saw it and passed).
    assert out is not None
    assert "[PII]" in _text(out)
    assert "123-45-6789" not in _text(out)


@pytest.mark.asyncio
async def test_length_guard_runs_on_redacted_text():
    """The length guard must validate the REDACTED text, raising if too long."""
    from adk_fluent._exceptions import GuardViolation

    fns = [
        (
            "guard:pii",
            {
                "action": "redact",
                "detector": __import__("adk_fluent._guards", fromlist=["_RegexDetector"])._RegexDetector(),
                "threshold": 0.5,
                "replacement": "[PII]",
            },
        ),
        ("guard:length", {"min": 0, "max": 3}),  # redacted text exceeds 3 chars
    ]
    composed = _compose_callbacks(fns)
    resp = _resp("SSN 123-45-6789")
    with pytest.raises(GuardViolation):
        await composed(callback_context=MagicMock(), llm_response=resp)


@pytest.mark.asyncio
async def test_generic_callbacks_keep_short_circuit():
    """Non-guard callbacks keep ADK first-non-None replace-and-stop semantics."""
    calls = []

    async def cb1(**kw):
        calls.append("cb1")
        return "replaced"

    async def cb2(**kw):
        calls.append("cb2")
        return "should-not-run"

    composed = _compose_callbacks([cb1, cb2])
    out = await composed(callback_context=MagicMock(), llm_response=_resp("x"))
    assert out == "replaced"
    assert calls == ["cb1"]
