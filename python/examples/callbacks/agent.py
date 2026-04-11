"""
Content Moderation with Logging -- Additive Callbacks

Demonstrates before_model and after_model callbacks.  The scenario:
a content moderation agent where we log every request before it
reaches the model and audit every response after generation.

Converted from cookbook example: 03_callbacks.py

Usage:
    cd examples
    adk web callbacks
"""


# --- Tools & Callbacks ---


def log_moderation_request(callback_context, llm_request):
    """Log incoming content for audit trail before the model processes it."""
    print("[AUDIT] Moderation request received")


def check_response_safety(callback_context, llm_response):
    """Verify model output meets safety standards after generation."""
    print("[AUDIT] Response safety check passed")


from adk_fluent import Agent
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

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

root_agent = agent_fluent
