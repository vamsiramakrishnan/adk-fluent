"""
Deterministic Route Branching

Converted from cookbook example: 17_route_branching.py

Usage:
    cd examples
    adk web route_branching
"""

from adk_fluent import Agent
from adk_fluent._routing import Route
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

booker = Agent("booker").model("gemini-2.5-flash").instruct("Book flights.")
info = Agent("info").model("gemini-2.5-flash").instruct("Provide info.")
default = Agent("fallback").model("gemini-2.5-flash").instruct("Handle other.")

# Route on exact match
route = Route("intent").eq("booking", booker).eq("info", info).otherwise(default)

# Route on substring
urgent = Agent("urgent").model("gemini-2.5-flash").instruct("Handle urgently.")
normal = Agent("normal").model("gemini-2.5-flash").instruct("Handle normally.")
text_route = Route("message").contains("URGENT", urgent).otherwise(normal)

# Route on threshold
premium = Agent("premium").model("gemini-2.5-flash").instruct("Premium service.")
basic = Agent("basic").model("gemini-2.5-flash").instruct("Basic service.")
score_route = Route("score").gt(0.8, premium).otherwise(basic)

# Complex multi-key predicate
complex_route = (
    Route().when(lambda s: s.get("status") == "vip" and float(s.get("score", 0)) > 0.5, premium).otherwise(basic)
)

root_agent = complex_route.build()
