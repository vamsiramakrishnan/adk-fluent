"""Dependency Injection"""

# --- NATIVE ---
import functools

from google.adk.agents.llm_agent import LlmAgent


def search_db_native(query: str, db=None) -> str:
    """Search the database."""
    return f"Results for {query} from {db}"


# Native ADK: manually wrap functions with partial or closures
# LLM sees the db parameter — not ideal
agent_native = LlmAgent(
    name="searcher",
    model="gemini-2.5-flash",
    instruction="Search for data.",
    tools=[functools.partial(search_db_native, db="my_database")],
)

# --- FLUENT ---
import inspect

from adk_fluent import Agent
from adk_fluent.di import inject_resources


def search_db(query: str, db: object) -> str:
    """Search the database."""
    return f"Results for {query} from {db}"


# .inject() hides db from LLM schema, injects at call time
agent_fluent = (
    Agent("searcher").model("gemini-2.5-flash").instruct("Search for data.").tool(search_db).inject(db="my_database")
)

# --- ASSERT ---
# inject() stores resources on the builder
assert agent_fluent._config["_resources"] == {"db": "my_database"}

# inject_resources() wraps a function and hides injected params from signature
wrapped = inject_resources(search_db, {"db": "sqlite"})
sig = inspect.signature(wrapped)
assert "query" in sig.parameters
assert "db" not in sig.parameters
