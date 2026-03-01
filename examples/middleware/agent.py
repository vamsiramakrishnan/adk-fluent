"""
Middleware: Production Middleware Stack for a Healthcare API Agent

Converted from cookbook example: 45_middleware.py

Usage:
    cd examples
    adk web middleware
"""

from adk_fluent import Agent, RetryMiddleware, StructuredLogMiddleware
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# Scenario: A healthcare agent that queries electronic health records.
# Production requirements mandate:
#   1. Retry with exponential backoff for transient EHR API failures
#   2. Structured audit logging for HIPAA compliance

agent_fluent = (
    Agent("patient_lookup")
    .model("gemini-2.5-flash")
    .instruct("Look up patient records from the EHR system.")
    .middleware(RetryMiddleware(max_attempts=3))
    .middleware(StructuredLogMiddleware())
)

root_agent = agent_fluent.build()
