"""Uniform Declarative Schemas — ToolSchema, CallbackSchema, PredicateSchema, PromptSchema.

Demonstrates how to declare typed state dependencies for tools, callbacks,
predicates, and prompts using the same Annotated-hint pattern as StateSchema.
"""

from __future__ import annotations

from typing import Annotated

from adk_fluent import (
    Agent,
    Route,
    StateSchema,
    Scoped,
    ToolSchema,
    CallbackSchema,
    PredicateSchema,
    PromptSchema,
    Reads,
    Writes,
    Param,
)
from adk_fluent.testing.contracts import check_contracts


# ── State Schema (existing pattern) ──────────────────────────────────


class TriageState(StateSchema):
    intent: str
    confidence: float
    user_tier: Annotated[str, Scoped("user")]
    ticket_id: str | None = None


# ── Tool Schema (NEW) ────────────────────────────────────────────────


class SearchTools(ToolSchema):
    query: Annotated[str, Reads()]
    user_tier: Annotated[str, Reads(scope="user")]
    results: Annotated[list, Writes()]
    max_results: Annotated[int, Param()] = 10


# ── Callback Schema (NEW) ────────────────────────────────────────────


class AuditCallbacks(CallbackSchema):
    intent: Annotated[str, Reads()]
    audit_log: Annotated[list, Writes()]


# ── Predicate Schema (NEW) ───────────────────────────────────────────


class HighConfidence(PredicateSchema):
    confidence: Annotated[float, Reads()]

    @staticmethod
    def evaluate(confidence: float) -> bool:
        return confidence >= 0.8


# ── Prompt Schema (NEW) ──────────────────────────────────────────────


class SearchPrompt(PromptSchema):
    intent: Annotated[str, Reads()]
    user_tier: Annotated[str, Reads(scope="user")]


# ── Pipeline ─────────────────────────────────────────────────────────

classifier = Agent("classifier").save_as("confidence").instruct("Classify the user's intent and confidence.")

searcher = (
    Agent("searcher").tool_schema(SearchTools).prompt_schema(SearchPrompt).instruct("Search for relevant documents.")
)

processor = Agent("processor").callback_schema(AuditCallbacks).instruct("Process and respond.")

pipeline = classifier >> Route("confidence").when(HighConfidence, searcher >> processor).otherwise(
    Agent("fallback").instruct("Ask for clarification.")
)

# ── Contract check ───────────────────────────────────────────────────

issues = check_contracts(pipeline.to_ir())
for issue in issues:
    if isinstance(issue, dict):
        print(f"  [{issue['level']}] {issue['agent']}: {issue['message']}")
    else:
        print(f"  {issue}")

if not issues:
    print("All contracts satisfied!")

# ── Introspection ────────────────────────────────────────────────────

print()
print("SearchTools:")
print(f"  reads:  {SearchTools.reads_keys()}")
print(f"  writes: {SearchTools.writes_keys()}")
print(f"  params: {SearchTools.param_names()}")

print("AuditCallbacks:")
print(f"  reads:  {AuditCallbacks.reads_keys()}")
print(f"  writes: {AuditCallbacks.writes_keys()}")

print("HighConfidence:")
print(f"  reads:    {HighConfidence.reads_keys()}")
print(f"  evaluate: {HighConfidence({'confidence': 0.9})}")

print("SearchPrompt:")
print(f"  reads:  {SearchPrompt.reads_keys()}")
