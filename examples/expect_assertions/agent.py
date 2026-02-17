"""
Expect: State Contract Assertions in Pipelines

Converted from cookbook example: 36_expect_assertions.py

Usage:
    cd examples
    adk web expect_assertions
"""

from adk_fluent import Agent, Pipeline, expect
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# expect(): assert a state contract at a pipeline step
# Raises ValueError with your message if predicate fails
pipeline_fluent = (
    Agent("writer").model("gemini-2.5-flash").instruct("Write a draft.").outputs("draft")
    >> expect(lambda s: "draft" in s, "Draft must exist before review")
    >> Agent("reviewer").model("gemini-2.5-flash").instruct("Review the draft.")
)

# Multiple expectations in a pipeline
validated_pipeline = (
    Agent("extractor").model("gemini-2.5-flash").instruct("Extract entities.")
    >> expect(lambda s: "entities" in s, "Extraction must produce entities")
    >> Agent("enricher").model("gemini-2.5-flash").instruct("Enrich entities.")
    >> expect(lambda s: len(s.get("entities", "")) > 0, "Entities must not be empty")
    >> Agent("formatter").model("gemini-2.5-flash").instruct("Format output.")
)

root_agent = validated_pipeline.build()
