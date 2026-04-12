from adk_fluent import Agent

agent = (
    Agent("helper", "gemini-2.5-flash")
    .instruct("You are a helpful assistant.")
    .describe("A helper agent")
    .writes("result")
    .build()
)
