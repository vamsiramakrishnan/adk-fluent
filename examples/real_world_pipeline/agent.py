"""
Real-World Pipeline: Full Expression Language

Converted from cookbook example: 28_real_world_pipeline.py

Usage:
    cd examples
    adk web real_world_pipeline
"""

from adk_fluent import Agent, Pipeline
from adk_fluent._routing import Route
from adk_fluent.presets import Preset
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

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
complex_handler = (
    Agent("researcher").instruct("Research thoroughly.").use(production)
    >> Agent("synthesizer").instruct("Synthesize findings.").use(production)
)
creative_handler = (
    (Agent("brainstorm").instruct("Generate ideas.").use(production)
     | Agent("critique").instruct("Find flaws.").use(production))
    >> Agent("refine").instruct("Refine the best ideas.").use(production)
)

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
    >> Route("intent")
        .eq("simple", simple_handler)
        .eq("complex", complex_handler)
        .eq("creative", creative_handler)
    >> quality_loop
    >> formatter
)

root_agent = pipeline.build()
