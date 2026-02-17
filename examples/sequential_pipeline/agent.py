"""
Sequential Pipeline

Converted from cookbook example: 04_sequential_pipeline.py

Usage:
    cd examples
    adk web sequential_pipeline
"""

from adk_fluent import Agent, Pipeline

pipeline_fluent = (
    Pipeline("blog_pipeline")
    .describe("Research then write")
    .step(Agent("researcher").model("gemini-2.5-flash").instruct("Research the topic."))
    .step(Agent("writer").model("gemini-2.5-flash").instruct("Write a summary."))
    .build()
)

root_agent = pipeline_fluent
