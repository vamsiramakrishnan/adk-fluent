# Brand Search Optimization

A multi-agent system that helps e-commerce teams optimize product titles for search visibility. A root router agent orchestrates three sub-agents: keyword finding (BigQuery), search results browsing (Selenium), and comparison reporting (generator + critic loop).

## Architecture

root_agent (router) → keyword_finding_agent, search_results_agent, comparison_root_agent → [comparison_generator_agent, comparison_critic_agent]

## Native ADK

The original uses 12 files across 6 directories:

```
brand_search_optimization/
├── __init__.py
├── agent.py
├── prompt.py
├── shared_libraries/
│   ├── __init__.py
│   └── constants.py
├── tools/
│   ├── __init__.py
│   └── bq_connector.py
└── sub_agents/
    ├── keyword_finding/
    │   ├── __init__.py
    │   ├── agent.py
    │   └── prompt.py
    ├── search_results/
    │   ├── __init__.py
    │   ├── agent.py
    │   └── prompt.py
    └── comparison/
        ├── __init__.py
        ├── agent.py
        └── prompt.py
```

<details><summary>shared_libraries/constants.py (click to expand)</summary>

```python
MODEL = "gemini-2.5-flash"
AGENT_NAME = "brand_search_optimization"
DESCRIPTION = "A helpful assistant for brand search optimization."
```

</details>

<details><summary>sub_agents/keyword_finding/agent.py (click to expand)</summary>

```python
from google.adk.agents.llm_agent import Agent
from ...shared_libraries import constants
from ...tools import bq_connector
from . import prompt

keyword_finding_agent = Agent(
    model=constants.MODEL,
    name="keyword_finding_agent",
    description="A helpful agent to find keywords",
    instruction=prompt.KEYWORD_FINDING_AGENT_PROMPT,
    tools=[bq_connector.get_product_details_for_brand],
)
```

</details>

<details><summary>sub_agents/search_results/agent.py (click to expand)</summary>

```python
from google.adk.agents.llm_agent import Agent
from google.adk.tools.load_artifacts_tool import load_artifacts_tool
from ...shared_libraries import constants
from . import prompt
# ... 9 Selenium tool function imports ...

search_results_agent = Agent(
    model=constants.MODEL,
    name="search_results_agent",
    description="Get top 3 search results info for a keyword using web browsing",
    instruction=prompt.SEARCH_RESULT_AGENT_PROMPT,
    tools=[go_to_url, take_screenshot, find_element_with_text,
           click_element_with_text, enter_text_into_element,
           scroll_down_screen, get_page_source, load_artifacts_tool,
           analyze_webpage_and_determine_action],
)
```

</details>

<details><summary>sub_agents/comparison/agent.py (click to expand)</summary>

```python
from google.adk.agents.llm_agent import Agent
from ...shared_libraries import constants
from . import prompt

comparison_generator_agent = Agent(
    model=constants.MODEL,
    name="comparison_generator_agent",
    description="A helpful agent to generate comparison.",
    instruction=prompt.COMPARISON_AGENT_PROMPT,
)

comparsion_critic_agent = Agent(
    model=constants.MODEL,
    name="comparison_critic_agent",
    description="A helpful agent to critique comparison.",
    instruction=prompt.COMPARISON_CRITIC_AGENT_PROMPT,
)

comparison_root_agent = Agent(
    model=constants.MODEL,
    name="comparison_root_agent",
    description="A helpful agent to compare titles",
    instruction=prompt.COMPARISON_ROOT_AGENT_PROMPT,
    sub_agents=[comparison_generator_agent, comparsion_critic_agent],
)
```

</details>

<details><summary>agent.py — root (click to expand)</summary>

```python
from google.adk.agents.llm_agent import Agent
from . import prompt
from .shared_libraries import constants
from .sub_agents.comparison.agent import comparison_root_agent
from .sub_agents.keyword_finding.agent import keyword_finding_agent
from .sub_agents.search_results.agent import search_results_agent

root_agent = Agent(
    model=constants.MODEL,
    name=constants.AGENT_NAME,
    description=constants.DESCRIPTION,
    instruction=prompt.ROOT_PROMPT,
    sub_agents=[keyword_finding_agent, search_results_agent, comparison_root_agent],
)
```

</details>

## Fluent API

4 files, flat directory:

```python
# agent.py
from adk_fluent import Agent
from dotenv import load_dotenv

from .prompt import (
    COMPARISON_CRITIC_PROMPT, COMPARISON_PROMPT, COMPARISON_ROOT_PROMPT,
    KEYWORD_FINDING_PROMPT, ROOT_PROMPT, SEARCH_RESULTS_PROMPT,
)
from .tools import (
    analyze_webpage, click_element_with_text, enter_text_into_element,
    find_element_with_text, get_page_source, get_product_details_for_brand,
    go_to_url, scroll_down_screen, take_screenshot,
)

load_dotenv()

MODEL = "gemini-2.5-flash"

# --- Sub-agents ---

keyword_finding = (
    Agent("keyword_finding_agent", MODEL)
    .describe("A helpful agent to find keywords")
    .instruct(KEYWORD_FINDING_PROMPT)
    .tool(get_product_details_for_brand)
)

search_results = (
    Agent("search_results_agent", MODEL)
    .describe("Get top 3 search results info for a keyword using web browsing")
    .instruct(SEARCH_RESULTS_PROMPT)
    .tool(go_to_url)
    .tool(take_screenshot)
    .tool(find_element_with_text)
    .tool(click_element_with_text)
    .tool(enter_text_into_element)
    .tool(scroll_down_screen)
    .tool(get_page_source)
    .tool(analyze_webpage)
)

# Comparison: generator + critic loop, managed by a routing sub-agent

comparison_generator = (
    Agent("comparison_generator_agent", MODEL)
    .describe("A helpful agent to generate comparison.")
    .instruct(COMPARISON_PROMPT)
)

comparison_critic = (
    Agent("comparison_critic_agent", MODEL)
    .describe("A helpful agent to critique comparison.")
    .instruct(COMPARISON_CRITIC_PROMPT)
)

comparison_root = (
    Agent("comparison_root_agent", MODEL)
    .describe("A helpful agent to compare titles")
    .instruct(COMPARISON_ROOT_PROMPT)
    .sub_agents([comparison_generator.build(), comparison_critic.build()])
)

# --- Root agent ---

root_agent = (
    Agent("brand_search_optimization", MODEL)
    .describe("A helpful assistant for brand search optimization.")
    .instruct(ROOT_PROMPT)
    .sub_agents([
        keyword_finding.build(),
        search_results.build(),
        comparison_root.build(),
    ])
    .build()
)
```

## What Changed

- `constants.MODEL` referenced everywhere → single `MODEL` variable at top of `agent.py`
- `constants.AGENT_NAME`, `constants.DESCRIPTION` → inline strings
- `instruction=prompt.X` → `.instruct(X)`
- `description="..."` → `.describe("...")`
- `tools=[fn1, fn2, ...]` → `.tool(fn1).tool(fn2)...`
- `Agent(sub_agents=[...])` → `.sub_agents([...])`
- Nested sub-agents (comparison_root with generator + critic) work the same way with `.sub_agents()` accepting `.build()` results
- 12 original files across 6 directories → 4 files in 1 directory
- No `shared_libraries/constants.py` needed
- No `__init__.py` chain through sub-agent directories
- Tool functions simplified with stubs (no BigQuery/Selenium dependencies)

## Metrics

| Metric                            | Native | Fluent | Reduction |
| --------------------------------- | ------ | ------ | --------- |
| Agent definition files            | 4      | 1      | 75%       |
| Total files                       | 12     | 4      | 67%       |
| Directories                       | 6      | 1      | 83%       |
| `import` statements (agent files) | 15     | 12     | 20%       |
| Constants/config files            | 1      | 0      | 100%      |
| `__init__.py` files               | 6      | 1      | 83%       |
