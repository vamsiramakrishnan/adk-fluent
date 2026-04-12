"""
News Analysis Pipeline with Operator Composition: >>, |, *

Pipeline topologies:
    >>  scraper >> analyzer >> reporter
    |   ( politics | markets )
    *   ( draft_writer >> fact_checker ) * 3

Converted from cookbook example: 16_operator_composition.py

Usage:
    cd examples
    adk web operator_composition
"""

from adk_fluent import Agent, Pipeline
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

s = Agent("scraper").model("gemini-2.5-flash").instruct("Scrape news articles from sources.")
a = Agent("analyzer").model("gemini-2.5-flash").instruct("Analyze sentiment and key themes.")
r = Agent("reporter").model("gemini-2.5-flash").instruct("Write a summary news report.")

# >> creates Pipeline (SequentialAgent): scrape -> analyze -> report
pipeline_fluent = s >> a >> r

# | creates FanOut (ParallelAgent): gather from multiple beats simultaneously
pol = Agent("politics").model("gemini-2.5-flash").instruct("Gather political news.")
mkt = Agent("markets").model("gemini-2.5-flash").instruct("Gather financial market data.")
parallel_fluent = pol | mkt

# * creates Loop (LoopAgent): draft and fact-check up to 3 times
dw = Agent("draft_writer").model("gemini-2.5-flash").instruct("Write a news draft.")
fc = Agent("fact_checker").model("gemini-2.5-flash").instruct("Fact-check the draft.")
loop_fluent = (dw >> fc) * 3

root_agent = loop_fluent.build()
