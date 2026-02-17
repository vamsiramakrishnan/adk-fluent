"""
Streaming with .stream()

Converted from cookbook example: 09_streaming.py

Usage:
    cd examples
    adk web streaming
"""

from adk_fluent import Agent
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# Streaming in one line:
# async for chunk in Agent("s").model("gemini-2.5-flash").instruct("Tell stories.").stream("Once upon a time"):
#     print(chunk, end="")

builder = Agent("s").model("gemini-2.5-flash").instruct("Tell stories.")

root_agent = builder.build()
