"""Additive Callbacks"""

# --- NATIVE ---
from google.adk.agents.llm_agent import LlmAgent


def log_before(callback_context, llm_request):
    print("before model")


def log_after(callback_context, llm_response):
    print("after model")


agent_native = LlmAgent(
    name="observed",
    model="gemini-2.5-flash",
    instruction="You are observed.",
    before_model_callback=log_before,
    after_model_callback=log_after,
)

# --- FLUENT ---
from adk_fluent import Agent

agent_fluent = (
    Agent("observed")
    .model("gemini-2.5-flash")
    .instruct("You are observed.")
    .before_model(log_before)
    .after_model(log_after)
    .build()
)

# --- ASSERT ---
assert type(agent_native) == type(agent_fluent)
assert agent_native.before_model_callback == agent_fluent.before_model_callback
assert agent_native.after_model_callback == agent_fluent.after_model_callback
