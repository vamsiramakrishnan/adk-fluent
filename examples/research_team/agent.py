"""
Research team — multi-agent pipeline built with adk-fluent.

Demonstrates: Pipeline, FanOut, Loop, callbacks, tools, coordinator pattern.

Usage:
    cd examples
    adk web research_team
    adk run research_team
"""

from adk_fluent import Agent, Pipeline, FanOut, Loop


# --- Tools ---

def search_web(query: str) -> str:
    """Search the web for information."""
    return f"[Web results for '{query}': Found 3 relevant articles about {query}]"


def search_papers(query: str) -> str:
    """Search academic papers."""
    return f"[Paper results for '{query}': Found 2 papers on {query}]"


def save_draft(content: str) -> str:
    """Save a draft to storage."""
    return f"Draft saved ({len(content)} chars)"


# --- Callbacks ---

def log_agent_start(callback_context):
    """Log when each agent starts."""
    print(f"  >> Agent starting: {callback_context.agent_name}")


# --- Sub-agents ---

# 1. Research phase: search web and papers in parallel
research_phase = (
    FanOut("research")
    .describe("Search multiple sources simultaneously")
    .branch(
        Agent("web_researcher")
        .model("gemini-2.5-flash")
        .instruct("Search the web for the given topic. Summarize key findings.")
        .tool(search_web)
    )
    .branch(
        Agent("paper_researcher")
        .model("gemini-2.5-flash")
        .instruct("Search academic papers for the given topic. Cite key papers.")
        .tool(search_papers)
    )
)

# 2. Writing phase: draft then refine in a loop
writing_phase = (
    Loop("refine")
    .describe("Write and refine the article")
    .max_iterations(2)
    .step(
        Agent("writer")
        .model("gemini-2.5-flash")
        .instruct(
            "Write a comprehensive article based on the research findings. "
            "Incorporate feedback from previous iterations if available."
        )
        .tool(save_draft)
    )
    .step(
        Agent("editor")
        .model("gemini-2.5-flash")
        .instruct(
            "Review the article for clarity, accuracy, and completeness. "
            "Provide specific feedback for improvement."
        )
    )
)

# 3. Full pipeline: research -> write/refine
root_agent = (
    Pipeline("research_team")
    .describe("Research a topic, write an article, then refine it")
    .before_agent(log_agent_start)
    .step(research_phase)
    .step(writing_phase)
    .build()
)
