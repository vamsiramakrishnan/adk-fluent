# Real-World Pipeline: Full Expression Language

*How to compose agents into a sequential pipeline.*

_Source: `28_real_world_pipeline.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
# A real-world content pipeline in native ADK would be 80+ lines of
# explicit agent construction, manual routing, and callback wiring.
# See below for the fluent equivalent in ~30 lines.
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, Pipeline
from adk_fluent._routing import Route
from adk_fluent.presets import Preset


# Shared production preset
def audit_log(callback_context, llm_response):
    """Log all model responses for audit."""
    pass


production = Preset(model="gemini-2.5-flash", after_model=audit_log)

# Step 1: Classifier determines intent
classifier = (
    Agent("classifier")
    .instruct("Classify user request as 'simple', 'complex', or 'creative'.")
    .outputs("intent")
    .use(production)
)

# Step 2: Route to appropriate handler
simple_handler = Agent("simple").instruct("Give a direct answer.").use(production)
complex_handler = Agent("researcher").instruct("Research thoroughly.").use(production) >> Agent("synthesizer").instruct(
    "Synthesize findings."
).use(production)
creative_handler = (
    Agent("brainstorm").instruct("Generate ideas.").use(production)
    | Agent("critique").instruct("Find flaws.").use(production)
) >> Agent("refine").instruct("Refine the best ideas.").use(production)

# Step 3: Quality check loop
quality_loop = (
    Agent("reviewer").instruct("Review output quality.").outputs("quality").use(production)
    >> Agent("improver").instruct("Improve if needed.").use(production)
).loop_until(lambda s: s.get("quality") == "good", max_iterations=3)

# Step 4: Format output (only if valid)
formatter = (
    Agent("formatter")
    .instruct("Format the final response.")
    .proceed_if(lambda s: s.get("quality") == "good")
    .use(production)
)

# Compose the full pipeline
pipeline = (
    classifier
    >> Route("intent").eq("simple", simple_handler).eq("complex", complex_handler).eq("creative", creative_handler)
    >> quality_loop
    >> formatter
)
```
:::
::::

## Equivalence

```python
# The full pipeline is a Pipeline builder
assert isinstance(pipeline, Pipeline)

# It can be built into a real ADK agent graph
built = pipeline.build()

# Top level is SequentialAgent
from google.adk.agents.sequential_agent import SequentialAgent

assert isinstance(built, SequentialAgent)

# Has multiple stages
assert len(built.sub_agents) >= 3
```

:::{seealso}
API reference: [Pipeline](../api/workflow.md#builder-Pipeline)
:::
