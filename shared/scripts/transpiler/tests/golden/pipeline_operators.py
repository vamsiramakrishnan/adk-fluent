from adk_fluent import Agent, S

writer = Agent("writer", "gemini-2.5-flash").instruct("Write a draft.").writes("draft")

reviewer = Agent("reviewer", "gemini-2.5-flash").instruct("Review the {draft}.")

pipeline = (writer >> reviewer) * 3

fallback = Agent("fast", "gemini-2.5-flash") // Agent("strong", "gemini-2.5-pro")

fanout = Agent("web").instruct("Search web.") | Agent("papers").instruct("Search papers.")
