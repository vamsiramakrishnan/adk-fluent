"""Visibility Policies for Multi-Agent Pipelines"""

# --- NATIVE ---
# Native ADK shows all agent outputs to users. There is no built-in
# mechanism to suppress intermediate agent events.

# --- FLUENT ---
from adk_fluent import Agent
from adk_fluent._visibility import infer_visibility

MODEL = "gemini-2.5-flash"

# Build a 3-agent pipeline
pipeline = (
    Agent("drafter").model(MODEL).instruct("Write a draft.")
    >> Agent("reviewer").model(MODEL).instruct("Review the draft.")
    >> Agent("editor").model(MODEL).instruct("Produce final version.")
)

# Infer visibility from topology
ir = pipeline.to_ir()
vis = infer_visibility(ir)

# Pipeline-level policies
debug_pipeline = (
    Agent("a").model(MODEL).instruct("Step 1.")
    >> Agent("b").model(MODEL).instruct("Step 2.")
)
debug_pipeline.transparent()

prod_pipeline = (
    Agent("a").model(MODEL).instruct("Step 1.")
    >> Agent("b").model(MODEL).instruct("Step 2.")
)
prod_pipeline.filtered()

# Per-agent overrides
shown = Agent("logger").model(MODEL).instruct("Log.").show()
hidden = Agent("cleanup").model(MODEL).instruct("Clean.").hide()

# --- ASSERT ---
# Terminal agent is user-facing, intermediate agents are internal
assert vis["drafter"] == "internal"
assert vis["reviewer"] == "internal"
assert vis["editor"] == "user"

# Policy methods set config
assert debug_pipeline._config["_visibility_policy"] == "transparent"
assert prod_pipeline._config["_visibility_policy"] == "filtered"

# Per-agent overrides set config
assert shown._config["_visibility_override"] == "user"
assert hidden._config["_visibility_override"] == "internal"
