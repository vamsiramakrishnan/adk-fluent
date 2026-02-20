"""Customer Service Hub: Agent Transfer Control

Demonstrates controlling how agents transfer between each other using
disallow_transfer_to_parent, disallow_transfer_to_peers, and the
.isolate() convenience method.  The scenario: a customer service system
where a coordinator routes to specialist agents that must complete their
task before returning control.
"""

# --- NATIVE ---
from google.adk.agents.llm_agent import LlmAgent

billing_native = LlmAgent(
    name="billing_specialist",
    model="gemini-2.5-flash",
    instruction=(
        "You handle billing inquiries: refunds, payment disputes, "
        "invoice corrections, and subscription changes. Resolve the "
        "issue completely before finishing."
    ),
    description="Handles billing, payment, and subscription issues",
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)

technical_native = LlmAgent(
    name="technical_specialist",
    model="gemini-2.5-flash",
    instruction=(
        "You handle technical support: bug reports, integration issues, "
        "API errors, and configuration problems. Walk the customer "
        "through troubleshooting steps."
    ),
    description="Handles technical support and troubleshooting",
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)

general_native = LlmAgent(
    name="general_support",
    model="gemini-2.5-flash",
    instruction=(
        "You handle general inquiries: account information, product "
        "questions, and feedback. You may transfer back to the "
        "coordinator if the issue requires a specialist."
    ),
    description="Handles general inquiries and account questions",
)

coordinator_native = LlmAgent(
    name="service_coordinator",
    model="gemini-2.5-flash",
    instruction=(
        "You are the front-line customer service coordinator. Greet the "
        "customer, understand their issue, and route to the right "
        "specialist: billing for payment issues, technical for bugs "
        "and integrations, or general for everything else."
    ),
    sub_agents=[billing_native, technical_native, general_native],
)

# --- FLUENT ---
from adk_fluent import Agent

# Using explicit .disallow_transfer_to_parent() and .disallow_transfer_to_peers()
billing_explicit = (
    Agent("billing_specialist")
    .model("gemini-2.5-flash")
    .instruct(
        "You handle billing inquiries: refunds, payment disputes, "
        "invoice corrections, and subscription changes. Resolve the "
        "issue completely before finishing."
    )
    .describe("Handles billing, payment, and subscription issues")
    .disallow_transfer_to_parent(True)
    .disallow_transfer_to_peers(True)
)

# Using .isolate() -- sets both flags in one call
billing_isolated = (
    Agent("billing_specialist")
    .model("gemini-2.5-flash")
    .instruct(
        "You handle billing inquiries: refunds, payment disputes, "
        "invoice corrections, and subscription changes. Resolve the "
        "issue completely before finishing."
    )
    .describe("Handles billing, payment, and subscription issues")
    .isolate()
)

technical_fluent = (
    Agent("technical_specialist")
    .model("gemini-2.5-flash")
    .instruct(
        "You handle technical support: bug reports, integration issues, "
        "API errors, and configuration problems. Walk the customer "
        "through troubleshooting steps."
    )
    .describe("Handles technical support and troubleshooting")
    .isolate()
)

general_fluent = (
    Agent("general_support")
    .model("gemini-2.5-flash")
    .instruct(
        "You handle general inquiries: account information, product "
        "questions, and feedback. You may transfer back to the "
        "coordinator if the issue requires a specialist."
    )
    .describe("Handles general inquiries and account questions")
)

coordinator_fluent = (
    Agent("service_coordinator")
    .model("gemini-2.5-flash")
    .instruct(
        "You are the front-line customer service coordinator. Greet the "
        "customer, understand their issue, and route to the right "
        "specialist: billing for payment issues, technical for bugs "
        "and integrations, or general for everything else."
    )
    .sub_agent(billing_isolated)
    .sub_agent(technical_fluent)
    .sub_agent(general_fluent)
    .build()
)

# --- ASSERT ---

# 1. Coordinator defaults: transfer is allowed
assert coordinator_fluent.disallow_transfer_to_parent is False
assert coordinator_fluent.disallow_transfer_to_peers is False

# 2. Explicit flags work correctly
built_explicit = billing_explicit.build()
assert built_explicit.disallow_transfer_to_parent is True
assert built_explicit.disallow_transfer_to_peers is True

# 3. .isolate() sets both flags
built_isolated = billing_isolated.build()
assert built_isolated.disallow_transfer_to_parent is True
assert built_isolated.disallow_transfer_to_peers is True

# 4. .isolate() and explicit flags produce the same result
assert built_explicit.disallow_transfer_to_parent == built_isolated.disallow_transfer_to_parent
assert built_explicit.disallow_transfer_to_peers == built_isolated.disallow_transfer_to_peers

# 5. General agent keeps defaults (can transfer freely)
built_general = general_fluent.build()
assert built_general.disallow_transfer_to_parent is False
assert built_general.disallow_transfer_to_peers is False

# 6. Coordinator has the correct number of sub-agents
assert len(coordinator_fluent.sub_agents) == 3
assert coordinator_fluent.sub_agents[0].name == "billing_specialist"
assert coordinator_fluent.sub_agents[1].name == "technical_specialist"
assert coordinator_fluent.sub_agents[2].name == "general_support"

# 7. Native and fluent produce equivalent types
assert type(coordinator_native) == type(coordinator_fluent)
assert type(billing_native) == type(built_isolated)
