"""
Financial Advisor: Multi-agent financial advisory system.

Converted from adk-samples financial_advisor — root coordinator delegates
to 4 specialist sub-agents via AgentTool (LLM-driven routing).

Usage:
    cd examples
    adk web financial_advisor
"""

from adk_fluent import Agent
from dotenv import load_dotenv
from google.adk.tools import google_search

from .prompt import (
    DATA_ANALYST_PROMPT,
    EXECUTION_ANALYST_PROMPT,
    FINANCIAL_COORDINATOR_PROMPT,
    RISK_ANALYST_PROMPT,
    TRADING_ANALYST_PROMPT,
)

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

MODEL = "gemini-2.5-pro"

# --- Sub-agents ---

data_analyst = (
    Agent("data_analyst_agent", MODEL)
    .instruct(DATA_ANALYST_PROMPT)
    .tool(google_search)
    .writes("market_data_analysis_output")
)

trading_analyst = (
    Agent("trading_analyst_agent", MODEL).instruct(TRADING_ANALYST_PROMPT).writes("proposed_trading_strategies_output")
)

execution_analyst = (
    Agent("execution_analyst_agent", MODEL).instruct(EXECUTION_ANALYST_PROMPT).writes("execution_plan_output")
)

risk_analyst = Agent("risk_analyst_agent", MODEL).instruct(RISK_ANALYST_PROMPT).writes("final_risk_assessment_output")

# --- Root coordinator ---

root_agent = (
    Agent("financial_coordinator", MODEL)
    .describe(
        "guide users through a structured process to receive financial "
        "advice by orchestrating a series of expert subagents"
    )
    .instruct(FINANCIAL_COORDINATOR_PROMPT)
    .writes("financial_coordinator_output")
    .delegate_to(data_analyst)
    .delegate_to(trading_analyst)
    .delegate_to(execution_analyst)
    .delegate_to(risk_analyst)
    .build()
)
