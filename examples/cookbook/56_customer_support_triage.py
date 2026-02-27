"""Customer Support Triage -- ADK-Samples Inspired Multi-Tier Support

Demonstrates building a customer support triage system inspired by
real call center architectures and Google's ADK agent samples. Uses
state capture, context engineering, routing, and escalation gates.

Uses: S.capture, C.none, C.from_state, Route, gate, save_as
"""

# --- NATIVE ---
# Native ADK triage requires:
#   - 5+ LlmAgent declarations
#   - Custom BaseAgent for state capture
#   - Manual include_contents="none" for stateless classification
#   - Custom routing logic via InstructionProvider
#   - Custom escalation gate via BaseAgent + EventActions(escalate=True)
# Total: ~100 lines plus custom agent classes

# --- FLUENT ---
from adk_fluent import Agent, Pipeline, S, C, gate
from adk_fluent._routing import Route

MODEL = "gemini-2.5-flash"

# Step 1: Capture the customer's message into state
# Step 2: Classify intent without seeing prior conversation history
classifier = (
    Agent("intent_classifier")
    .model(MODEL)
    .instruct(
        "Classify the customer message into exactly one category: "
        "'billing', 'technical', 'account', or 'general'.\n"
        "Customer message: {customer_message}"
    )
    .context(C.none())  # Stateless — only sees the captured message
    .save_as("intent")
)

# Step 3: Specialized handlers for each intent
billing_handler = (
    Agent("billing_specialist")
    .model(MODEL)
    .instruct(
        "You are a billing specialist. Help the customer with payment issues, "
        "refunds, subscription changes, and invoice questions.\n"
        "Customer message: {customer_message}"
    )
    .context(C.from_state("customer_message"))
    .save_as("agent_response")
)

technical_handler = (
    Agent("tech_support")
    .model(MODEL)
    .instruct(
        "You are a technical support engineer. Diagnose the issue, "
        "suggest troubleshooting steps, and escalate if unresolvable.\n"
        "Customer message: {customer_message}"
    )
    .context(C.from_state("customer_message"))
    .save_as("agent_response")
)

account_handler = (
    Agent("account_manager")
    .model(MODEL)
    .instruct(
        "You are an account manager. Help with account access, "
        "profile updates, and security concerns.\n"
        "Customer message: {customer_message}"
    )
    .context(C.from_state("customer_message"))
    .save_as("agent_response")
)

general_handler = (
    Agent("general_support")
    .model(MODEL)
    .instruct(
        "You are a general support agent. Help with FAQs, product info, "
        "and general inquiries.\n"
        "Customer message: {customer_message}"
    )
    .context(C.user_only())
    .save_as("agent_response")
)

# Step 4: Satisfaction check with escalation gate
satisfaction_check = (
    Agent("satisfaction_monitor")
    .model(MODEL)
    .instruct(
        "Evaluate if the customer's issue was resolved satisfactorily. "
        "Set resolved to 'yes' or 'no'."
    )
    .save_as("resolved")
)

escalation_gate = gate(
    lambda s: s.get("resolved") == "no",
    message="Customer issue unresolved. Escalating to human supervisor.",
    gate_key="_escalation_gate",
)

# Compose the full triage system
support_system = (
    S.capture("customer_message")
    >> classifier
    >> Route("intent")
    .eq("billing", billing_handler)
    .eq("technical", technical_handler)
    .eq("account", account_handler)
    .otherwise(general_handler)
    >> satisfaction_check
    >> escalation_gate
)

# --- ASSERT ---
# Pipeline builds correctly
assert isinstance(support_system, Pipeline)
built = support_system.build()

# Has 5 stages: capture, classifier, router, satisfaction, gate
assert len(built.sub_agents) == 5

# First agent is CaptureAgent for S.capture()
from adk_fluent._base import CaptureAgent

assert isinstance(built.sub_agents[0], CaptureAgent)

# Classifier uses C.none() — no conversation history
classifier_agent = built.sub_agents[1]
assert classifier_agent.name == "intent_classifier"
assert classifier_agent.include_contents == "none"

# Route is configured with 4 branches
# (billing, technical, account, general as otherwise)
route_agent = built.sub_agents[2]
assert len(route_agent.sub_agents) == 4
