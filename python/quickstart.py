"""adk-fluent quickstart -- copy this file, set one env var, run."""

from adk_fluent import Agent

agent = Agent("helper", "gemini-2.5-flash").instruct("You are a helpful assistant. Be concise.")

print(agent.ask("Summarize the benefits of Python in one sentence."))
