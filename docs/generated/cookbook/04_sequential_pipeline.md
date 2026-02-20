# Document Processing Pipeline -- Sequential Pipeline

Demonstrates a SequentialAgent that chains steps in order.  The
scenario: a document processing pipeline that extracts key data
from a contract, analyzes legal risks, then produces an executive
summary.

*How to compose agents into a sequential pipeline.*

_Source: `04_sequential_pipeline.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.sequential_agent import SequentialAgent

extractor = LlmAgent(
    name="extractor",
    model="gemini-2.5-flash",
    instruction=(
        "Extract key terms from the contract: parties involved, "
        "effective dates, payment terms, and termination clauses."
    ),
)
analyst = LlmAgent(
    name="risk_analyst",
    model="gemini-2.5-flash",
    instruction=(
        "Analyze the extracted terms for legal risks. Flag any "
        "unusual clauses, missing protections, or liability concerns."
    ),
)
summarizer = LlmAgent(
    name="summarizer",
    model="gemini-2.5-flash",
    instruction=(
        "Produce a one-page executive summary combining the extracted "
        "terms and risk analysis. Use clear, non-legal language."
    ),
)
pipeline_native = SequentialAgent(
    name="contract_review",
    description="Extract, analyze, and summarize contracts",
    sub_agents=[extractor, analyst, summarizer],
)
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, Pipeline

pipeline_fluent = (
    Pipeline("contract_review")
    .describe("Extract, analyze, and summarize contracts")
    .step(
        Agent("extractor")
        .model("gemini-2.5-flash")
        .instruct(
            "Extract key terms from the contract: parties involved, "
            "effective dates, payment terms, and termination clauses."
        )
    )
    .step(
        Agent("risk_analyst")
        .model("gemini-2.5-flash")
        .instruct(
            "Analyze the extracted terms for legal risks. Flag any "
            "unusual clauses, missing protections, or liability concerns."
        )
    )
    .step(
        Agent("summarizer")
        .model("gemini-2.5-flash")
        .instruct(
            "Produce a one-page executive summary combining the extracted "
            "terms and risk analysis. Use clear, non-legal language."
        )
    )
    .build()
)
```
:::
::::

## Equivalence

```python
assert type(pipeline_native) == type(pipeline_fluent)
assert len(pipeline_fluent.sub_agents) == 3
assert pipeline_fluent.sub_agents[0].name == "extractor"
assert pipeline_fluent.sub_agents[1].name == "risk_analyst"
assert pipeline_fluent.sub_agents[2].name == "summarizer"
```

:::{seealso}
API reference: [Pipeline](../api/workflow.md#builder-Pipeline)
:::
