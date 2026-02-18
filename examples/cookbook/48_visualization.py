"""Graph Visualization"""

# --- NATIVE ---
# Native ADK has no built-in visualization.
# Agent trees must be manually diagrammed.

# --- FLUENT ---
from adk_fluent import Agent

# Any builder can generate a Mermaid diagram
pipeline = Agent("classifier") >> Agent("resolver") >> Agent("responder")
mermaid = pipeline.to_mermaid()

# Build the pipeline for adk web
agent_fluent = pipeline.build()

# --- ASSERT ---
assert "graph TD" in mermaid
assert "classifier" in mermaid
assert "resolver" in mermaid
assert "responder" in mermaid
assert "-->" in mermaid

# Parallel branches also produce valid Mermaid
fanout = Agent("a") | Agent("b") | Agent("c")
fanout_mermaid = fanout.to_mermaid()
assert "graph TD" in fanout_mermaid
