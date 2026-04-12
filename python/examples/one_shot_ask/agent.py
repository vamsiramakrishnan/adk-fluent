"""
Quick Code Review -- One-Shot Execution with .ask()

Demonstrates the .ask() convenience method for fire-and-forget
queries.  The scenario: a code review agent that can be invoked
with a single line to get feedback on a code snippet.
No LLM calls are made here -- we only verify builder mechanics.

Converted from cookbook example: 08_one_shot_ask.py

Usage:
    cd examples
    adk web one_shot_ask
"""

from adk_fluent import Agent
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# In production, one line is all you need:
# feedback = (
#     Agent("code_reviewer")
#     .model("gemini-2.5-flash")
#     .instruct("Review code for bugs, style issues, and security vulnerabilities.")
#     .ask("Review this: def f(x): return x+1")
# )

# Builder mechanics verification (no LLM call):
builder = (
    Agent("code_reviewer")
    .model("gemini-2.5-flash")
    .instruct(
        "Review code for bugs, style issues, and security vulnerabilities. "
        "Focus on correctness, readability, and potential edge cases."
    )
)

root_agent = builder.build()
