"""
Multi-Language Support Routing with Dict >> Shorthand

Converted from cookbook example: 18_dict_routing.py

Usage:
    cd examples
    adk web dict_routing
"""

from adk_fluent import Agent, Pipeline
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# Step 1: Language detector outputs the detected language to state
detector = (
    Agent("language_detector")
    .model("gemini-2.5-flash")
    .instruct("Detect the language of the customer message. Output exactly one of: 'english', 'spanish', 'french'.")
    .writes("language")
)

# Step 2: Dict >> creates deterministic routing (zero LLM calls for routing)
english_support = (
    Agent("english_support")
    .model("gemini-2.5-flash")
    .instruct("Respond to the customer in English. Be helpful and professional.")
)
spanish_support = (
    Agent("spanish_support")
    .model("gemini-2.5-flash")
    .instruct("Responde al cliente en espanol. Se profesional y amable.")
)
french_support = (
    Agent("french_support")
    .model("gemini-2.5-flash")
    .instruct("Repondez au client en francais. Soyez professionnel et aimable.")
)

pipeline = detector >> {
    "english": english_support,
    "spanish": spanish_support,
    "french": french_support,
}

root_agent = pipeline.build()
