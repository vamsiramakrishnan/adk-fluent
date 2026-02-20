"""Senior Architect Delegates to Junior Specialists (LLM-Driven Routing)"""

# --- NATIVE ---
from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.agent_tool import AgentTool

# Native: manually create an AgentTool for each specialist
database_specialist = LlmAgent(
    name="database_specialist",
    model="gemini-2.5-flash",
    instruction=(
        "You are a database architecture specialist. Design schemas, "
        "optimize queries, and recommend indexing strategies."
    ),
)

coordinator_native = LlmAgent(
    name="tech_lead",
    model="gemini-2.5-flash",
    instruction=(
        "You are a senior tech lead. Analyze architecture requests and delegate to the appropriate specialist."
    ),
    tools=[AgentTool(agent=database_specialist)],
)

# --- FLUENT ---
from adk_fluent import Agent

# Junior specialists — each focused on a specific domain
db_expert = (
    Agent("database_specialist")
    .model("gemini-2.5-flash")
    .instruct(
        "You are a database architecture specialist. Design schemas, "
        "optimize queries, and recommend indexing strategies."
    )
)

frontend_expert = (
    Agent("frontend_specialist")
    .model("gemini-2.5-flash")
    .instruct(
        "You are a frontend architecture specialist. Design component "
        "hierarchies, state management patterns, and performance optimizations."
    )
)

# .delegate() wraps each agent as AgentTool — the senior architect's LLM
# decides when to delegate (LLM-driven routing, unlike Route which is deterministic)
senior_architect = (
    Agent("senior_architect")
    .model("gemini-2.5-flash")
    .instruct(
        "You are a senior software architect. Analyze incoming architecture "
        "requests and delegate to the appropriate specialist based on the "
        "technical domain involved."
    )
    .delegate(db_expert)
    .delegate(frontend_expert)
)

# --- ASSERT ---
# delegate adds to tools list
assert len(senior_architect._lists["tools"]) == 2

# Each tool is an AgentTool wrapping the built specialist
built = senior_architect.build()
assert len(built.tools) == 2
assert all(isinstance(t, AgentTool) for t in built.tools)
