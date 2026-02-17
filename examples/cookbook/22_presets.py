"""Presets: Reusable Configuration Bundles"""

# --- NATIVE ---
# Native ADK has no preset mechanism. Reusing config requires:
#   base_kwargs = dict(model="gemini-2.5-flash", before_model_callback=my_cb)
#   agent1 = LlmAgent(name="a1", instruction="Do X.", **base_kwargs)
#   agent2 = LlmAgent(name="a2", instruction="Do Y.", **base_kwargs)
#
# This breaks down when you need callbacks to accumulate or
# when different builders have different alias mappings.

# --- FLUENT ---
from adk_fluent import Agent
from adk_fluent.presets import Preset


def log_before(callback_context, llm_request):
    """Log before model calls."""
    pass

def log_after(callback_context, llm_response):
    """Log after model calls."""
    pass


# Define reusable presets
production = Preset(
    model="gemini-2.5-flash",
    before_model=log_before,
    after_model=log_after,
)

# Apply to any builder with .use()
agent_a = (
    Agent("service_a")
    .instruct("Handle service A requests.")
    .use(production)
)

agent_b = (
    Agent("service_b")
    .instruct("Handle service B requests.")
    .use(production)
)

# --- ASSERT ---
# Both agents got the model from preset
assert agent_a._config["model"] == "gemini-2.5-flash"
assert agent_b._config["model"] == "gemini-2.5-flash"

# Both agents got the callbacks
assert log_before in agent_a._callbacks["before_model_callback"]
assert log_after in agent_a._callbacks["after_model_callback"]
assert log_before in agent_b._callbacks["before_model_callback"]
assert log_after in agent_b._callbacks["after_model_callback"]

# .use() returns self for chaining
assert agent_a._config["instruction"] == "Handle service A requests."
