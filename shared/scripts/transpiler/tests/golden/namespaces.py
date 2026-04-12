from adk_fluent import Agent, S, C, P

agent = (
    Agent("analyst", "gemini-2.5-flash")
    .instruct(
        P.role("Senior data analyst")
        + P.task("Analyze the dataset")
        + P.constraint("Be concise", "Use tables")
    )
    .context(C.none())
    .build()
)

transform = S.pick("summary", "confidence")
