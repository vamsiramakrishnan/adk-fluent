"""Client: Orchestrator that delegates to remote A2A specialists.

Assumes server.py is running on port 8001::

    uvicorn examples.a2a_remote_delegation.server:app --port 8001

Then run this client normally.
"""

from adk_fluent import Agent, RemoteAgent, Route

# ---------------------------------------------------------------------------
# Consume a remote A2A agent -- one line
# ---------------------------------------------------------------------------

research = RemoteAgent("research", "http://localhost:8001")

# ---------------------------------------------------------------------------
# Option 1: Sub-agent delegation (LLM decides when to delegate)
# ---------------------------------------------------------------------------

coordinator = (
    Agent("coordinator", "gemini-2.5-flash")
    .instruct(
        "You are a coordinator. For research questions, delegate to the "
        "research specialist. Handle casual questions yourself."
    )
    .sub_agent(research)
    .build()
)

# ---------------------------------------------------------------------------
# Option 2: Operator composition (pipeline)
# ---------------------------------------------------------------------------

pipeline = Agent("classifier", "gemini-2.5-flash").instruct("Classify.") >> research

# ---------------------------------------------------------------------------
# Option 3: Deterministic routing (no LLM cost for routing)
# ---------------------------------------------------------------------------

router = Agent("classifier", "gemini-2.5-flash").instruct(
    "Classify the user request as 'research' or 'general'."
).writes("intent") >> Route("intent").eq("research", RemoteAgent("research", "http://localhost:8001")).otherwise(
    Agent("general", "gemini-2.5-flash").instruct("Answer generally.")
)

# ---------------------------------------------------------------------------
# Option 4: Fallback -- try remote first, fall back to local
# ---------------------------------------------------------------------------

fallback = RemoteAgent("research", "http://localhost:8001").timeout(10) // Agent("local", "gemini-2.5-flash").instruct(
    "Answer as best you can."
)

# ---------------------------------------------------------------------------
# Option 5: RemoteAgent with discovery
# ---------------------------------------------------------------------------

from adk_fluent import RemoteAgent as RA

discovered = RA.discover("research", "research.agents.acme.com")
pipeline_v2 = Agent("coordinator") >> discovered
