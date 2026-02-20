# Market Research Fan-Out -- Parallel FanOut

Demonstrates a ParallelAgent that runs branches concurrently.  The
scenario: a market research system that simultaneously gathers
intelligence from web sources, academic papers, and social media
to produce a comprehensive competitive analysis.

*How to run agents in parallel using FanOut.*

_Source: `05_parallel_fanout.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.parallel_agent import ParallelAgent

fanout_native = ParallelAgent(
    name="market_research",
    sub_agents=[
        LlmAgent(
            name="web_analyst",
            model="gemini-2.5-flash",
            instruction=(
                "Search the web for recent news articles, press releases, "
                "and blog posts about competitors in this market segment."
            ),
        ),
        LlmAgent(
            name="academic_analyst",
            model="gemini-2.5-flash",
            instruction=(
                "Search academic databases for recent research papers and industry reports relevant to this market."
            ),
        ),
        LlmAgent(
            name="social_analyst",
            model="gemini-2.5-flash",
            instruction=(
                "Analyze social media sentiment and trending discussions about products and brands in this market."
            ),
        ),
    ],
)
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, FanOut

fanout_fluent = (
    FanOut("market_research")
    .branch(
        Agent("web_analyst")
        .model("gemini-2.5-flash")
        .instruct(
            "Search the web for recent news articles, press releases, "
            "and blog posts about competitors in this market segment."
        )
    )
    .branch(
        Agent("academic_analyst")
        .model("gemini-2.5-flash")
        .instruct("Search academic databases for recent research papers and industry reports relevant to this market.")
    )
    .branch(
        Agent("social_analyst")
        .model("gemini-2.5-flash")
        .instruct("Analyze social media sentiment and trending discussions about products and brands in this market.")
    )
    .build()
)
```
:::
::::

## Equivalence

```python
assert type(fanout_native) == type(fanout_fluent)
assert len(fanout_fluent.sub_agents) == 3
assert fanout_fluent.sub_agents[0].name == "web_analyst"
assert fanout_fluent.sub_agents[1].name == "academic_analyst"
assert fanout_fluent.sub_agents[2].name == "social_analyst"
```

:::{seealso}
API reference: [FanOut](../api/workflow.md#builder-FanOut)
:::
