"""
Conditional Gating with proceed_if

Converted from cookbook example: 19_conditional_gating.py

Usage:
    cd examples
    adk web conditional_gating
"""

from adk_fluent import Agent

# proceed_if: only runs if predicate(state) is truthy
enricher = (
    Agent("enricher")
    .model("gemini-2.5-flash")
    .instruct("Enrich the validated data.")
    .proceed_if(lambda s: s.get("valid") == "yes")
)

# Chain proceed_if in a pipeline: skip steps based on state
validator = Agent("validator").model("gemini-2.5-flash").instruct("Validate input.").outputs("valid")
formatter = (
    Agent("formatter")
    .model("gemini-2.5-flash")
    .instruct("Format the output.")
    .proceed_if(lambda s: s.get("valid") == "yes")
)

pipeline = validator >> enricher >> formatter

root_agent = pipeline.build()
