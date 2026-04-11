"""
ML Inference Monitoring: Performance Tap for Pure Observation

Converted from cookbook example: 35_tap_observation.py

Usage:
    cd examples
    adk web tap_observation
"""

from adk_fluent import Agent, Pipeline, tap
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# tap(): creates a pure observation step — reads state, never mutates.
# Perfect for monitoring ML pipeline health without affecting predictions.
ml_pipeline = (
    Agent("feature_engineer")
    .model("gemini-2.5-flash")
    .instruct("Extract and normalize features from the raw input data.")
    >> tap(lambda s: print(f"Features extracted: {len(s)} keys in state"))
    >> Agent("inference_engine")
    .model("gemini-2.5-flash")
    .instruct("Run inference on the prepared features and return predictions.")
)


# Named functions keep their name — better observability in production dashboards
def log_prediction_metrics(state):
    """Log prediction metadata to the monitoring system."""
    confidence = state.get("confidence", "unknown")
    latency = state.get("latency_ms", "unknown")
    print(f"[MONITOR] Confidence: {confidence}, Latency: {latency}ms")


pipeline_with_monitoring = (
    Agent("model_server")
    .model("gemini-2.5-flash")
    .instruct("Execute the ML model and return predictions with confidence scores.")
    >> tap(log_prediction_metrics)
    >> Agent("response_formatter")
    .model("gemini-2.5-flash")
    .instruct("Format the prediction into a human-readable response.")
)

# .tap() method on any builder — inline monitoring for quick debugging
pipeline_method = (
    Agent("anomaly_detector")
    .model("gemini-2.5-flash")
    .instruct("Detect anomalies in the incoming data stream.")
    .tap(lambda s: print(f"Anomaly detection complete, state keys: {list(s.keys())}"))
)

root_agent = pipeline_method.build()
