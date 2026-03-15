"""Server: Publish a specialist agent via A2A.

Run::

    pip install adk-fluent[a2a]
    uvicorn examples.a2a_remote_delegation.server:app --port 8001

The agent card is auto-generated and served at:
    http://localhost:8001/.well-known/agent.json
"""

from adk_fluent import Agent, A2AServer


def web_search(query: str) -> str:
    """Search the web for information."""
    return f"Search results for: {query}"


# ---------------------------------------------------------------------------
# Option 1: Ultra-concise one-liner
# ---------------------------------------------------------------------------

# app = (
#     Agent("researcher", "gemini-2.5-flash")
#     .instruct("You are a research specialist. Provide thorough, cited answers.")
#     .tool(web_search)
#     .publish(port=8001)
# )

# ---------------------------------------------------------------------------
# Option 2: Full control with A2AServer
# ---------------------------------------------------------------------------

researcher = (
    Agent("researcher", "gemini-2.5-flash")
    .instruct(
        "You are a research specialist. Provide thorough, well-cited answers "
        "to research questions. Always include sources."
    )
    .tool(web_search)
    .skill(
        "research",
        "Academic Research",
        description="Deep research with citations and source verification",
        tags=["research", "academic", "citations"],
        examples=[
            "Find recent papers on transformer architectures",
            "What are the latest advances in quantum computing?",
        ],
    )
)

app = (
    A2AServer(researcher)
    .port(8001)
    .provider("Research Lab", "https://research-lab.example.com")
    .streaming(True)
    .version("1.0.0")
    .docs("https://research-lab.example.com/docs")
    .build()
)
