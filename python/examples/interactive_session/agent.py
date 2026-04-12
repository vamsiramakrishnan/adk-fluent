"""
Customer Support Chat Session with .session()

Converted from cookbook example: 13_interactive_session.py

Usage:
    cd examples
    adk web interactive_session
"""

from adk_fluent import Agent
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

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

root_agent = builder.build()
