"""
Medical Advice Safety Guardrails -- Guardrails with .guard()

Demonstrates guard mechanisms for agent safety and policy enforcement:
1. Legacy callable guards (backward compatibility)
2. G namespace composable guards (new declarative API)

The scenario: a medical information agent with safety guards that
screen requests and responses for dangerous self-diagnosis or
treatment recommendations, enforce output constraints, and prevent
PII leakage.

Converted from cookbook example: 12_guards.py

Usage:
    cd examples
    adk web guards
"""


# --- Tools & Callbacks ---


def medical_safety_screen(callback_context, llm_request):
    """Screen for dangerous medical advice in both requests and responses.

    Checks for self-medication dosage instructions, diagnostic claims
    without disclaimers, and emergency situations that need 911.
    """
    return None


from adk_fluent import Agent, G
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# ──────────────────────────────────────────────────────────────────
# Pattern 1: Legacy callable guard (backward compatible)
# ──────────────────────────────────────────────────────────────────

# One call registers both before and after:
builder_legacy = (
    Agent("medical_info")
    .model("gemini-2.5-flash")
    .instruct(
        "You provide general health and wellness information. "
        "Always include a disclaimer that you are not a doctor. "
        "Never prescribe medication or provide specific dosages. "
        "For emergencies, direct users to call emergency services."
    )
    .guard(medical_safety_screen)
)

# ──────────────────────────────────────────────────────────────────
# Pattern 2: G namespace guards (declarative, composable)
# ──────────────────────────────────────────────────────────────────

# Individual guards:
builder_json = Agent("medical_info").guard(G.json())
builder_length = Agent("medical_info").guard(G.length(max=500))
builder_pii = Agent("medical_info").guard(G.pii("redact"))
builder_budget = Agent("medical_info").guard(G.budget(max_tokens=5000))

# Composition with | operator:
builder_composed = (
    Agent("medical_advisor")
    .model("gemini-2.5-flash")
    .instruct(
        "You provide general health and wellness information. "
        "Always include a disclaimer that you are not a doctor. "
        "Never prescribe medication or provide specific dosages. "
        "For emergencies, direct users to call emergency services."
    )
    .guard(G.json() | G.length(max=500) | G.pii("redact") | G.budget(max_tokens=5000))
)

# ──────────────────────────────────────────────────────────────────
# Pattern 3: Provider-based PII detection
# ──────────────────────────────────────────────────────────────────

# Default regex-based detector:
builder_pii_default = Agent("medical_info").guard(G.pii("redact"))

# Custom regex detector with specific patterns:
custom_detector = G.regex_detector(
    {
        "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
        "PHONE": r"\b\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
    }
)
builder_pii_custom = Agent("medical_info").guard(G.pii("redact", detector=custom_detector))

# Multi-detector (union of multiple providers):
detector_a = G.regex_detector({"EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"})
detector_b = G.regex_detector({"SSN": r"\b\d{3}-\d{2}-\d{4}\b"})
multi_detector = G.multi(detector_a, detector_b)
builder_pii_multi = Agent("medical_info").guard(G.pii("block", detector=multi_detector, threshold=0.8))

# ──────────────────────────────────────────────────────────────────
# Pattern 4: Additional guard types
# ──────────────────────────────────────────────────────────────────

# Topic blocking:
builder_topic = Agent("medical_info").guard(G.topic(deny=["self-diagnosis", "prescription", "dosage"]))

# Regex-based redaction:
builder_regex = Agent("medical_info").guard(G.regex(r"\b\d+ ?mg\b", action="redact", replacement="[DOSAGE]"))

# Rate limiting:
builder_rate = Agent("medical_info").guard(G.rate_limit(rpm=60))

# Max conversation turns:
builder_turns = Agent("medical_info").guard(G.max_turns(n=10))

# ──────────────────────────────────────────────────────────────────
# Pattern 5: Full safety stack
# ──────────────────────────────────────────────────────────────────

builder_full = (
    Agent("medical_advisor_safe")
    .model("gemini-2.5-flash")
    .instruct(
        "You provide general health and wellness information. "
        "Always include a disclaimer that you are not a doctor. "
        "Never prescribe medication or provide specific dosages. "
        "For emergencies, direct users to call emergency services."
    )
    .guard(
        G.rate_limit(rpm=100)
        | G.max_turns(n=20)
        | G.pii("redact", threshold=0.7)
        | G.regex(r"\b\d+ ?mg\b", action="redact", replacement="[DOSAGE]")
        | G.topic(deny=["self-diagnosis", "prescription"])
        | G.length(max=1000)
        | G.budget(max_tokens=10000)
    )
)

root_agent = builder_full.build()
