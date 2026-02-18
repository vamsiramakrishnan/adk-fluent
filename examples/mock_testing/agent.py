"""
Mock: Bypass LLM Calls for Testing

Converted from cookbook example: 37_mock_testing.py

Usage:
    cd examples
    adk web mock_testing
"""

from adk_fluent import Agent
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# .mock(list): cycle through canned responses
agent_list = (
    Agent("writer").model("gemini-2.5-flash").instruct("Write a story.").mock(["Once upon a time...", "The end."])
)

# .mock(callable): dynamic response based on the LLM request
agent_fn = (
    Agent("echo").model("gemini-2.5-flash").instruct("Echo the user's message.").mock(lambda req: "Mocked: I heard you")
)

# Chainable -- .mock() returns self
agent_chained = (
    Agent("analyzer")
    .model("gemini-2.5-flash")
    .mock(["Analysis complete."])
    .instruct("Analyze the data.")
    .outputs("analysis")
)

root_agent = agent_chained.build()
