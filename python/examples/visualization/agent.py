"""
Architecture Documentation -- Mermaid Diagrams from Live Code

Demonstrates to_mermaid() for generating architecture diagrams that
stay in sync with code. The scenario: a DevOps team documenting their
incident response platform's agent topology for runbooks and onboarding.

Converted from cookbook example: 48_visualization.py

Usage:
    cd examples
    adk web visualization
"""

from adk_fluent import Agent
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# Incident response platform with multiple topology types:
# sequential stages, parallel fan-out, and conditional routing

# Stage 1: Alert triage
triage = (
    Agent("alert_ingestor")
    .model("gemini-2.5-flash")
    .instruct("Ingest alert from PagerDuty/OpsGenie and extract severity, service, and description.")
    .writes("alert_data")
)

# Stage 2: Parallel diagnosis from multiple sources
diagnosis = (
    Agent("log_analyzer")
    .model("gemini-2.5-flash")
    .instruct("Search application logs for errors correlated with the alert timeframe.")
    | Agent("metrics_checker")
    .model("gemini-2.5-flash")
    .instruct("Check Prometheus/Grafana metrics for anomalies in the affected service.")
    | Agent("trace_analyzer")
    .model("gemini-2.5-flash")
    .instruct("Analyze distributed traces to identify the failing component.")
)

# Stage 3: Resolution
resolution = (
    Agent("incident_responder")
    .model("gemini-2.5-flash")
    .instruct("Synthesize findings and recommend remediation steps. Draft incident report.")
)

# Full pipeline: sequential with parallel fan-out in the middle
incident_pipeline = triage >> diagnosis >> resolution

# Generate architecture diagram
mermaid_diagram = incident_pipeline.to_mermaid()

# Generate human-readable explanation
explanation = incident_pipeline.explain()

# Build for deployment
built = incident_pipeline.build()

root_agent = built
