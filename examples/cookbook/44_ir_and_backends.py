"""IR and Backends"""

# --- NATIVE ---
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.sequential_agent import SequentialAgent

a = LlmAgent(name="a", model="gemini-2.5-flash", instruction="Step 1.")
b = LlmAgent(name="b", model="gemini-2.5-flash", instruction="Step 2.")
seq = SequentialAgent(name="pipeline", sub_agents=[a, b])

# --- FLUENT ---
from adk_fluent import Agent

pipeline = Agent("a").instruct("Step 1.") >> Agent("b").instruct("Step 2.")

# Inspect the IR tree (frozen dataclasses)
ir = pipeline.to_ir()

# Compile to native ADK App via IR
app = pipeline.to_app()

# .build() still works for direct agent construction
agent_fluent = pipeline.build()

# --- ASSERT ---
from adk_fluent._ir_generated import AgentNode, SequenceNode

assert isinstance(ir, SequenceNode)
assert len(ir.children) == 2
assert isinstance(ir.children[0], AgentNode)
assert ir.children[0].name == "a"
assert ir.children[1].name == "b"

# to_app() produces a native ADK App
from google.adk.apps.app import App

assert isinstance(app, App)
assert type(seq) == type(agent_fluent)
