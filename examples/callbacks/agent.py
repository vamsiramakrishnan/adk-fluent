"""
Additive Callbacks

Converted from cookbook example: 03_callbacks.py

Usage:
    cd examples
    adk web callbacks
"""


# --- Tools & Callbacks ---

def log_before(callback_context, llm_request):
    print("before model")

def log_after(callback_context, llm_response):
    print("after model")

from adk_fluent import Agent

agent_fluent = (
    Agent("observed")
    .model("gemini-2.5-flash")
    .instruct("You are observed.")
    .before_model(log_before)
    .after_model(log_after)
    .build()
)

root_agent = agent_fluent
