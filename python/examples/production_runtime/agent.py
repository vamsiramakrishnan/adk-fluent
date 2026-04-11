"""
Production Deployment -- to_app() with Middleware Stack

Real-world use case: E-commerce order processing with retry middleware
for transient failures. Production systems need resilience -- this shows
how middleware and pipelines compose to handle validation, payment, and
fulfillment with automatic retries and structured logging.

In other frameworks: LangGraph handles retries via custom node wrappers
that must be applied to each node individually. adk-fluent uses middleware
composition with the M module, applying cross-cutting concerns uniformly
across the entire pipeline.

Converted from cookbook example: 15_production_runtime.py

Usage:
    cd examples
    adk web production_runtime
"""

from adk_fluent import Agent, RetryMiddleware, StructuredLogMiddleware
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# to_app() compiles through IR to a production-ready ADK App.
# Middleware wraps every agent invocation with cross-cutting concerns.
pipeline = (
    Agent("order_validator")
    .model("gemini-2.5-flash")
    .instruct("Validate the incoming order: check required fields, verify pricing, confirm inventory.")
    >> Agent("payment_processor")
    .model("gemini-2.5-flash")
    .instruct("Process payment for the validated order. Apply discounts and calculate tax.")
    >> Agent("fulfillment")
    .model("gemini-2.5-flash")
    .instruct("Create shipping label and dispatch order to the nearest warehouse.")
)

# Add production middleware
pipeline.middleware(RetryMiddleware(max_attempts=3))
pipeline.middleware(StructuredLogMiddleware())

# Compile to native App -- ready for Runner
app = pipeline.to_app()

# Also build the sequential agent directly for comparison
built_fluent = pipeline.build()

root_agent = built_fluent
