"""Mock Testing: Customer Onboarding Pipeline with Deterministic Mocks"""

# --- NATIVE ---
# Native ADK uses before_model_callback to bypass the LLM during tests:
#
#   from google.adk.models.llm_response import LlmResponse
#   from google.genai import types
#
#   def mock_callback(callback_context, llm_request):
#       return LlmResponse(
#           content=types.Content(
#               role="model",
#               parts=[types.Part(text="KYC: approved")]
#           )
#       )
#
#   kyc_agent = LlmAgent(
#       name="kyc_verifier", model="gemini-2.5-flash",
#       instruction="Verify customer KYC documents.",
#       before_model_callback=mock_callback,
#   )
#
# For a multi-step onboarding pipeline, you'd need one callback per agent,
# making test setup verbose and fragile.

# --- FLUENT ---
from adk_fluent import Agent

# Scenario: Customer onboarding pipeline with three stages:
#   1. KYC verification -- checks identity documents
#   2. Risk assessment -- evaluates financial risk profile
#   3. Account provisioning -- creates the customer account

# .mock(list): cycle through scripted responses for repeatable tests
kyc_verifier = (
    Agent("kyc_verifier")
    .model("gemini-2.5-flash")
    .instruct("Verify the customer's identity documents and return approval status.")
    .outputs("kyc_status")
    .mock(["KYC: approved", "KYC: pending review"])
)

# .mock(callable): dynamic responses based on the LLM request context
risk_assessor = (
    Agent("risk_assessor")
    .model("gemini-2.5-flash")
    .instruct("Evaluate the customer's financial risk profile.")
    .outputs("risk_level")
    .mock(lambda req: "risk_level: low")
)

# Chainable -- .mock() returns self so it composes with other builder methods
account_provisioner = (
    Agent("account_provisioner")
    .model("gemini-2.5-flash")
    .mock(["Account ACT-10042 created successfully."])
    .instruct("Provision a new bank account for the approved customer.")
    .outputs("account_id")
)

# Full onboarding pipeline with all agents mocked for integration testing
onboarding_pipeline = kyc_verifier >> risk_assessor >> account_provisioner

# --- ASSERT ---
from google.adk.models.llm_response import LlmResponse

# .mock(list) registers a before_model_callback
assert len(kyc_verifier._callbacks["before_model_callback"]) == 1

# The callback returns LlmResponse (bypasses the actual LLM)
cb = kyc_verifier._callbacks["before_model_callback"][0]
result = cb(callback_context=None, llm_request=None)
assert isinstance(result, LlmResponse)
assert result.content.parts[0].text == "KYC: approved"

# List responses cycle through deterministically
r2 = cb(None, None)
assert r2.content.parts[0].text == "KYC: pending review"
r3 = cb(None, None)
assert r3.content.parts[0].text == "KYC: approved"  # cycles back

# .mock(callable) also registers a callback
assert len(risk_assessor._callbacks["before_model_callback"]) == 1
cb_fn = risk_assessor._callbacks["before_model_callback"][0]
result_fn = cb_fn(None, None)
assert result_fn.content.parts[0].text == "risk_level: low"

# Chainable: .mock() returns self, preserving all builder state
assert account_provisioner._config["instruction"] == "Provision a new bank account for the approved customer."
assert account_provisioner._config["output_key"] == "account_id"
