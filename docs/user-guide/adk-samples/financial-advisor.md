# Financial Advisor

Multi-agent financial advisory system with data analysis, trading strategies, execution planning, and risk evaluation.

## Architecture

Root coordinator delegates to 4 specialist sub-agents via AgentTool:

- data_analyst_agent → market_data_analysis_output
- trading_analyst_agent → proposed_trading_strategies_output
- execution_analyst_agent → execution_plan_output
- risk_analyst_agent → final_risk_assessment_output

## Native ADK

Original uses 8+ files across 5 directories:

```
financial_advisor/
├── __init__.py
├── agent.py
├── prompt.py
└── sub_agents/
    ├── data_analyst/
    │   ├── __init__.py
    │   ├── agent.py
    │   └── prompt.py
    ├── trading_analyst/
    │   ├── __init__.py
    │   ├── agent.py
    │   └── prompt.py
    ├── execution_analyst/
    │   ├── __init__.py
    │   ├── agent.py
    │   └── prompt.py
    └── risk_analyst/
        ├── __init__.py
        ├── agent.py
        └── prompt.py
```

<details><summary>sub_agents/data_analyst/agent.py (click to expand)</summary>

```python
from google.adk import Agent
from google.adk.tools import google_search
from . import prompt
MODEL = "gemini-2.5-pro"
data_analyst_agent = Agent(
    model=MODEL, name="data_analyst_agent",
    instruction=prompt.DATA_ANALYST_PROMPT,
    output_key="market_data_analysis_output",
    tools=[google_search],
)
```

</details>

<details><summary>sub_agents/trading_analyst/agent.py (click to expand)</summary>

```python
from google.adk import Agent
from . import prompt
MODEL = "gemini-2.5-pro"
trading_analyst_agent = Agent(
    model=MODEL, name="trading_analyst_agent",
    instruction=prompt.TRADING_ANALYST_PROMPT,
    output_key="proposed_trading_strategies_output",
)
```

</details>

<details><summary>sub_agents/execution_analyst/agent.py (click to expand)</summary>

```python
from google.adk import Agent
from . import prompt
MODEL = "gemini-2.5-pro"
execution_analyst_agent = Agent(
    model=MODEL, name="execution_analyst_agent",
    instruction=prompt.EXECUTION_ANALYST_PROMPT,
    output_key="execution_plan_output",
)
```

</details>

<details><summary>sub_agents/risk_analyst/agent.py (click to expand)</summary>

```python
from google.adk import Agent
from . import prompt
MODEL = "gemini-2.5-pro"
risk_analyst_agent = Agent(
    model=MODEL, name="risk_analyst_agent",
    instruction=prompt.RISK_ANALYST_PROMPT,
    output_key="final_risk_assessment_output",
)
```

</details>

```python
# financial_advisor/agent.py
from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool
from . import prompt
from .sub_agents.data_analyst import data_analyst_agent
from .sub_agents.execution_analyst import execution_analyst_agent
from .sub_agents.risk_analyst import risk_analyst_agent
from .sub_agents.trading_analyst import trading_analyst_agent

MODEL = "gemini-2.5-pro"

financial_coordinator = LlmAgent(
    name="financial_coordinator",
    model=MODEL,
    description=(
        "guide users through a structured process to receive financial "
        "advice by orchestrating a series of expert subagents..."
    ),
    instruction=prompt.FINANCIAL_COORDINATOR_PROMPT,
    output_key="financial_coordinator_output",
    tools=[
        AgentTool(agent=data_analyst_agent),
        AgentTool(agent=trading_analyst_agent),
        AgentTool(agent=execution_analyst_agent),
        AgentTool(agent=risk_analyst_agent),
    ],
)
root_agent = financial_coordinator
```

## Fluent API

2 files, flat directory:

```
financial_advisor/
├── __init__.py
├── agent.py
└── prompt.py
```

```python
# agent.py
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

load_dotenv()

MODEL = "gemini-2.5-pro"

data_analyst = (
    Agent("data_analyst_agent", MODEL)
    .instruct(DATA_ANALYST_PROMPT)
    .tool(google_search)
    .outputs("market_data_analysis_output")
)

trading_analyst = (
    Agent("trading_analyst_agent", MODEL)
    .instruct(TRADING_ANALYST_PROMPT)
    .outputs("proposed_trading_strategies_output")
)

execution_analyst = (
    Agent("execution_analyst_agent", MODEL)
    .instruct(EXECUTION_ANALYST_PROMPT)
    .outputs("execution_plan_output")
)

risk_analyst = (
    Agent("risk_analyst_agent", MODEL)
    .instruct(RISK_ANALYST_PROMPT)
    .outputs("final_risk_assessment_output")
)

root_agent = (
    Agent("financial_coordinator", MODEL)
    .describe(
        "guide users through a structured process to receive financial "
        "advice by orchestrating a series of expert subagents"
    )
    .instruct(FINANCIAL_COORDINATOR_PROMPT)
    .outputs("financial_coordinator_output")
    .delegate(data_analyst)
    .delegate(trading_analyst)
    .delegate(execution_analyst)
    .delegate(risk_analyst)
    .build()
)
```

## What Changed

- 4x `AgentTool(agent=...)` → `.delegate()`
- `output_key=` → `.outputs()`
- `instruction=` → `.instruct()`
- `description=` → `.describe()`
- 8+ files across 5 directories → 2 files in 1 directory
- No `__init__.py` re-export chain needed
- No separate sub-agent packages

## Metrics

| Metric                 | Native | Fluent | Reduction |
| ---------------------- | ------ | ------ | --------- |
| Agent definition files | 5      | 1      | 80%       |
| Total Python files     | 10     | 3      | 70%       |
| Directories            | 5      | 1      | 80%       |
| `import` statements    | 15+    | 5      | 67%       |
