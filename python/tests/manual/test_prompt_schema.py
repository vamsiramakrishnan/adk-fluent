"""Tests for PromptSchema — typed prompt state dependency declarations."""

from __future__ import annotations

from typing import Annotated

from adk_fluent._prompt_schema import PromptSchema
from adk_fluent._schema_base import Reads


class TriagePrompt(PromptSchema):
    intent: Annotated[str, Reads()]
    confidence: Annotated[float, Reads()]
    user_tier: Annotated[str, Reads(scope="user")]


class SimplePrompt(PromptSchema):
    topic: Annotated[str, Reads()]


class EmptyPrompt(PromptSchema):
    pass


class TestPromptSchemaFields:
    def test_reads_keys(self):
        assert TriagePrompt.reads_keys() == frozenset({"intent", "confidence", "user:user_tier"})

    def test_reads_keys_simple(self):
        assert SimplePrompt.reads_keys() == frozenset({"topic"})

    def test_empty_schema(self):
        assert EmptyPrompt.reads_keys() == frozenset()

    def test_field_introspection(self):
        assert len(TriagePrompt._fields) == 3
        assert "intent" in TriagePrompt._fields

    def test_dir_includes_fields(self):
        d = dir(TriagePrompt)
        assert "intent" in d
        assert "user_tier" in d


class TestPromptSchemaBuilderIntegration:
    def test_prompt_schema_on_agent(self):
        from adk_fluent import Agent

        a = Agent("classifier").prompt_schema(TriagePrompt).instruct("Classify intent")
        ir = a.to_ir()
        assert ir.prompt_schema is TriagePrompt

    def test_prompt_schema_adds_to_reads_keys(self):
        from adk_fluent import Agent

        a = Agent("classifier").prompt_schema(TriagePrompt).instruct("Classify intent")
        ir = a.to_ir()
        assert "intent" in ir.reads_keys
        assert "confidence" in ir.reads_keys
        assert "user:user_tier" in ir.reads_keys

    def test_prompt_schema_no_writes(self):
        from adk_fluent import Agent

        a = Agent("classifier").prompt_schema(TriagePrompt).instruct("Classify")
        ir = a.to_ir()
        # PromptSchema should NOT add any writes_keys
        # (only reads — prompts don't write state)
        assert "intent" not in ir.writes_keys
        assert "confidence" not in ir.writes_keys
