"""
Pipeline Optimization with IR -- Inspecting and Compiling Agent Graphs

Demonstrates to_ir() for pipeline analysis, to_app() for production
compilation, and to_mermaid() for architecture documentation. The
scenario: a mortgage approval pipeline where the platform team
inspects the agent graph for optimization before deployment.

Converted from cookbook example: 44_ir_and_backends.py

Usage:
    cd examples
    adk web ir_and_backends
"""

from adk_fluent import Agent
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

root_agent = built_fluent
