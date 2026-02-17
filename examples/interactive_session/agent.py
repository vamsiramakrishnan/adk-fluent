"""
Interactive Session with .session()

Converted from cookbook example: 13_interactive_session.py

Usage:
    cd examples
    adk web interactive_session
"""

from adk_fluent import Agent

# Context manager handles everything:
# async with Agent("chat").model("gemini-2.5-flash").instruct("Tutor.").session() as chat:
#     response1 = await chat.send("What is calculus?")
#     response2 = await chat.send("Give me an example.")

builder = Agent("chat").model("gemini-2.5-flash").instruct("Tutor.")

root_agent = builder.build()
