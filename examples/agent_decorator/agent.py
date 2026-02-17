"""
@agent Decorator Syntax

Converted from cookbook example: 24_agent_decorator.py

Usage:
    cd examples
    adk web agent_decorator
"""

from adk_fluent.decorators import agent
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)


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

root_agent = built
