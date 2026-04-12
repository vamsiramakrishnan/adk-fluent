# G Module: Declarative Guard Composition

Demonstrates the G module -- a fluent composition surface for safety,
validation, and policy guards. Guards compile into before/after model
callbacks automatically.

Key concepts:
  - GGuard: single guard unit with phase and compile function
  - GComposite: composable chain with | operator
  - G.json(), G.length(), G.regex(): structural guards
  - G.output(), G.input(): schema validation guards
  - G.pii(), G.toxicity(), G.topic(): content safety guards
  - G.budget(), G.rate_limit(), G.max_turns(): policy guards
  - G.grounded(), G.hallucination(): grounding guards
  - G.when(predicate, guard): conditional guards
  - Provider protocols: PIIDetector, ContentJudge

:::{tip} What you'll learn
How to register lifecycle callbacks with accumulation semantics.
:::

_Source: `67_g_module_guards.py`_

::::{tab-set}
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, Pipeline
from adk_fluent._guards import (
    G,
    GComposite,
    GGuard,
    GuardViolation,
    PIIDetector,
    PIIFinding,
    ContentJudge,
    JudgmentResult,
)

# --- 1. GComposite composition with | operator ---
json_guard = G.json()
assert isinstance(json_guard, GComposite)
assert len(json_guard) == 1

length_guard = G.length(min=10, max=500)
assert isinstance(length_guard, GComposite)

# Compose with pipe operator
chain = G.json() | G.length(max=500)
assert isinstance(chain, GComposite)
assert len(chain) == 2  # two guards

# Chaining multiple guards
multi_chain = G.json() | G.length(max=500) | G.pii("redact")
assert len(multi_chain) == 3

# --- 2. G.json() compiles to after_model_callback ---
agent = Agent("validator").model("gemini-2.5-flash")
agent.guard(G.json())

# Guard compiles into after_model_callback
callbacks = agent._callbacks.get("after_model_callback", [])
assert any(name == "guard:json" for name, _ in callbacks)

# Guard spec is also tracked in config
guard_specs = agent._config.get("_guard_specs", ())
assert len(guard_specs) == 1
assert guard_specs[0]._kind == "json"

# --- 3. G.length(min, max) validates output length ---
agent2 = Agent("length_checker").model("gemini-2.5-flash")
agent2.guard(G.length(min=20, max=1000))

callbacks2 = agent2._callbacks.get("after_model_callback", [])
assert any(name == "guard:length" for name, _ in callbacks2)

# The config is stored in the callback
for name, config in callbacks2:
    if name == "guard:length":
        assert config["min"] == 20
        assert config["max"] == 1000

# --- 4. G.regex(pattern, action) enforces pattern matching ---
# Block mode: raises GuardViolation on match
block_guard = G.regex(r"\b(password|secret)\b", action="block")
agent3 = Agent("regex_blocker").model("gemini-2.5-flash")
agent3.guard(block_guard)

callbacks3 = agent3._callbacks.get("after_model_callback", [])
assert any(name == "guard:regex" for name, _ in callbacks3)

# Redact mode: replaces matches
redact_guard = G.regex(
    r"\b\d{3}-\d{2}-\d{4}\b",  # SSN pattern
    action="redact",
    replacement="[REDACTED-SSN]",
)
agent4 = Agent("regex_redactor").model("gemini-2.5-flash")
agent4.guard(redact_guard)

for name, config in agent4._callbacks.get("after_model_callback", []):
    if name == "guard:regex":
        assert config["action"] == "redact"
        assert config["replacement"] == "[REDACTED-SSN]"

# --- 5. G.output(schema) and G.input(schema) validate schemas ---


class ResponseSchema:
    """Example output schema."""

    answer: str
    confidence: float


class RequestSchema:
    """Example input schema."""

    query: str
    context: str


# Output validation (after_model_callback)
agent5 = Agent("output_validator").model("gemini-2.5-flash")
agent5.guard(G.output(ResponseSchema))

output_callbacks = agent5._callbacks.get("after_model_callback", [])
assert any(name == "guard:output" for name, _ in output_callbacks)

for name, schema in output_callbacks:
    if name == "guard:output":
        assert schema is ResponseSchema

# Input validation (before_model_callback)
agent6 = Agent("input_validator").model("gemini-2.5-flash")
agent6.guard(G.input(RequestSchema))

input_callbacks = agent6._callbacks.get("before_model_callback", [])
assert any(name == "guard:input" for name, _ in input_callbacks)

for name, schema in input_callbacks:
    if name == "guard:input":
        assert schema is RequestSchema

# --- 6. G.pii() with default regex detector ---
agent7 = Agent("pii_scanner").model("gemini-2.5-flash")
agent7.guard(G.pii("redact"))

pii_callbacks = agent7._callbacks.get("after_model_callback", [])
assert any(name == "guard:pii" for name, _ in pii_callbacks)

for name, config in pii_callbacks:
    if name == "guard:pii":
        assert config["action"] == "redact"
        assert config["threshold"] == 0.5
        assert config["replacement"] == "[PII]"
        # Default detector is _RegexDetector
        assert hasattr(config["detector"], "detect")

# --- 7. G.pii() with custom detector (PIIDetector protocol) ---


class CustomPIIDetector:
    """Custom PII detector implementing PIIDetector protocol."""

    async def detect(self, text: str) -> list[PIIFinding]:
        """Detect custom PII patterns."""
        findings = []
        # Example: detect employee IDs like EMP-12345
        import re

        for match in re.finditer(r"\bEMP-\d{5}\b", text):
            findings.append(
                PIIFinding(
                    kind="EMPLOYEE_ID",
                    start=match.start(),
                    end=match.end(),
                    confidence=1.0,
                    text=match.group(),
                )
            )
        return findings


custom_detector = CustomPIIDetector()
assert isinstance(custom_detector, PIIDetector)  # Protocol check

agent8 = Agent("custom_pii").model("gemini-2.5-flash")
agent8.guard(G.pii("block", detector=custom_detector, threshold=0.8))

for name, config in agent8._callbacks.get("after_model_callback", []):
    if name == "guard:pii":
        assert config["detector"] is custom_detector
        assert config["threshold"] == 0.8
        assert config["action"] == "block"

# --- 8. G.toxicity() and G.topic() for content safety ---
agent9 = Agent("toxicity_filter").model("gemini-2.5-flash")
agent9.guard(G.toxicity(threshold=0.8))

toxicity_callbacks = agent9._callbacks.get("after_model_callback", [])
assert any(name == "guard:toxicity" for name, _ in toxicity_callbacks)

for name, config in toxicity_callbacks:
    if name == "guard:toxicity":
        assert config["threshold"] == 0.8
        assert hasattr(config["judge"], "judge")

# Topic blocking
agent10 = Agent("topic_filter").model("gemini-2.5-flash")
denied_topics = ["politics", "religion", "financial_advice"]
agent10.guard(G.topic(deny=denied_topics))

topic_callbacks = agent10._callbacks.get("after_model_callback", [])
assert any(name == "guard:topic" for name, _ in topic_callbacks)

for name, config in topic_callbacks:
    if name == "guard:topic":
        assert config["deny"] == denied_topics

# --- 9. G.budget(), G.rate_limit(), G.max_turns() policy guards ---

# Token budget enforcement
agent11 = Agent("budget_enforcer").model("gemini-2.5-flash")
agent11.guard(G.budget(max_tokens=5000))

budget_callbacks = agent11._callbacks.get("after_model_callback", [])
assert any(name == "guard:budget" for name, _ in budget_callbacks)

for name, config in budget_callbacks:
    if name == "guard:budget":
        assert config["max_tokens"] == 5000

# Rate limiting
agent12 = Agent("rate_limiter").model("gemini-2.5-flash")
agent12.guard(G.rate_limit(rpm=60))

rate_callbacks = agent12._callbacks.get("before_model_callback", [])
assert any(name == "guard:rate_limit" for name, _ in rate_callbacks)

for name, config in rate_callbacks:
    if name == "guard:rate_limit":
        assert config["rpm"] == 60

# Max turns limit
agent13 = Agent("turn_limiter").model("gemini-2.5-flash")
agent13.guard(G.max_turns(n=10))

turns_callbacks = agent13._callbacks.get("before_model_callback", [])
assert any(name == "guard:max_turns" for name, _ in turns_callbacks)

for name, config in turns_callbacks:
    if name == "guard:max_turns":
        assert config["n"] == 10

# --- 10. G.grounded() and G.hallucination() for grounding ---

# Grounding guard reads from state
agent14 = Agent("grounded_agent").model("gemini-2.5-flash")
agent14.guard(G.grounded(sources_key="documents"))

grounded_callbacks = agent14._callbacks.get("after_model_callback", [])
assert any(name == "guard:grounded" for name, _ in grounded_callbacks)

for name, config in grounded_callbacks:
    if name == "guard:grounded":
        assert config["sources_key"] == "documents"

# Check that guard declares reads dependency
guard_specs14 = agent14._config.get("_guard_specs", ())
for spec in guard_specs14:
    if spec._kind == "grounded":
        assert spec._reads_keys == frozenset({"documents"})

# Hallucination detection
agent15 = Agent("hallucination_detector").model("gemini-2.5-flash")
agent15.guard(G.hallucination(threshold=0.7, sources_key="sources"))

halluc_callbacks = agent15._callbacks.get("after_model_callback", [])
assert any(name == "guard:hallucination" for name, _ in halluc_callbacks)

for name, config in halluc_callbacks:
    if name == "guard:hallucination":
        assert config["threshold"] == 0.7
        assert config["sources_key"] == "sources"

# Hallucination guard also declares reads dependency
guard_specs15 = agent15._config.get("_guard_specs", ())
for spec in guard_specs15:
    if spec._kind == "hallucination":
        assert spec._reads_keys == frozenset({"sources"})

# --- 11. G.when(predicate, guard) for conditional guards ---


def is_production(state):
    """Example predicate checking environment."""
    return state.get("env") == "production"


# Conditional PII guard: only in production
agent16 = Agent("conditional_guard").model("gemini-2.5-flash")
conditional = G.when(is_production, G.pii("redact"))
agent16.guard(conditional)

# The inner guard is still compiled
pii_found = any(name == "guard:pii" for name, _ in agent16._callbacks.get("after_model_callback", []))
assert pii_found

# Guard spec tracks the conditional wrapper
guard_specs16 = agent16._config.get("_guard_specs", ())
assert any(spec._kind == "when" for spec in guard_specs16)

# Conditional with multiple guards chained
conditional_multi = G.when(lambda s: s.get("strict_mode", False), G.json() | G.length(max=500) | G.pii("block"))
agent17 = Agent("multi_conditional").model("gemini-2.5-flash")
agent17.guard(conditional_multi)

# All inner guards compiled
callbacks17 = agent17._callbacks.get("after_model_callback", [])
assert any(name == "guard:json" for name, _ in callbacks17)
assert any(name == "guard:length" for name, _ in callbacks17)
assert any(name == "guard:pii" for name, _ in callbacks17)

# --- 12. Builder integration: full guard chain on agent ---
agent18 = (
    Agent("protected_agent")
    .model("gemini-2.5-flash")
    .instruct("You are a helpful assistant.")
    .guard(G.json() | G.pii("redact") | G.budget(10000))
)

# All three guards compiled
callbacks18 = agent18._callbacks.get("after_model_callback", [])
guard_names = [name for name, _ in callbacks18]
assert "guard:json" in guard_names
assert "guard:pii" in guard_names
assert "guard:budget" in guard_names

# Guard specs tracked
specs18 = agent18._config.get("_guard_specs", ())
assert len(specs18) == 3

# --- 13. NamespaceSpec protocol conformance ---
composite = G.json() | G.pii("redact")

# _kind discriminator
assert composite._kind == "guard_chain"

# _as_list() flattens guards
flattened = composite._as_list()
assert len(flattened) == 2
assert all(isinstance(g, GGuard) for g in flattened)

# _reads_keys union
json_guard_obj = G.json()
assert json_guard_obj._reads_keys == frozenset()

grounded_guard = G.grounded(sources_key="docs")
assert grounded_guard._reads_keys == frozenset({"docs"})

# Union of reads
combined_reads = G.json() | G.grounded("docs") | G.hallucination(sources_key="refs")
union_reads = combined_reads._reads_keys
assert union_reads is not None
assert "docs" in union_reads
assert "refs" in union_reads

# _writes_keys always empty for guards
assert composite._writes_keys == frozenset()

# --- 14. Guard specs stored in builder config ---
agent19 = Agent("spec_tracking").model("gemini-2.5-flash")

# No specs initially
assert "_guard_specs" not in agent19._config

# Add first guard
agent19.guard(G.json())
specs = agent19._config.get("_guard_specs", ())
assert len(specs) == 1

# Add more guards -- they accumulate
agent19.guard(G.pii("redact"))
specs = agent19._config.get("_guard_specs", ())
assert len(specs) == 2

agent19.guard(G.budget(5000))
specs = agent19._config.get("_guard_specs", ())
assert len(specs) == 3

# Each spec is a GGuard instance
assert all(isinstance(s, GGuard) for s in specs)

# --- 15. Full production example: comprehensive guard chain on medical agent ---


class MedicalResponseSchema:
    """Structured medical information response."""

    answer: str
    disclaimer: str
    sources: list[str]


class CustomToxicityJudge:
    """Custom judge for medical content appropriateness."""

    async def judge(self, text: str, context: dict | None = None) -> JudgmentResult:
        """Check for harmful medical advice."""
        # Simplified example: block if text contains dangerous keywords
        dangerous_keywords = ["self-medicate", "stop taking", "ignore doctor"]
        if any(kw in text.lower() for kw in dangerous_keywords):
            return JudgmentResult(passed=False, score=0.95, reason="Contains potentially harmful medical advice")
        return JudgmentResult(passed=True, score=0.1, reason="Safe")


# Build a medical agent with comprehensive safety guards
medical_agent = (
    Agent("medical_advisor")
    .model("gemini-2.5-flash")
    .instruct(
        "You provide general health information only. "
        "Always include disclaimers. Never diagnose or prescribe. "
        "Direct emergencies to 911."
    )
    .guard(
        # Structural validation
        G.output(MedicalResponseSchema)
        | G.length(min=50, max=2000)
        # PII protection
        | G.pii("redact", replacement="[PATIENT-INFO]")
        # Content safety
        | G.toxicity(threshold=0.7, judge=CustomToxicityJudge())
        | G.topic(deny=["specific_diagnosis", "prescription_dosage"])
        # Grounding
        | G.grounded(sources_key="medical_sources")
        | G.hallucination(threshold=0.6, sources_key="medical_sources")
        # Policy limits
        | G.budget(max_tokens=8000)
        | G.max_turns(n=5)
    )
)

# Verify all guards compiled
after_callbacks = medical_agent._callbacks.get("after_model_callback", [])
before_callbacks = medical_agent._callbacks.get("before_model_callback", [])

# After model guards
after_guard_names = [name for name, _ in after_callbacks]
assert "guard:output" in after_guard_names
assert "guard:length" in after_guard_names
assert "guard:pii" in after_guard_names
assert "guard:toxicity" in after_guard_names
assert "guard:topic" in after_guard_names
assert "guard:grounded" in after_guard_names
assert "guard:hallucination" in after_guard_names
assert "guard:budget" in after_guard_names

# Before model guards
before_guard_names = [name for name, _ in before_callbacks]
assert "guard:max_turns" in before_guard_names

# Guard specs tracked
medical_specs = medical_agent._config.get("_guard_specs", ())
assert len(medical_specs) == 9  # All nine guards

# Verify reads dependencies declared correctly
reads_specs = [s for s in medical_specs if s._reads_keys]
assert len(reads_specs) == 2  # grounded and hallucination
assert all("medical_sources" in s._reads_keys for s in reads_specs)

# --- Integration with pipeline: guards on individual agents ---
writer = (
    Agent("medical_writer")
    .model("gemini-2.5-flash")
    .instruct("Draft response.")
    .guard(G.pii("redact") | G.length(max=1000))
)
reviewer = (
    Agent("medical_reviewer")
    .model("gemini-2.5-flash")
    .instruct("Review safety.")
    .guard(G.toxicity(threshold=0.8) | G.budget(5000))
)

# Build pipeline with guarded agents
pipeline = writer >> reviewer

# Each agent has its own guards
writer_specs = writer._config.get("_guard_specs", ())
assert len(writer_specs) == 2

reviewer_specs = reviewer._config.get("_guard_specs", ())
assert len(reviewer_specs) == 2

print("All G module guard composition assertions passed!")
```
:::
::::
