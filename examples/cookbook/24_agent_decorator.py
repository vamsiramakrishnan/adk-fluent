"""@agent Decorator Syntax"""

# --- NATIVE ---
# Native ADK:
#   from google.adk.agents.llm_agent import LlmAgent
#
#   def get_weather(city: str) -> str:
#       return f"Sunny in {city}"
#
#   agent = LlmAgent(
#       name="weather_bot",
#       model="gemini-2.5-flash",
#       instruction="You help with weather queries.",
#       tools=[get_weather],
#   )

# --- FLUENT ---
from adk_fluent.decorators import agent


@agent("weather_bot", model="gemini-2.5-flash")
def weather_bot():
    """You help with weather queries."""
    pass


@weather_bot.tool
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Sunny in {city}"


@weather_bot.on("before_model")
def log_call(callback_context, llm_request):
    """Log every model call."""
    pass


# The decorator returns a builder, not a built agent
# Build it when ready:
built = weather_bot.build()

# --- ASSERT ---
from adk_fluent.agent import Agent as AgentBuilder

# Decorator produces a builder
assert isinstance(weather_bot, AgentBuilder)

# Docstring becomes instruction
assert weather_bot._config["instruction"] == "You help with weather queries."

# Tools are registered
assert len(weather_bot._lists["tools"]) == 1

# Callbacks are registered via .on()
assert len(weather_bot._callbacks["before_model_callback"]) == 1

# Builds to a real ADK agent
from google.adk.agents.llm_agent import LlmAgent

assert isinstance(built, LlmAgent)
assert built.name == "weather_bot"
