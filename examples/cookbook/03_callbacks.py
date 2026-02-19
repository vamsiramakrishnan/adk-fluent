"""Content Moderation with Logging -- Additive Callbacks

Demonstrates before_model and after_model callbacks.  The scenario:
a content moderation agent where we log every request before it
reaches the model and audit every response after generation.
"""

# --- NATIVE ---
from google.adk.agents.llm_agent import LlmAgent


def log_moderation_request(callback_context, llm_request):
    """Log incoming content for audit trail before the model processes it."""
    print("[AUDIT] Moderation request received")


def check_response_safety(callback_context, llm_response):
    """Verify model output meets safety standards after generation."""
    print("[AUDIT] Response safety check passed")


agent_native = LlmAgent(
    name="content_moderator",
    model="gemini-2.5-flash",
    instruction=(
        "You are a content moderation agent. Evaluate user-submitted "
        "content and flag anything that violates community guidelines. "
        "Provide a severity rating: safe, warning, or violation."
    ),
    before_model_callback=log_moderation_request,
    after_model_callback=check_response_safety,
)

# --- FLUENT ---
from adk_fluent import Agent

agent_fluent = (
    Agent("content_moderator")
    .model("gemini-2.5-flash")
    .instruct(
        "You are a content moderation agent. Evaluate user-submitted "
        "content and flag anything that violates community guidelines. "
        "Provide a severity rating: safe, warning, or violation."
    )
    .before_model(log_moderation_request)
    .after_model(check_response_safety)
    .build()
)

# --- ASSERT ---
assert type(agent_native) == type(agent_fluent)
assert agent_native.before_model_callback == agent_fluent.before_model_callback
assert agent_native.after_model_callback == agent_fluent.after_model_callback
