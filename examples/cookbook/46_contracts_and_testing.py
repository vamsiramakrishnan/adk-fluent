"""Contracts and Testing"""

# --- NATIVE ---
# Native ADK has no built-in contract verification or mock testing.
# Pipeline data flow errors are discovered at runtime.

# --- FLUENT ---
from pydantic import BaseModel

from adk_fluent import Agent
from adk_fluent.testing import MockBackend, check_contracts, mock_backend


class Intent(BaseModel):
    category: str
    confidence: float


# 1. Declare data contracts
pipeline = Agent("classifier").produces(Intent) >> Agent("resolver").consumes(Intent)

# 2. Verify at build time (no LLM calls)
issues = check_contracts(pipeline.to_ir())

# 3. Create a mock backend for deterministic testing
mb = mock_backend({"classifier": {"category": "billing", "confidence": 0.95}, "resolver": "Done."})

# --- ASSERT ---
# Contract verification passes — classifier produces what resolver consumes
assert issues == []

# Mock backend satisfies the Backend protocol
from adk_fluent.backends import Backend

assert isinstance(mb, Backend)

# Catch contract violations: resolver consumes Intent but nothing produces it
bad_pipeline = Agent("a") >> Agent("resolver").consumes(Intent)
bad_issues = check_contracts(bad_pipeline.to_ir())
assert len(bad_issues) == 2  # category and confidence missing
assert "category" in bad_issues[0]
