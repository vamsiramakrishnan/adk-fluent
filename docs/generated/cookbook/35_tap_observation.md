# ML Inference Monitoring: Performance Tap for Pure Observation

*How to use ml inference monitoring: performance tap for pure observation with the fluent API.*

_Source: `35_tap_observation.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
# Native ADK requires subclassing BaseAgent for a pure observation step.
# In an ML inference pipeline, you need to log latency and prediction
# metadata without mutating the pipeline state:
from google.adk.agents.base_agent import BaseAgent as NativeBaseAgent
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.sequential_agent import SequentialAgent


class LogInferenceMetrics(NativeBaseAgent):
    """Custom agent just to log inference metrics without modifying state."""

    async def _run_async_impl(self, ctx):
        prediction = ctx.session.state.get("prediction", {})
        print(f"Inference result: {prediction}")
        print(f"Model confidence: {ctx.session.state.get('confidence', 'N/A')}")
        # yield nothing -- pure observation


preprocessor = LlmAgent(name="preprocessor", model="gemini-2.5-flash", instruction="Preprocess input.")
logger = LogInferenceMetrics(name="metrics_logger")
postprocessor = LlmAgent(name="postprocessor", model="gemini-2.5-flash", instruction="Format output.")

pipeline_native = SequentialAgent(name="pipeline", sub_agents=[preprocessor, logger, postprocessor])
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, Pipeline, tap

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
```
:::
::::

## Equivalence

```python
from adk_fluent._base import _TapBuilder

# tap() creates a _TapBuilder
t = tap(lambda s: None)
assert isinstance(t, _TapBuilder)

# >> tap() creates a Pipeline with 3 steps
assert isinstance(ml_pipeline, Pipeline)
built = ml_pipeline.build()
assert len(built.sub_agents) == 3

# Named function keeps its name
named = tap(log_prediction_metrics)
assert named._config["name"] == "log_prediction_metrics"

# Lambda gets sanitized name
anon = tap(lambda s: None)
assert anon._config["name"].startswith("tap_")
assert anon._config["name"].isidentifier()

# .tap() method returns a Pipeline (self >> tap_step)
assert isinstance(pipeline_method, Pipeline)
```
