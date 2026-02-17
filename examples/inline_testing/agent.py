"""
Inline Testing with .test()

Converted from cookbook example: 11_inline_testing.py

Usage:
    cd examples
    adk web inline_testing
"""

from adk_fluent import Agent

# Chain tests directly into agent definition:
# agent = (
#     Agent("qa").model("gemini-2.5-flash")
#     .instruct("Answer math questions.")
#     .test("What is 2+2?", contains="4")
#     .test("What is 10*10?", contains="100")
#     .build()
# )

builder = Agent("qa").model("gemini-2.5-flash").instruct("Answer math.")

root_agent = builder.build()
