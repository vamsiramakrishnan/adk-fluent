"""
Pipeline Optimization with IR -- Inspecting, Compiling, and Selecting Backends

Demonstrates to_ir() for pipeline analysis, to_app() for production
compilation, to_mermaid() for architecture documentation, and the new
compile layer for backend-selectable execution. The scenario: a mortgage
approval pipeline where the platform team inspects the agent graph for
optimization before deploying to different execution backends.

Converted from cookbook example: 44_ir_and_backends.py

Usage:
    cd examples
    adk web ir_and_backends
"""

from adk_fluent import Agent, EngineCapabilities
from adk_fluent import compile as compile_ir
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# Same pipeline expressed fluently
mortgage_pipeline = (
    Agent("doc_collector").model("gemini-2.5-flash").instruct("Collect and validate required mortgage documents.")
    >> (
        Agent("credit_check").model("gemini-2.5-flash").instruct("Run credit check on the applicant.")
        | Agent("income_verifier")
        .model("gemini-2.5-flash")
        .instruct("Verify employment and income from pay stubs and tax returns.")
    )
    >> Agent("underwriter")
    .model("gemini-2.5-flash")
    .instruct("Make final loan approval decision based on all gathered data.")
)

# 1. Inspect the IR tree -- frozen dataclass graph for analysis
ir = mortgage_pipeline.to_ir()

# 2. Compile to native ADK App -- production deployment
app = mortgage_pipeline.to_app()

# 3. Generate architecture diagram -- auto-sync documentation
mermaid = mortgage_pipeline.to_mermaid()

# 4. Build directly for comparison
built_fluent = mortgage_pipeline.build()

# 5. NEW: Compile through the compile layer with backend selection
#    The compile layer adds optimization passes and backend-specific compilation.
adk_result = compile_ir(ir, backend="adk")
asyncio_result = compile_ir(ir, backend="asyncio")
temporal_result = compile_ir(ir, backend="temporal")

# 6. NEW: Inspect engine capabilities per backend
adk_caps = adk_result.capabilities
temporal_caps = temporal_result.capabilities

root_agent = built_fluent
