# Primitives Showcase: tap, expect, gate, Route, S.* in a single pipeline

*How to compose agents into a sequential pipeline.*

_Source: `43_primitives_showcase.py`_

::::{tab-set}
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, Pipeline, S, tap, expect, gate
from adk_fluent._routing import Route
from adk_fluent.workflow import Loop

MODEL = "gemini-2.5-flash"

# --- 1. tap: observe state without mutating ---

observed = []
writer = Agent("writer", MODEL).instruct("Write a draft.").outputs("draft")
pipeline_with_tap = writer >> tap(lambda s: observed.append(s.get("draft")))
assert isinstance(pipeline_with_tap, Pipeline)

# tap via method syntax (same result)
pipeline_method = writer.tap(lambda s: observed.append(s.get("draft")))
assert isinstance(pipeline_method, Pipeline)

# --- 2. expect: assert state contracts between steps ---

validator = Agent("validator", MODEL).instruct("Validate input.").outputs("valid")
enricher = Agent("enricher", MODEL).instruct("Enrich the data.")

pipeline_with_expect = validator >> expect(lambda s: s.get("valid") == "yes", "Validation must pass") >> enricher
assert isinstance(pipeline_with_expect, Pipeline)
built = pipeline_with_expect.build()
assert len(built.sub_agents) == 3  # validator, expect, enricher

# --- 3. gate: human-in-the-loop approval ---

risk_gate = gate(
    lambda s: s.get("risk_level") == "high",
    message="High-risk action requires approval",
    gate_key="risk_gate",
)
executor = Agent("executor", MODEL).instruct("Execute the action.")

pipeline_with_gate = Agent("analyzer", MODEL).instruct("Analyze risk.").outputs("risk_level") >> risk_gate >> executor
assert isinstance(pipeline_with_gate, Pipeline)
built_gate = pipeline_with_gate.build()
assert len(built_gate.sub_agents) == 3

# --- 4. Route: deterministic branching (not LLM-based) ---

classifier = Agent("classify", MODEL).instruct("Classify intent.").outputs("intent")
handler_a = Agent("handle_a", MODEL).instruct("Handle intent A.")
handler_b = Agent("handle_b", MODEL).instruct("Handle intent B.")
fallback = Agent("handle_default", MODEL).instruct("Handle unknown.")

route = Route("intent").eq("question", handler_a).eq("command", handler_b).otherwise(fallback)

routed_pipeline = classifier >> route
assert isinstance(routed_pipeline, Pipeline)
built_route = routed_pipeline.build()
assert len(built_route.sub_agents) == 2  # classifier + route_agent

# Route with .when() for multi-key predicates
complex_route = (
    Route()
    .when(lambda s: s.get("score", 0) > 0.8 and s.get("lang") == "en", handler_a)
    .when(lambda s: s.get("score", 0) > 0.5, handler_b)
    .otherwise(fallback)
)
assert len(complex_route._rules) == 2
assert complex_route._default is fallback

# --- 5. S.*: state transforms as pipeline steps ---

# S.pick — keep only specified keys
pick_step = S.pick("name", "email")
assert callable(pick_step)

# S.drop — remove specified keys
drop_step = S.drop("_internal", "_debug")
assert callable(drop_step)

# S.rename — rename keys
rename_step = S.rename(old_key="new_key")
assert callable(rename_step)

# S.default — set defaults for missing keys
default_step = S.default(language="en", retries=0)
assert callable(default_step)

# S.merge — combine multiple keys into one
merge_step = S.merge("findings_a", "findings_b", into="combined")
assert callable(merge_step)

# S.transform — apply a function to a single state value
transform_step = S.transform("draft", str.upper)
assert callable(transform_step)

# S.guard — assert invariants
guard_step = S.guard(lambda s: "draft" in s, "Draft must exist in state")
assert callable(guard_step)

# S.log — debug-print selected keys
log_step = S.log("draft", "score")
assert callable(log_step)

# S.compute — derive new keys from full state
compute_step = S.compute(avg=lambda s: (s.get("a", 0) + s.get("b", 0)) / 2)
assert callable(compute_step)

# --- 6. All together: composing primitives in one pipeline ---

full_pipeline = (
    # Set defaults
    S.default(retries=0, language="en")
    # Classify
    >> Agent("classify", MODEL).instruct("Classify the input.").outputs("intent")
    # Route based on classification
    >> Route("intent")
    .eq("research", Agent("researcher", MODEL).instruct("Research.").outputs("findings"))
    .eq("summarize", Agent("summarizer", MODEL).instruct("Summarize.").outputs("findings"))
    .otherwise(Agent("general", MODEL).instruct("General help.").outputs("findings"))
    # Observe after routing
    >> tap(lambda s: None)  # no-op observation
    # Assert contract
    >> expect(lambda s: "findings" in s, "Routing must produce findings")
    # Transform state
    >> S.compute(word_count=lambda s: len(s.get("findings", "").split()))
    # Write report
    >> Agent("writer", MODEL).instruct("Write report.").outputs("draft")
)

assert isinstance(full_pipeline, Pipeline)
built_full = full_pipeline.build()
# S.default, classify, route_agent, tap, expect, compute, writer = 7 steps
assert len(built_full.sub_agents) == 7

# --- 7. sub_agent() — the new canonical method ---

coordinator = (
    Agent("coordinator", MODEL)
    .instruct("Coordinate tasks.")
    .sub_agent(Agent("worker_a", MODEL).instruct("Work A."))
    .sub_agent(Agent("worker_b", MODEL).instruct("Work B."))
)
built_coord = coordinator.build()
assert len(built_coord.sub_agents) == 2

# --- 8. include_history() — explicit alias ---

agent_no_history = Agent("no_hist", MODEL).include_history("none").instruct("Do something.")
assert agent_no_history._config["include_contents"] == "none"

# .history() still works as short alias
agent_short = Agent("short", MODEL).history("none").instruct("Do something.")
assert agent_short._config["include_contents"] == "none"
```
:::
::::
