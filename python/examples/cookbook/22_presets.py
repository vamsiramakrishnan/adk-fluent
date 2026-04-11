"""Enterprise Agent with Shared Compliance Preset"""

# --- NATIVE ---
# Native ADK has no preset mechanism. Reusing config requires:
#   base_kwargs = dict(model="gemini-2.5-flash", before_model_callback=audit_log)
#   agent1 = LlmAgent(name="a1", instruction="Do X.", **base_kwargs)
#   agent2 = LlmAgent(name="a2", instruction="Do Y.", **base_kwargs)
#
# This breaks down when you need callbacks to accumulate or
# when different builders have different alias mappings.

# --- FLUENT ---
from adk_fluent import Agent
from adk_fluent.presets import Preset


def audit_before_model(callback_context, llm_request):
    """Log all LLM requests for SOC2 compliance audit trail."""
    pass


def audit_after_model(callback_context, llm_response):
    """Log all LLM responses for compliance review."""
    pass


# Define a reusable compliance preset for all enterprise agents
compliance = Preset(
    model="gemini-2.5-flash",
    before_model=audit_before_model,
    after_model=audit_after_model,
)

# Apply the preset to multiple domain-specific agents with .use()
billing_agent = (
    Agent("billing_agent").instruct("Handle billing inquiries, invoices, and payment disputes.").use(compliance)
)

hr_agent = (
    Agent("hr_agent").instruct("Answer employee questions about benefits, PTO, and company policies.").use(compliance)
)

# --- ASSERT ---
# Both agents got the model from preset
assert billing_agent._config["model"] == "gemini-2.5-flash"
assert hr_agent._config["model"] == "gemini-2.5-flash"

# Both agents got the compliance audit callbacks
assert audit_before_model in billing_agent._callbacks["before_model_callback"]
assert audit_after_model in billing_agent._callbacks["after_model_callback"]
assert audit_before_model in hr_agent._callbacks["before_model_callback"]
assert audit_after_model in hr_agent._callbacks["after_model_callback"]

# .use() returns self for chaining -- instructions are preserved
assert billing_agent._config["instruction"] == "Handle billing inquiries, invoices, and payment disputes."
