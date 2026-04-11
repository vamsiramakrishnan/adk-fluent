"""
Timeout: Real-Time Trading Agent with Strict Execution Deadline

Converted from cookbook example: 40_timeout.py

Usage:
    cd examples
    adk web timeout
"""

from adk_fluent import Agent, Pipeline
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# Scenario: A real-time trading system where market analysis must complete
# within strict time bounds. Stale analysis is worse than no analysis.

# .timeout(seconds): wrap any agent with a time limit
# Market data analysis must complete within 5 seconds or be discarded
market_analyzer = (
    Agent("market_analyzer")
    .model("gemini-2.5-flash")
    .instruct(
        "Analyze current market conditions for the requested ticker symbol. Identify trend direction and volatility."
    )
    .timeout(5)
)

# Timeout in a pipeline -- only the slow step is time-bounded
# The strategy computation gets 30 seconds; other steps run without limits
trading_pipeline = (
    Agent("data_ingest").model("gemini-2.5-flash").instruct("Ingest real-time market data for the portfolio.")
    >> Agent("strategy_engine")
    .model("gemini-2.5-flash")
    .instruct("Compute optimal trading strategy based on current positions and market conditions.")
    .timeout(30)
    >> Agent("order_formatter").model("gemini-2.5-flash").instruct("Format the strategy as executable trade orders.")
)

# Timeout on an entire pipeline -- the full analysis-to-execution flow
# must complete within 60 seconds to catch the trading window
bounded_execution = (
    Agent("pre_trade_check").model("gemini-2.5-flash").instruct("Verify margin requirements and position limits.")
    >> Agent("trade_executor").model("gemini-2.5-flash").instruct("Execute the trade orders against the exchange.")
).timeout(60)

root_agent = bounded_execution.build()
