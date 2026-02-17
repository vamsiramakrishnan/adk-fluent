"""
Weather agent — built with adk-fluent, runs with adk web / adk run / adk deploy.

Usage:
    cd examples
    adk web weather_agent     # opens web UI at http://localhost:8000
    adk run weather_agent     # interactive CLI
    adk deploy weather_agent  # deploy to Vertex AI
"""

from adk_fluent import Agent
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)


# --- Tools (plain functions, auto-wrapped) ---

def get_weather(city: str) -> dict:
    """Get the current weather for a city."""
    # Stub — replace with real API call
    weather_data = {
        "new york": {"temp": "72F", "condition": "Sunny", "humidity": "45%"},
        "london": {"temp": "58F", "condition": "Cloudy", "humidity": "78%"},
        "tokyo": {"temp": "80F", "condition": "Clear", "humidity": "60%"},
    }
    data = weather_data.get(city.lower(), {"temp": "??", "condition": "Unknown"})
    return {"city": city, **data}


def get_forecast(city: str, days: int = 3) -> dict:
    """Get a multi-day forecast for a city."""
    return {
        "city": city,
        "days": days,
        "forecast": [f"Day {i+1}: Sunny, {70+i}F" for i in range(days)],
    }


# --- Agent definition (fluent) ---

root_agent = (
    Agent("weather_agent")
    .model("gemini-2.5-flash")
    .describe("An agent that provides weather information and forecasts")
    .instruct(
        "You are a weather assistant. Use the available tools to answer "
        "questions about current weather and forecasts. Always mention the "
        "city name and conditions in your response."
    )
    .tool(get_weather)
    .tool(get_forecast)
    .build()
)
