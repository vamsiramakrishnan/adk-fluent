# Deep Search

A multi-agent research system that iteratively searches the web, evaluates
research quality in a loop, and composes a fully cited report. This is the
most complex ADK sample port, featuring nested pipeline/loop composition,
a custom `BaseAgent` subclass, structured output with Pydantic, and multiple
callback functions.

## Architecture

```
interactive_planner_agent
  |
  |-- tool: plan_generator (AgentTool)
  |
  +-- sub_agent: research_pipeline (Pipeline)
        |
        +-- step 1: section_planner
        +-- step 2: section_researcher
        +-- step 3: iterative_refinement_loop (Loop, max 5)
        |     +-- research_evaluator (output_schema: Feedback)
        |     +-- EscalationChecker (custom BaseAgent)
        |     +-- enhanced_search_executor
        +-- step 4: report_composer_with_citations
```

## Native ADK

The original is a single ~250 line file with deeply nested constructor calls:

```python
import datetime, re
from collections.abc import AsyncGenerator
from typing import Literal
from google.adk.agents import BaseAgent, LlmAgent, LoopAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.adk.planners import BuiltInPlanner
from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool
from google.genai import types as genai_types
from pydantic import BaseModel, Field


class SearchQuery(BaseModel):
    search_query: str = Field(description="A specific search query.")

class Feedback(BaseModel):
    grade: Literal["pass", "fail"] = Field(description="pass/fail")
    comment: str = Field(description="Detailed evaluation explanation")
    follow_up_queries: list[SearchQuery] | None = Field(default=None)


def collect_research_sources_callback(callback_context):
    session = callback_context._invocation_context.session
    url_to_short_id = callback_context.state.get("url_to_short_id", {})
    sources = callback_context.state.get("sources", {})
    id_counter = len(url_to_short_id) + 1
    for event in session.events:
        if not (event.grounding_metadata and event.grounding_metadata.grounding_chunks):
            continue
        chunks_info = {}
        for idx, chunk in enumerate(event.grounding_metadata.grounding_chunks):
            if not chunk.web:
                continue
            url = chunk.web.uri
            title = chunk.web.title if chunk.web.title != chunk.web.domain else chunk.web.domain
            if url not in url_to_short_id:
                short_id = f"src-{id_counter}"
                url_to_short_id[url] = short_id
                sources[short_id] = {
                    "short_id": short_id, "title": title, "url": url,
                    "domain": chunk.web.domain, "supported_claims": [],
                }
                id_counter += 1
            chunks_info[idx] = url_to_short_id[url]
        if event.grounding_metadata.grounding_supports:
            for support in event.grounding_metadata.grounding_supports:
                confidence_scores = support.confidence_scores or []
                chunk_indices = support.grounding_chunk_indices or []
                for i, chunk_idx in enumerate(chunk_indices):
                    if chunk_idx in chunks_info:
                        short_id = chunks_info[chunk_idx]
                        confidence = confidence_scores[i] if i < len(confidence_scores) else 0.5
                        text_segment = support.segment.text if support.segment else ""
                        sources[short_id]["supported_claims"].append(
                            {"text_segment": text_segment, "confidence": confidence}
                        )
    callback_context.state["url_to_short_id"] = url_to_short_id
    callback_context.state["sources"] = sources


def citation_replacement_callback(callback_context):
    final_report = callback_context.state.get("final_cited_report", "")
    sources = callback_context.state.get("sources", {})
    def tag_replacer(match):
        short_id = match.group(1)
        if not (source_info := sources.get(short_id)):
            return ""
        display_text = source_info.get("title", source_info.get("domain", short_id))
        return f" [{display_text}]({source_info['url']})"
    processed_report = re.sub(
        r'<cite\s+source\s*=\s*["\']?\s*(src-\d+)\s*["\']?\s*/>', tag_replacer, final_report
    )
    processed_report = re.sub(r"\s+([.,;:])", r"\1", processed_report)
    callback_context.state["final_report_with_citations"] = processed_report
    return genai_types.Content(parts=[genai_types.Part(text=processed_report)])


class EscalationChecker(BaseAgent):
    """Checks if grade is 'pass' and escalates to stop the loop."""
    def __init__(self, name):
        super().__init__(name=name)

    async def _run_async_impl(self, ctx):
        evaluation_result = ctx.session.state.get("research_evaluation")
        if evaluation_result and evaluation_result.get("grade") == "pass":
            yield Event(author=self.name, actions=EventActions(escalate=True))
        else:
            yield Event(author=self.name)


plan_generator = LlmAgent(
    model="gemini-2.5-pro",
    name="plan_generator",
    description="Generates research plan",
    instruction="...",  # long prompt omitted
    tools=[google_search],
)

section_planner = LlmAgent(
    model="gemini-2.5-pro",
    name="section_planner",
    description="Breaks plan into report sections",
    instruction="...",
    output_key="report_sections",
)

section_researcher = LlmAgent(
    model="gemini-2.5-pro",
    name="section_researcher",
    description="Performs web research",
    planner=BuiltInPlanner(
        thinking_config=genai_types.ThinkingConfig(include_thoughts=True)
    ),
    instruction="...",
    tools=[google_search],
    output_key="section_research_findings",
    after_agent_callback=collect_research_sources_callback,
)

research_evaluator = LlmAgent(
    model="gemini-2.5-pro",
    name="research_evaluator",
    description="Evaluates research quality",
    instruction="...",
    output_schema=Feedback,
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
    output_key="research_evaluation",
)

enhanced_search_executor = LlmAgent(
    model="gemini-2.5-pro",
    name="enhanced_search_executor",
    description="Executes follow-up searches",
    planner=BuiltInPlanner(
        thinking_config=genai_types.ThinkingConfig(include_thoughts=True)
    ),
    instruction="...",
    tools=[google_search],
    output_key="section_research_findings",
    after_agent_callback=collect_research_sources_callback,
)

report_composer = LlmAgent(
    model="gemini-2.5-pro",
    name="report_composer_with_citations",
    include_contents="none",
    description="Composes final cited report",
    instruction="...",
    output_key="final_cited_report",
    after_agent_callback=citation_replacement_callback,
)

research_pipeline = SequentialAgent(
    name="research_pipeline",
    description="Executes research plan with iterative refinement",
    sub_agents=[
        section_planner,
        section_researcher,
        LoopAgent(
            name="iterative_refinement_loop",
            max_iterations=5,
            sub_agents=[
                research_evaluator,
                EscalationChecker(name="escalation_checker"),
                enhanced_search_executor,
            ],
        ),
        report_composer,
    ],
)

interactive_planner_agent = LlmAgent(
    name="interactive_planner_agent",
    model="gemini-2.5-pro",
    description="Primary research assistant",
    instruction="...",
    sub_agents=[research_pipeline],
    tools=[AgentTool(plan_generator)],
    output_key="research_plan",
)

root_agent = interactive_planner_agent
```

## Fluent API

2 files, flat directory:

```
deep_search/
  __init__.py
  prompt.py      # Prompts, Pydantic models, callbacks, EscalationChecker
  agent.py        # Fluent agent definitions
```

<details><summary>deep_search/prompt.py (click to expand)</summary>

```python
"""Prompts, Pydantic models, callbacks, and custom BaseAgent for Deep Search."""

import re
from collections.abc import AsyncGenerator
from typing import Literal

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types as genai_types
from pydantic import BaseModel, Field


# --- Pydantic Models ---

class SearchQuery(BaseModel):
    search_query: str = Field(description="A specific search query for web search.")

class Feedback(BaseModel):
    grade: Literal["pass", "fail"] = Field(description="pass/fail")
    comment: str = Field(description="Detailed evaluation explanation")
    follow_up_queries: list[SearchQuery] | None = Field(default=None)


# --- Prompts (7 constants, ~30 lines each) ---

PLAN_GENERATOR_PROMPT = "..."       # Research strategist, 5-point plan
SECTION_PLANNER_PROMPT = "..."      # Report architect, 4-6 sections
SECTION_RESEARCHER_PROMPT = "..."   # Two-phase: gather + synthesise
RESEARCH_EVALUATOR_PROMPT = "..."   # QA analyst, pass/fail + follow-ups
ENHANCED_SEARCH_PROMPT = "..."      # Execute follow-up queries
REPORT_COMPOSER_PROMPT = "..."      # Compose cited report
INTERACTIVE_PLANNER_PROMPT = "..."  # Planning assistant


# --- Callbacks ---

def collect_research_sources_callback(callback_context):
    """Extract grounding URLs/titles from session events into state."""
    ...

def citation_replacement_callback(callback_context):
    """Replace <cite source="src-N"/> tags with markdown links."""
    ...


# --- Custom BaseAgent ---

class EscalationChecker(BaseAgent):
    """Check if grade == 'pass' and escalate to exit the loop."""

    async def _run_async_impl(self, ctx):
        evaluation_result = ctx.session.state.get("research_evaluation")
        if evaluation_result and evaluation_result.get("grade") == "pass":
            yield Event(author=self.name, actions=EventActions(escalate=True))
        else:
            yield Event(author=self.name)
```

</details>

```python
# deep_search/agent.py

import datetime

from adk_fluent import Agent, until
from dotenv import load_dotenv
from google.adk.planners import BuiltInPlanner
from google.adk.tools import google_search
from google.genai import types as genai_types

from .prompt import (
    Feedback,
    ENHANCED_SEARCH_PROMPT,
    INTERACTIVE_PLANNER_PROMPT,
    PLAN_GENERATOR_PROMPT,
    REPORT_COMPOSER_PROMPT,
    RESEARCH_EVALUATOR_PROMPT,
    SECTION_PLANNER_PROMPT,
    SECTION_RESEARCHER_PROMPT,
    citation_replacement_callback,
    collect_research_sources_callback,
)

load_dotenv()

MODEL = "gemini-2.5-pro"
MAX_ITERATIONS = 5
TODAY = datetime.datetime.now().strftime("%Y-%m-%d")

thinking = BuiltInPlanner(
    thinking_config=genai_types.ThinkingConfig(include_thoughts=True)
)

# --- Agent definitions ---

plan_generator = (
    Agent("plan_generator", MODEL)
    .describe("Generates or refines research plans.")
    .instruct(PLAN_GENERATOR_PROMPT.format(today=TODAY))
    .tool(google_search)
)

section_planner = (
    Agent("section_planner", MODEL)
    .describe("Breaks down the research plan into report sections.")
    .instruct(SECTION_PLANNER_PROMPT)
    .outputs("report_sections")
)

section_researcher = (
    Agent("section_researcher", MODEL)
    .describe("Performs the first pass of web research.")
    .planner(thinking)
    .instruct(SECTION_RESEARCHER_PROMPT)
    .tool(google_search)
    .outputs("section_research_findings")
    .after_agent(collect_research_sources_callback)
)

research_evaluator = (
    Agent("research_evaluator", MODEL)
    .describe("Critically evaluates research quality.")
    .instruct(RESEARCH_EVALUATOR_PROMPT.format(today=TODAY))
    .disallow_transfer_to_parent(True)
    .disallow_transfer_to_peers(True)
    .outputs("research_evaluation")
) @ Feedback

enhanced_search = (
    Agent("enhanced_search_executor", MODEL)
    .describe("Executes follow-up searches.")
    .planner(thinking)
    .instruct(ENHANCED_SEARCH_PROMPT)
    .tool(google_search)
    .outputs("section_research_findings")
    .after_agent(collect_research_sources_callback)
)

report_composer = (
    Agent("report_composer_with_citations", MODEL)
    .history("none")
    .describe("Composes the final cited report.")
    .instruct(REPORT_COMPOSER_PROMPT)
    .outputs("final_cited_report")
    .after_agent(citation_replacement_callback)
)

# --- Composition ---
#
# >> creates Pipeline (SequentialAgent)
# * until(...) creates Loop that exits when predicate is satisfied,
#   replacing the manual EscalationChecker BaseAgent entirely

refinement_loop = (
    research_evaluator >> enhanced_search
) * until(
    lambda s: s.get("research_evaluation", {}).get("grade") == "pass",
    max=MAX_ITERATIONS,
)

research_pipeline = (
    section_planner >> section_researcher >> refinement_loop >> report_composer
).name("research_pipeline").describe(
    "Executes research with iterative refinement and composes cited report."
)

root_agent = (
    Agent("interactive_planner_agent", MODEL)
    .describe("The primary research assistant.")
    .instruct(INTERACTIVE_PLANNER_PROMPT.format(today=TODAY))
    .sub_agents([research_pipeline.build()])
    .delegate(plan_generator)
    .outputs("research_plan")
    .build()
)
```

## What Changed

### Pipeline operator `>>`

Native ADK requires nesting `SequentialAgent` and `LoopAgent` constructors
with explicit `sub_agents=` lists. The `>>` operator replaces all of this:

```python
# Native — nested constructors with keyword arguments
research_pipeline = SequentialAgent(
    name="research_pipeline",
    sub_agents=[
        section_planner,
        section_researcher,
        LoopAgent(
            name="iterative_refinement_loop",
            max_iterations=5,
            sub_agents=[
                research_evaluator,
                EscalationChecker(name="escalation_checker"),
                enhanced_search_executor,
            ],
        ),
        report_composer,
    ],
)
```

```python
# Fluent — >> operator chains, * until() replaces EscalationChecker
refinement_loop = (
    research_evaluator >> enhanced_search
) * until(
    lambda s: s.get("research_evaluation", {}).get("grade") == "pass",
    max=MAX_ITERATIONS,
)

research_pipeline = (
    section_planner >> section_researcher >> refinement_loop >> report_composer
).name("research_pipeline")
```

### Loop with `* until()` — eliminates custom BaseAgent

The original requires a 30-line `EscalationChecker(BaseAgent)` subclass that
checks `state["research_evaluation"]["grade"] == "pass"` and emits
`EventActions(escalate=True)`. The `* until()` operator replaces this entirely
with a one-line predicate:

```python
# Native — 30+ lines of custom BaseAgent code
class EscalationChecker(BaseAgent):
    async def _run_async_impl(self, ctx):
        evaluation_result = ctx.session.state.get("research_evaluation")
        if evaluation_result and evaluation_result.get("grade") == "pass":
            yield Event(author=self.name, actions=EventActions(escalate=True))
        else:
            yield Event(author=self.name)

# Fluent — one-line predicate, no custom code
refinement_loop = (evaluator >> search) * until(
    lambda s: s.get("research_evaluation", {}).get("grade") == "pass",
    max=5,
)
```

### Typed output with `@` operator

```python
# Native
research_evaluator = LlmAgent(
    ...,
    output_schema=Feedback,
    output_key="research_evaluation",
)

# Fluent — @ binds the Pydantic schema
research_evaluator = (
    Agent("research_evaluator", MODEL)
    ...
    .outputs("research_evaluation")
) @ Feedback
```

### Include contents / history

```python
# Native
report_composer = LlmAgent(
    ...,
    include_contents="none",
)

# Fluent
report_composer = (
    Agent("report_composer_with_citations", MODEL)
    .history("none")
    ...
)
```

### Callbacks

```python
# Native
after_agent_callback=collect_research_sources_callback

# Fluent
.after_agent(collect_research_sources_callback)
```

### Planner and thinking config

```python
# Native — repeated inline construction
section_researcher = LlmAgent(
    ...,
    planner=BuiltInPlanner(
        thinking_config=genai_types.ThinkingConfig(include_thoughts=True)
    ),
)

# Fluent — define once, reuse
thinking = BuiltInPlanner(
    thinking_config=genai_types.ThinkingConfig(include_thoughts=True)
)

section_researcher = (
    Agent("section_researcher", MODEL)
    .planner(thinking)
    ...
)
```

## Metrics

| Metric                                                  | Native         | Fluent                    | Reduction          |
| ------------------------------------------------------- | -------------- | ------------------------- | ------------------ |
| Agent definition files                                  | 1 (250+ lines) | 2 (prompt.py + agent.py)  | Separated concerns |
| Nesting depth (constructors)                            | 4 levels       | 0 (flat operators)        | 100%               |
| `import` statements (agent file)                        | 13             | 9                         | 31%                |
| Boilerplate keywords (`name=`, `model=`, `sub_agents=`) | 30+            | 0                         | 100%               |
| Lines for pipeline composition                          | 18             | 7                         | 61%                |
| Custom `BaseAgent` code for loop control                | 30+ lines      | 0 (replaced by `until()`) | 100%               |
