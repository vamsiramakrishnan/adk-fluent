"""
Dict >> Routing Shorthand

Converted from cookbook example: 18_dict_routing.py

Usage:
    cd examples
    adk web dict_routing
"""

from adk_fluent import Agent, Pipeline
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# Step 1: Classifier outputs a key to session state
classifier = (
    Agent("classify")
    .model("gemini-2.5-flash")
    .instruct("Classify the user request as 'booking', 'info', or 'complaint'.")
    .outputs("intent")  # alias for .output_key("intent")
)

# Step 2: Dict >> creates deterministic routing (zero LLM calls for routing)
booker = Agent("booker").model("gemini-2.5-flash").instruct("Book flights.")
info = Agent("info_agent").model("gemini-2.5-flash").instruct("Provide info.")
support = Agent("support").model("gemini-2.5-flash").instruct("Handle complaints.")

pipeline = classifier >> {
    "booking": booker,
    "info": info,
    "complaint": support,
}

root_agent = pipeline.build()
