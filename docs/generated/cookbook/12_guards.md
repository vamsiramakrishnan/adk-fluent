# Medical Advice Safety Guardrails -- Guardrails with .guard()

Demonstrates guard mechanisms for agent safety and policy enforcement:
1. Legacy callable guards (backward compatibility)
2. G namespace composable guards (new declarative API)

The scenario: a medical information agent with safety guards that
screen requests and responses for dangerous self-diagnosis or
treatment recommendations, enforce output constraints, and prevent
PII leakage.

:::{tip} What you'll learn
How to attach guardrails to agent model calls.
:::

_Source: `12_guards.py`_

::::{tab-set}
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, G

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
```
:::
:::{tab-item} Native ADK
```python
from google.adk.agents.llm_agent import LlmAgent


def medical_safety_screen(callback_context, llm_request):
    """Screen for dangerous medical advice in both requests and responses.

    Checks for self-medication dosage instructions, diagnostic claims
    without disclaimers, and emergency situations that need 911.
    """
    return None


# In native ADK, you must register the same function twice:
agent_native = LlmAgent(
    name="medical_info",
    model="gemini-2.5-flash",
    instruction=(
        "You provide general health and wellness information. "
        "Always include a disclaimer that you are not a doctor. "
        "Never prescribe medication or provide specific dosages. "
        "For emergencies, direct users to call emergency services."
    ),
    before_model_callback=medical_safety_screen,
    after_model_callback=medical_safety_screen,
)
```
:::
::::

## Equivalence

```python
# Legacy guard registers as dual callback:
assert medical_safety_screen in builder_legacy._callbacks["before_model_callback"]
assert medical_safety_screen in builder_legacy._callbacks["after_model_callback"]

# G.json() compiles to after_model_callback:
json_cbs = builder_json._callbacks.get("after_model_callback", [])
assert any(item[0] == "guard:json" for item in json_cbs if isinstance(item, tuple))

# G.length() compiles with params:
length_cbs = builder_length._callbacks.get("after_model_callback", [])
assert any(
    item[0] == "guard:length" and item[1]["max"] == 500
    for item in length_cbs
    if isinstance(item, tuple) and len(item) == 2
)

# G.pii() compiles with detector:
pii_cbs = builder_pii._callbacks.get("after_model_callback", [])
assert any(
    item[0] == "guard:pii" and item[1]["action"] == "redact"
    for item in pii_cbs
    if isinstance(item, tuple) and len(item) == 2
)

# G.budget() compiles to after_model_callback:
budget_cbs = builder_budget._callbacks.get("after_model_callback", [])
assert any(
    item[0] == "guard:budget" and item[1]["max_tokens"] == 5000
    for item in budget_cbs
    if isinstance(item, tuple) and len(item) == 2
)

# Composed guards compile all specs:
composed_cbs = builder_composed._callbacks.get("after_model_callback", [])
guard_kinds = [item[0] for item in composed_cbs if isinstance(item, tuple)]
assert "guard:json" in guard_kinds
assert "guard:length" in guard_kinds
assert "guard:pii" in guard_kinds
assert "guard:budget" in guard_kinds

# Guard specs are stored in builder config:
guard_specs = builder_composed._config.get("_guard_specs", ())
assert len(guard_specs) == 4
assert all(hasattr(spec, "_kind") for spec in guard_specs)

# Full stack has all guards:
full_cbs_before = builder_full._callbacks.get("before_model_callback", [])
full_cbs_after = builder_full._callbacks.get("after_model_callback", [])
full_guard_kinds = [item[0] for item in full_cbs_before + full_cbs_after if isinstance(item, tuple)]
assert "guard:rate_limit" in full_guard_kinds
assert "guard:max_turns" in full_guard_kinds
assert "guard:pii" in full_guard_kinds
assert "guard:regex" in full_guard_kinds
assert "guard:topic" in full_guard_kinds
assert "guard:length" in full_guard_kinds
assert "guard:budget" in full_guard_kinds

print("✓ All guard patterns validated")
```
