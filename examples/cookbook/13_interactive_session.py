"""Customer Support Chat Session with .session()"""

# --- NATIVE ---
# Native ADK requires manual session lifecycle management:
#   from google.adk.agents.llm_agent import LlmAgent
#   from google.adk.runners import InMemoryRunner
#
#   agent = LlmAgent(
#       name="support_bot",
#       model="gemini-2.5-flash",
#       instruction="You are a customer support agent for an online store.",
#   )
#   runner = InMemoryRunner(agent=agent, app_name="support_app")
#   session = await runner.session_service.create_session(
#       app_name="support_app", user_id="customer_42"
#   )
#   # Then manually call runner.run_async() for each message
#   # No context manager -- you must track session/runner yourself

# --- FLUENT ---
from adk_fluent import Agent

# The fluent API wraps everything in an async context manager:
# async with (
#     Agent("support_bot")
#     .model("gemini-2.5-flash")
#     .instruct("You are a customer support agent for an online store. "
#               "Help customers with orders, returns, and product questions.")
#     .session()
# ) as chat:
#     response1 = await chat.send("I need to return an item I bought last week.")
#     response2 = await chat.send("The order number is ORD-98234.")
#     response3 = await chat.send("Thanks for the help!")

# Builder verification (no LLM call needed):
builder = (
    Agent("support_bot")
    .model("gemini-2.5-flash")
    .instruct(
        "You are a customer support agent for an online store. "
        "Help customers with orders, returns, and product questions."
    )
)

# --- ASSERT ---
assert hasattr(builder, "session")
assert callable(builder.session)
assert builder._config["name"] == "support_bot"
assert builder._config["model"] == "gemini-2.5-flash"
assert "customer support" in builder._config["instruction"]
