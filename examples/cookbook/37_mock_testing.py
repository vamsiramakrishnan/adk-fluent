"""Mock: Bypass LLM Calls for Testing"""

# --- NATIVE ---
# Native ADK uses before_model_callback to bypass the LLM:
#
#   from google.adk.models.llm_response import LlmResponse
#   from google.genai import types
#
#   def mock_callback(callback_context, llm_request):
#       return LlmResponse(
#           content=types.Content(
#               role="model",
#               parts=[types.Part(text="Mocked response")]
#           )
#       )
#
#   agent = LlmAgent(
#       name="agent", model="gemini-2.5-flash",
#       instruction="Do something.",
#       before_model_callback=mock_callback,
#   )
#
# This is exactly what ADK's ReplayPlugin does globally.
# adk-fluent provides .mock() for per-agent mocking.

# --- FLUENT ---
from adk_fluent import Agent

# .mock(list): cycle through canned responses
agent_list = (
    Agent("writer").model("gemini-2.5-flash").instruct("Write a story.").mock(["Once upon a time...", "The end."])
)

# .mock(callable): dynamic response based on the LLM request
agent_fn = (
    Agent("echo").model("gemini-2.5-flash").instruct("Echo the user's message.").mock(lambda req: "Mocked: I heard you")
)

# Chainable -- .mock() returns self
agent_chained = (
    Agent("analyzer")
    .model("gemini-2.5-flash")
    .mock(["Analysis complete."])
    .instruct("Analyze the data.")
    .outputs("analysis")
)

# --- ASSERT ---
from google.adk.models.llm_response import LlmResponse

# .mock(list) registers one before_model_callback
assert len(agent_list._callbacks["before_model_callback"]) == 1

# The callback returns LlmResponse (bypasses actual LLM)
cb = agent_list._callbacks["before_model_callback"][0]
result = cb(callback_context=None, llm_request=None)
assert isinstance(result, LlmResponse)
assert result.content.parts[0].text == "Once upon a time..."

# List responses cycle
r2 = cb(None, None)
assert r2.content.parts[0].text == "The end."
r3 = cb(None, None)
assert r3.content.parts[0].text == "Once upon a time..."  # cycles back

# .mock(callable) also registers callback
assert len(agent_fn._callbacks["before_model_callback"]) == 1
cb_fn = agent_fn._callbacks["before_model_callback"][0]
result_fn = cb_fn(None, None)
assert result_fn.content.parts[0].text == "Mocked: I heard you"

# Chainable: .mock() returns self
assert agent_chained._config["instruction"] == "Analyze the data."
assert agent_chained._config["output_key"] == "analysis"
