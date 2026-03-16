"""
E-Commerce Order Routing with Deterministic Branching

Real-world use case: E-commerce order routing system that directs orders to
different fulfillment handlers based on order type (standard, express,
international).

In other frameworks: LangGraph uses conditional_edges with a routing function
that returns the target node name. adk-fluent uses Route("key").eq() for
declarative, readable branching without routing functions.

Pipeline topology:
    Route("category")
        ├─ "electronics" -> electronics
        ├─ "clothing"    -> clothing
        ├─ "grocery"     -> grocery
        └─ otherwise     -> general

Converted from cookbook example: 17_route_branching.py

Usage:
    cd examples
    adk web route_branching
"""

from adk_fluent import Agent
from adk_fluent._routing import Route
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# Route on exact match: direct orders to the correct fulfillment team
electronics = Agent("electronics").model("gemini-2.5-flash").instruct("Process electronics orders.")
clothing = Agent("clothing").model("gemini-2.5-flash").instruct("Process clothing orders.")
grocery = Agent("grocery").model("gemini-2.5-flash").instruct("Process grocery orders with cold chain.")

category_route = (
    Route("category")
    .eq("electronics", electronics)
    .eq("clothing", clothing)
    .eq("grocery", grocery)
    .otherwise(Agent("general").model("gemini-2.5-flash").instruct("Process general merchandise."))
)

# Route on substring: detect priority keywords in order notes
express = Agent("express").model("gemini-2.5-flash").instruct("Expedite with next-day delivery.")
standard = Agent("standard").model("gemini-2.5-flash").instruct("Process with standard shipping.")
priority_route = Route("order_notes").contains("RUSH", express).otherwise(standard)

# Route on threshold: handle high-value orders differently
vip_handler = Agent("vip_handler").model("gemini-2.5-flash").instruct("Assign dedicated account manager.")
regular_handler = Agent("regular_handler").model("gemini-2.5-flash").instruct("Process normally.")
value_route = Route("order_total").gt(500.0, vip_handler).otherwise(regular_handler)

# Complex multi-key predicate: combine membership status and order value
complex_route = (
    Route()
    .when(lambda s: s.get("membership") == "platinum" and float(s.get("order_total", 0)) > 100, vip_handler)
    .otherwise(regular_handler)
)

root_agent = complex_route.build()
