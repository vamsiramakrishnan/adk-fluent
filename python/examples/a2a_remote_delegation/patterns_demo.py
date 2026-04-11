"""Demonstrate A2A composition patterns.

Shows how RemoteAgent composes with all adk-fluent operators and
higher-order patterns.
"""

from adk_fluent import Agent, RemoteAgent
from adk_fluent.patterns import (
    a2a_cascade,
    a2a_delegate,
    a2a_fanout,
    fan_out_merge,
    review_loop,
)

# ---------------------------------------------------------------------------
# Pattern 1: Fallback chain across remote models
# ---------------------------------------------------------------------------

fallback = a2a_cascade(
    "http://fast-model:8001",
    "http://accurate-model:8002",
    "http://fallback-model:8003",
    names=["fast", "accurate", "fallback"],
)

# ---------------------------------------------------------------------------
# Pattern 2: Parallel research fan-out
# ---------------------------------------------------------------------------

parallel_research = a2a_fanout(
    "http://web-search:8001",
    "http://paper-search:8002",
    "http://patent-search:8003",
    names=["web", "papers", "patents"],
)

# ---------------------------------------------------------------------------
# Pattern 3: Named delegation to remote specialists
# ---------------------------------------------------------------------------

coordinator = a2a_delegate(
    Agent("coordinator", "gemini-2.5-flash").instruct(
        "Route tasks to the right specialist based on the user's request."
    ),
    research="http://research:8001",
    writing="http://writing:8002",
    analysis="http://analysis:8003",
)

# ---------------------------------------------------------------------------
# Pattern 4: Hybrid local + remote with fallback
# ---------------------------------------------------------------------------

hybrid = RemoteAgent("fast", "http://fast:8001").timeout(10) // Agent("local", "gemini-2.5-flash").instruct(
    "Fallback: answer locally."
)

# ---------------------------------------------------------------------------
# Pattern 5: Remote agent in a review loop
# ---------------------------------------------------------------------------

loop = review_loop(
    worker=Agent("writer", "gemini-2.5-flash").instruct("Write a draft article about {topic}.").writes("draft"),
    reviewer=RemoteAgent("expert", "http://expert-reviewer:8001").describe(
        "Expert reviewer who evaluates draft quality."
    ),
    quality_key="quality",
    target="excellent",
    max_rounds=3,
)

# ---------------------------------------------------------------------------
# Pattern 6: Mixed local/remote fan-out with merge
# ---------------------------------------------------------------------------

merged_research = fan_out_merge(
    RemoteAgent("web", "http://web:8001").writes("web_results"),
    Agent("local_db", "gemini-2.5-flash").instruct("Query internal database for {topic}.").writes("db_results"),
    RemoteAgent("papers", "http://papers:8002").writes("paper_results"),
    merge_key="all_research",
)

# ---------------------------------------------------------------------------
# Pattern 7: T.a2a() -- remote agent as a tool
# ---------------------------------------------------------------------------

from adk_fluent import T

agent_with_remote_tool = (
    Agent("coordinator", "gemini-2.5-flash")
    .instruct("Use the research tool for deep questions.")
    .tools(T.a2a("http://research:8001", name="deep_research", description="Deep research tool"))
    .build()
)
