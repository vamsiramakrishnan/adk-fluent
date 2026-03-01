# Timeout: Real-Time Trading Agent with Strict Execution Deadline

:::{admonition} Why this matters
:class: important
In latency-sensitive systems, a stale result is worse than no result. A trading analysis that arrives after the market window closes is useless. A real-time recommendation that takes 30 seconds loses the customer. `.timeout()` enforces strict execution deadlines, canceling agents that exceed their time budget and allowing the pipeline to fail fast or fall back to an alternative.
:::

:::{warning} Without this
Without timeouts, a slow API call or a model that enters an infinite reasoning loop blocks the entire pipeline indefinitely. Users wait forever with no feedback. In native ADK, there's no built-in timeout mechanism -- you'd need to implement `asyncio.wait_for` wrappers around every agent call manually.
:::

:::{tip} What you'll learn
How to enforce execution time limits with .timeout().
:::

_Source: `40_timeout.py`_

::::{tab-set}
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, Pipeline

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
```
:::
:::{tab-item} Native ADK
```python
# Native ADK has no built-in timeout mechanism. You'd need to:
#   1. Subclass BaseAgent
#   2. Run the sub-agent in an asyncio.create_task
#   3. Use asyncio.Queue to forward events with deadline tracking
#   4. Cancel the task on timeout
# For trading systems, a missed deadline can mean significant losses.
# This is ~40 lines of async boilerplate per timeout.
```
:::
:::{tab-item} Architecture
```mermaid
graph TD
    n1[["data_ingest_then_strategy_engine_timeout_2_then_order_formatter (sequence)"]]
    n2["data_ingest"]
    n3["strategy_engine_timeout_2 (timeout 30s)"]
    n4["strategy_engine"]
    n5["order_formatter"]
    n3 --> n4
    n2 --> n3
    n3 --> n5
```
:::
::::

## Equivalence

```python
from adk_fluent._primitive_builders import TimedAgent
from adk_fluent._base import BuilderBase

# .timeout() returns a TimedAgent
assert isinstance(market_analyzer, TimedAgent)
assert isinstance(market_analyzer, BuilderBase)

# Stores the timeout duration
assert market_analyzer._seconds == 5

# Builds with sub-agent
built = market_analyzer.build()
assert len(built.sub_agents) == 1
assert built.sub_agents[0].name == "market_analyzer"

# Name includes original agent name for tracing
assert "market_analyzer" in market_analyzer._config["name"]

# Composable in pipeline -- timeout is transparent to pipeline construction
assert isinstance(trading_pipeline, Pipeline)
built_pipeline = trading_pipeline.build()
assert len(built_pipeline.sub_agents) == 3

# Pipeline-level timeout
assert isinstance(bounded_execution, TimedAgent)
assert bounded_execution._seconds == 60
```
