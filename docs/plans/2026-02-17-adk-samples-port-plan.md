# ADK Samples Port Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Port 6 complex ADK samples to fluent API with side-by-side comparison docs.

**Architecture:** Each sample gets an `examples/<name>/` directory with `agent.py` + `prompt.py`, and a `docs/user-guide/adk-samples/<name>.md` comparison page. An index page ties them together.

**Tech Stack:** adk-fluent (Python), Sphinx/Markdown docs, Google ADK

______________________________________________________________________

### Task 1: Create directory structure and index page

**Files:**

- Create: `examples/llm_auditor/__init__.py`
- Create: `examples/financial_advisor/__init__.py`
- Create: `examples/short_movie/__init__.py`
- Create: `examples/deep_search/__init__.py`
- Create: `examples/brand_search/__init__.py`
- Create: `examples/travel_concierge/__init__.py`
- Create: `docs/user-guide/adk-samples/index.md`

**Step 1: Create example directories**

```bash
mkdir -p examples/llm_auditor examples/financial_advisor examples/short_movie examples/deep_search examples/brand_search examples/travel_concierge
mkdir -p docs/user-guide/adk-samples
```

**Step 2: Create `__init__.py` files for each example**

Each `__init__.py` follows the same pattern:

```python
from . import agent
```

**Step 3: Create the index page**

Create `docs/user-guide/adk-samples/index.md`:

```markdown
# ADK Samples — Fluent API Ports

These examples port complex multi-agent samples from Google's
[adk-samples](https://github.com/google/adk-samples/tree/main/python/agents)
repository to the adk-fluent API. Each page shows native ADK code alongside
the fluent equivalent, highlighting structural improvements.

| Sample | Pattern | Key Fluent Features |
| ------ | ------- | ------------------- |
| [LLM Auditor](llm-auditor.md) | Sequential pipeline + callbacks | `>>` operator, `.after_model()` |
| [Financial Advisor](financial-advisor.md) | Tool-based delegation + state passing | `.delegate()`, `.outputs()` |
| [Short Movie](short-movie.md) | Sequential creative pipeline + generative tools | `>>` chain, `.outputs()`, custom tools |
| [Deep Search](deep-search.md) | Loop with evaluation + typed output + custom agent | `* until()`, `@ Schema`, nested `Pipeline` |
| [Brand Search](brand-search.md) | Router with nested sub-agents + web tools | `.sub_agents()`, nested agent hierarchies |
| [Travel Concierge](travel-concierge.md) | 6-group orchestrator + callbacks + state | `.delegate()`, massive boilerplate reduction |
```

**Step 4: Commit**

```bash
git add examples/llm_auditor examples/financial_advisor examples/short_movie examples/deep_search examples/brand_search examples/travel_concierge docs/user-guide/adk-samples
git commit -m "chore: scaffold directories for ADK sample ports"
```

______________________________________________________________________

### Task 2: Port LLM Auditor

**Files:**

- Create: `examples/llm_auditor/agent.py`
- Create: `examples/llm_auditor/prompt.py`
- Create: `docs/user-guide/adk-samples/llm-auditor.md`

**Step 1: Create `examples/llm_auditor/prompt.py`**

Copy the two prompts verbatim from the original sample:

```python
"""Prompts for the LLM Auditor agents."""

CRITIC_PROMPT = """
You are a professional investigative journalist, excelling at critical thinking and verifying information before printed to a highly-trustworthy publication.
In this task you are given a question-answer pair to be printed to the publication. The publication editor tasked you to double-check the answer text.

# Your task

Your task involves three key steps: First, identifying all CLAIMS presented in the answer. Second, determining the reliability of each CLAIM. And lastly, provide an overall assessment.

## Step 1: Identify the CLAIMS

Carefully read the provided answer text. Extract every distinct CLAIM made within the answer. A CLAIM can be a statement of fact about the world or a logical argument presented to support a point.

## Step 2: Verify each CLAIM

For each CLAIM you identified in Step 1, perform the following:

* Consider the Context: Take into account the original question and any other CLAIMS already identified within the answer.
* Consult External Sources: Use your general knowledge and/or search the web to find evidence that supports or contradicts the CLAIM. Aim to consult reliable and authoritative sources.
* Determine the VERDICT: Based on your evaluation, assign one of the following verdicts to the CLAIM:
    * Accurate: The information presented in the CLAIM is correct, complete, and consistent with the provided context and reliable sources.
    * Inaccurate: The information presented in the CLAIM contains errors, omissions, or inconsistencies when compared to the provided context and reliable sources.
    * Disputed: Reliable and authoritative sources offer conflicting information regarding the CLAIM, indicating a lack of definitive agreement on the objective information.
    * Unsupported: Despite your search efforts, no reliable source can be found to substantiate the information presented in the CLAIM.
    * Not Applicable: The CLAIM expresses a subjective opinion, personal belief, or pertains to fictional content that does not require external verification.
* Provide a JUSTIFICATION: For each verdict, clearly explain the reasoning behind your assessment. Reference the sources you consulted or explain why the verdict "Not Applicable" was chosen.

## Step 3: Provide an overall assessment

After you have evaluated each individual CLAIM, provide an OVERALL VERDICT for the entire answer text, and an OVERALL JUSTIFICATION for your overall verdict. Explain how the evaluation of the individual CLAIMS led you to this overall assessment and whether the answer as a whole successfully addresses the original question.

# Tips

Your work is iterative. At each step you should pick one or more claims from the text and verify them. Then, continue to the next claim or claims. You may rely on previous claims to verify the current claim.

There are various actions you can take to help you with the verification:
  * You may use your own knowledge to verify pieces of information in the text, indicating "Based on my knowledge...". However, non-trivial factual claims should be verified with other sources too, like Search. Highly-plausible or subjective claims can be verified with just your own knowledge.
  * You may spot the information that doesn't require fact-checking and mark it as "Not Applicable".
  * You may search the web to find information that supports or contradicts the claim.
  * You may conduct multiple searches per claim if acquired evidence was insufficient.
  * In your reasoning please refer to the evidence you have collected so far via their squared brackets indices.
  * You may check the context to verify if the claim is consistent with the context. Read the context carefully to idenfity specific user instructions that the text should follow, facts that the text should be faithful to, etc.
  * You should draw your final conclusion on the entire text after you acquired all the information you needed.

# Output format

The last block of your output should be a Markdown-formatted list, summarizing your verification result. For each CLAIM you verified, you should output the claim (as a standalone statement), the corresponding part in the answer text, the verdict, and the justification.

Here is the question and answer you are going to double check:
"""

REVISER_PROMPT = """
You are a professional editor working for a highly-trustworthy publication.
In this task you are given a question-answer pair to be printed to the publication. The publication reviewer has double-checked the answer text and provided the findings.
Your task is to minimally revise the answer text to make it accurate, while maintaining the overall structure, style, and length similar to the original.

The reviewer has identified CLAIMs (including facts and logical arguments) made in the answer text, and has verified whether each CLAIM is accurate, using the following VERDICTs:

    * Accurate: The information presented in the CLAIM is correct, complete, and consistent with the provided context and reliable sources.
    * Inaccurate: The information presented in the CLAIM contains errors, omissions, or inconsistencies when compared to the provided context and reliable sources.
    * Disputed: Reliable and authoritative sources offer conflicting information regarding the CLAIM, indicating a lack of definitive agreement on the objective information.
    * Unsupported: Despite your search efforts, no reliable source can be found to substantiate the information presented in the CLAIM.
    * Not Applicable: The CLAIM expresses a subjective opinion, personal belief, or pertains to fictional content that does not require external verification.

Editing guidelines for each type of claim:

  * Accurate claims: There is no need to edit them.
  * Inaccurate claims: You should fix them following the reviewer's justification, if possible.
  * Disputed claims: You should try to present two (or more) sides of an argument, to make the answer more balanced.
  * Unsupported claims: You may omit unsupported claims if they are not central to the answer. Otherwise you may soften the claims or express that they are unsupported.
  * Not applicable claims: There is no need to edit them.

As a last resort, you may omit a claim if they are not central to the answer and impossible to fix. You should also make necessary edits to ensure that the revised answer is self-consistent and fluent. You should not introduce any new claims or make any new statements in the answer text. Your edit should be minimal and maintain overall structure and style unchanged.

Output format:

  * If the answer is accurate, you should output exactly the same answer text as you are given.
  * If the answer is inaccurate, disputed, or unsupported, then you should output your revised answer text.
  * After the answer, output a line of "---END-OF-EDIT---" and stop.

Here is the question-answer pair and the reviewer-provided findings:
"""

END_OF_EDIT_MARK = "---END-OF-EDIT---"
```

**Step 2: Create `examples/llm_auditor/agent.py`**

```python
"""
LLM Auditor — Fluent API Port

Verifies & refines LLM-generated answers using web search.
Original: https://github.com/google/adk-samples/tree/main/python/agents/llm-auditor

Usage:
    cd examples
    adk web llm_auditor
"""

from adk_fluent import Agent
from dotenv import load_dotenv
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse
from google.adk.tools import google_search
from google.genai import types

from .prompt import CRITIC_PROMPT, END_OF_EDIT_MARK, REVISER_PROMPT

load_dotenv()


# --- Callbacks (unchanged from original) ---

def _render_reference(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> LlmResponse:
    """Appends grounding references to the response."""
    del callback_context
    if (
        not llm_response.content
        or not llm_response.content.parts
        or not llm_response.grounding_metadata
    ):
        return llm_response
    references = []
    for chunk in llm_response.grounding_metadata.grounding_chunks or []:
        title, uri, text = "", "", ""
        if chunk.retrieved_context:
            title = chunk.retrieved_context.title
            uri = chunk.retrieved_context.uri
            text = chunk.retrieved_context.text
        elif chunk.web:
            title = chunk.web.title
            uri = chunk.web.uri
        parts = [s for s in (title, text) if s]
        if uri and parts:
            parts[0] = f"[{parts[0]}]({uri})"
        if parts:
            references.append("* " + ": ".join(parts) + "\n")
    if references:
        reference_text = "".join(["\n\nReference:\n\n", *references])
        llm_response.content.parts.append(types.Part(text=reference_text))
        if all(part.text is not None for part in llm_response.content.parts):
            all_text = "\n".join(
                part.text for part in llm_response.content.parts
            )
            llm_response.content.parts[0].text = all_text
            del llm_response.content.parts[1:]
    return llm_response


def _remove_end_of_edit_mark(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> LlmResponse:
    del callback_context
    if not llm_response.content or not llm_response.content.parts:
        return llm_response
    for idx, part in enumerate(llm_response.content.parts):
        if END_OF_EDIT_MARK in part.text:
            del llm_response.content.parts[idx + 1 :]
            part.text = part.text.split(END_OF_EDIT_MARK, 1)[0]
    return llm_response


# --- Agent definition: 2 agents composed with >> ---

critic = (
    Agent("critic_agent", "gemini-2.5-flash")
    .instruct(CRITIC_PROMPT)
    .tool(google_search)
    .after_model(_render_reference)
)

reviser = (
    Agent("reviser_agent", "gemini-2.5-flash")
    .instruct(REVISER_PROMPT)
    .after_model(_remove_end_of_edit_mark)
)

# The >> operator creates a SequentialAgent (Pipeline) — identical to the
# original SequentialAgent(sub_agents=[critic_agent, reviser_agent])
root_agent = (critic >> reviser).build()
root_agent.name = "llm_auditor"
root_agent.description = (
    "Evaluates LLM-generated answers, verifies actual accuracy using the"
    " web, and refines the response to ensure alignment with real-world"
    " knowledge."
)
```

**Step 3: Create `docs/user-guide/adk-samples/llm-auditor.md`**

Create the side-by-side comparison doc. (Content provided in full in the actual file — includes native ADK code, fluent code, "What Changed" section, and metrics table.)

**Step 4: Commit**

```bash
git add examples/llm_auditor/ docs/user-guide/adk-samples/llm-auditor.md
git commit -m "feat: port LLM Auditor sample to fluent API with comparison docs"
```

______________________________________________________________________

### Task 3: Port Financial Advisor

**Files:**

- Create: `examples/financial_advisor/agent.py`
- Create: `examples/financial_advisor/prompt.py`
- Create: `docs/user-guide/adk-samples/financial-advisor.md`

**Step 1: Create `examples/financial_advisor/prompt.py`**

Copy all 5 prompts verbatim from the original: `FINANCIAL_COORDINATOR_PROMPT`, `DATA_ANALYST_PROMPT`, `TRADING_ANALYST_PROMPT`, `EXECUTION_ANALYST_PROMPT`, `RISK_ANALYST_PROMPT`.

**Step 2: Create `examples/financial_advisor/agent.py`**

```python
"""
Financial Advisor — Fluent API Port

Multi-agent financial advisory system with data analysis, trading strategies,
execution planning, and risk evaluation.
Original: https://github.com/google/adk-samples/tree/main/python/agents/financial-advisor

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

load_dotenv()

MODEL = "gemini-2.5-pro"

# --- Sub-agents ---

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

# --- Root agent: delegates to sub-agents via AgentTool ---

root_agent = (
    Agent("financial_coordinator", MODEL)
    .describe(
        "guide users through a structured process to receive financial "
        "advice by orchestrating a series of expert subagents. help them "
        "analyze a market ticker, develop trading strategies, define "
        "execution plans, and evaluate the overall risk."
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

**Step 3: Create comparison doc**

Create `docs/user-guide/adk-samples/financial-advisor.md` with side-by-side comparison.

Key metrics to highlight:

- Native: 8 Python files across 5 directories, ~50 LOC of agent definitions + imports
- Fluent: 2 files, ~45 LOC of agent definitions
- Key wins: no `AgentTool` imports, no `__init__.py` re-exports, flat structure

**Step 4: Commit**

```bash
git add examples/financial_advisor/ docs/user-guide/adk-samples/financial-advisor.md
git commit -m "feat: port Financial Advisor sample to fluent API with comparison docs"
```

______________________________________________________________________

### Task 4: Port Short Movie Agents

**Files:**

- Create: `examples/short_movie/agent.py`
- Create: `examples/short_movie/prompt.py`
- Create: `examples/short_movie/tools.py`
- Create: `docs/user-guide/adk-samples/short-movie.md`

**Step 1: Create `examples/short_movie/prompt.py`**

Copy prompts verbatim. Since the original loads from `.txt` files, inline them as Python constants: `DIRECTOR_PROMPT`, `STORY_PROMPT`, `STORY_DESC`, `SCREENPLAY_PROMPT`, `STORYBOARD_PROMPT`, `VIDEO_PROMPT`.

**Step 2: Create `examples/short_movie/tools.py`**

Copy the `storyboard_generate` and `video_generate` tool functions verbatim from the original. These are infrastructure tools that call Vertex AI APIs and remain unchanged.

**Step 3: Create `examples/short_movie/agent.py`**

```python
"""
Short Movie Agents — Fluent API Port

Orchestrates story → screenplay → storyboard → video pipeline.
Original: https://github.com/google/adk-samples/tree/main/python/agents/short-movie-agents

Usage:
    cd examples
    adk web short_movie
"""

from adk_fluent import Agent
from dotenv import load_dotenv

from .prompt import (
    DIRECTOR_PROMPT,
    SCREENPLAY_PROMPT,
    STORY_DESC,
    STORY_PROMPT,
    STORYBOARD_PROMPT,
    VIDEO_PROMPT,
)
from .tools import storyboard_generate, video_generate

load_dotenv()

MODEL = "gemini-2.5-flash"

# --- Sub-agents ---

story = (
    Agent("story_agent", MODEL)
    .describe(STORY_DESC)
    .instruct(STORY_PROMPT)
    .outputs("story")
)

screenplay = (
    Agent("screenplay_agent", MODEL)
    .describe("Agent responsible for writing a screenplay based on a story")
    .instruct(SCREENPLAY_PROMPT)
    .outputs("screenplay")
)

storyboard = (
    Agent("storyboard_agent", MODEL)
    .describe("Agent responsible for creating storyboards based on a screenplay and story")
    .instruct(STORYBOARD_PROMPT)
    .outputs("storyboard")
    .tool(storyboard_generate)
)

video = (
    Agent("video_agent", MODEL)
    .describe("Agent responsible for creating videos based on a screenplay and storyboards")
    .instruct(VIDEO_PROMPT)
    .outputs("video")
    .tool(video_generate)
)

# --- Root agent: LLM-driven routing to sub-agents ---

root_agent = (
    Agent("director_agent", MODEL)
    .describe(
        "Orchestrates the creation of a short, animated campfire story "
        "based on user input, utilizing specialized sub-agents for story "
        "generation, storyboard creation, and video generation."
    )
    .instruct(DIRECTOR_PROMPT)
    .sub_agents([story.build(), screenplay.build(), storyboard.build(), video.build()])
    .build()
)
```

**Step 4: Create comparison doc**

Create `docs/user-guide/adk-samples/short-movie.md`.

Key metrics:

- Native: 5 agent files + utils + prompt files across nested directories (~200 LOC agent code)
- Fluent: 3 files (agent.py, prompt.py, tools.py), ~50 LOC agent code
- Key wins: no try/except agent creation boilerplate, no `load_prompt_from_file` utility, flat structure

**Step 5: Commit**

```bash
git add examples/short_movie/ docs/user-guide/adk-samples/short-movie.md
git commit -m "feat: port Short Movie Agents sample to fluent API with comparison docs"
```

______________________________________________________________________

### Task 5: Port Deep Search

**Files:**

- Create: `examples/deep_search/agent.py`
- Create: `examples/deep_search/prompt.py`
- Create: `docs/user-guide/adk-samples/deep-search.md`

This is the most complex port. The original uses:

- `SequentialAgent` with nested `LoopAgent`
- Custom `BaseAgent` subclass (`EscalationChecker`)
- Pydantic `output_schema` for structured output
- `BuiltInPlanner` with thinking config
- Two `after_agent_callback` functions
- `include_contents="none"` and `disallow_transfer_*` flags

**Step 1: Create `examples/deep_search/prompt.py`**

Copy all prompt strings and the Pydantic models (`SearchQuery`, `Feedback`) verbatim. Also copy the two callback functions (`collect_research_sources_callback`, `citation_replacement_callback`) and the `EscalationChecker` class — these are domain logic that the fluent API wraps but doesn't replace.

**Step 2: Create `examples/deep_search/agent.py`**

```python
"""
Deep Search — Fluent API Port

Multi-agent research system with iterative search, evaluation loops,
and cited report generation.
Original: https://github.com/google/adk-samples/tree/main/python/agents/deep-search

Usage:
    cd examples
    adk web deep_search
"""

import datetime

from adk_fluent import Agent, Loop, Pipeline
from dotenv import load_dotenv
from google.adk.planners import BuiltInPlanner
from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool
from google.genai import types as genai_types

from .prompt import (
    EscalationChecker,
    Feedback,
    citation_replacement_callback,
    collect_research_sources_callback,
)

load_dotenv()

CRITIC_MODEL = "gemini-2.5-pro"
WORKER_MODEL = "gemini-2.5-pro"
MAX_ITERATIONS = 5
TODAY = datetime.datetime.now().strftime("%Y-%m-%d")

# --- Agent definitions ---

plan_generator = (
    Agent("plan_generator", WORKER_MODEL)
    .describe("Generates or refine the existing 5 line action-oriented research plan.")
    .instruct(f"""
    You are a research strategist. Your job is to create a high-level RESEARCH PLAN...
    Current date: {TODAY}
    """)  # Full prompt in prompt.py — abbreviated here for plan readability
    .tool(google_search)
)

section_planner = (
    Agent("section_planner", WORKER_MODEL)
    .describe("Breaks down the research plan into a structured markdown outline.")
    .instruct("You are an expert report architect...")  # Full prompt from prompt.py
    .outputs("report_sections")
)

section_researcher = (
    Agent("section_researcher", WORKER_MODEL)
    .describe("Performs the crucial first pass of web research.")
    .planner(BuiltInPlanner(
        thinking_config=genai_types.ThinkingConfig(include_thoughts=True)
    ))
    .instruct("You are a highly capable research and synthesis agent...")
    .tool(google_search)
    .outputs("section_research_findings")
    .after_agent(collect_research_sources_callback)
)

research_evaluator = (
    Agent("research_evaluator", CRITIC_MODEL)
    .describe("Critically evaluates research and generates follow-up queries.")
    .instruct(f"You are a meticulous quality assurance analyst... Current date: {TODAY}")
    .output_schema(Feedback)
    .disallow_transfer_to_parent(True)
    .disallow_transfer_to_peers(True)
    .outputs("research_evaluation")
)

enhanced_search = (
    Agent("enhanced_search_executor", WORKER_MODEL)
    .describe("Executes follow-up searches and integrates new findings.")
    .planner(BuiltInPlanner(
        thinking_config=genai_types.ThinkingConfig(include_thoughts=True)
    ))
    .instruct("You are a specialist researcher executing a refinement pass...")
    .tool(google_search)
    .outputs("section_research_findings")
    .after_agent(collect_research_sources_callback)
)

report_composer = (
    Agent("report_composer_with_citations", CRITIC_MODEL)
    .history("none")
    .describe("Transforms research data and a markdown outline into a final, cited report.")
    .instruct("Transform the provided data into a polished research report...")
    .outputs("final_cited_report")
    .after_agent(citation_replacement_callback)
)

# --- Composition ---

refinement_loop = (
    Loop("iterative_refinement_loop")
    .max_iterations(MAX_ITERATIONS)
    .step(research_evaluator)
    .step(EscalationChecker(name="escalation_checker"))
    .step(enhanced_search)
)

research_pipeline = (
    Pipeline("research_pipeline")
    .describe(
        "Executes a pre-approved research plan. It performs iterative research, "
        "evaluation, and composes a final, cited report."
    )
    .step(section_planner)
    .step(section_researcher)
    .step(refinement_loop)
    .step(report_composer)
)

root_agent = (
    Agent("interactive_planner_agent", WORKER_MODEL)
    .describe("The primary research assistant.")
    .instruct(f"""
    You are a research planning assistant...
    Current date: {TODAY}
    Do not perform any research yourself.
    """)
    .sub_agents([research_pipeline.build()])
    .tool(AgentTool(plan_generator.build()))
    .outputs("research_plan")
    .build()
)
```

**Step 3: Create comparison doc**

Create `docs/user-guide/adk-samples/deep-search.md`.

Key points to highlight:

- `Loop("name").step().step().step().max_iterations(5)` replaces `LoopAgent(name=..., max_iterations=5, sub_agents=[...])`
- `Pipeline("name").step().step().step().step()` replaces `SequentialAgent(name=..., sub_agents=[...])`
- `.output_schema(Feedback)` replaces `output_schema=Feedback`
- `.history("none")` replaces `include_contents="none"`
- `.after_agent(fn)` replaces `after_agent_callback=fn`
- Custom `EscalationChecker(BaseAgent)` works unchanged — fluent API accepts both builders and native agents
- All ADK fields accessible: `.planner()`, `.disallow_transfer_to_parent()`, `.disallow_transfer_to_peers()`

**Step 4: Commit**

```bash
git add examples/deep_search/ docs/user-guide/adk-samples/deep-search.md
git commit -m "feat: port Deep Search sample to fluent API with comparison docs"
```

______________________________________________________________________

### Task 6: Port Brand Search Optimization

**Files:**

- Create: `examples/brand_search/agent.py`
- Create: `examples/brand_search/prompt.py`
- Create: `examples/brand_search/tools.py`
- Create: `docs/user-guide/adk-samples/brand-search.md`

**Step 1: Create `examples/brand_search/prompt.py`**

Copy all prompts: `ROOT_PROMPT`, `KEYWORD_FINDING_AGENT_PROMPT`, `SEARCH_RESULT_AGENT_PROMPT`, `COMPARISON_AGENT_PROMPT`, `COMPARISON_CRITIC_AGENT_PROMPT`, `COMPARISON_ROOT_AGENT_PROMPT`.

**Step 2: Create `examples/brand_search/tools.py`**

Copy the BigQuery tool (`get_product_details_for_brand`) and all Selenium browser tools (`go_to_url`, `take_screenshot`, `find_element_with_text`, `click_element_with_text`, `enter_text_into_element`, `scroll_down_screen`, `get_page_source`, `analyze_webpage_and_determine_action`) verbatim. These are infrastructure tools.

**Step 3: Create `examples/brand_search/agent.py`**

```python
"""
Brand Search Optimization — Fluent API Port

Multi-agent system for e-commerce brand search optimization with keyword
finding, web browsing, and comparison analysis.
Original: https://github.com/google/adk-samples/tree/main/python/agents/brand-search-optimization

Usage:
    cd examples
    adk web brand_search
"""

from adk_fluent import Agent
from dotenv import load_dotenv
from google.adk.tools.load_artifacts_tool import load_artifacts_tool

from .prompt import (
    COMPARISON_AGENT_PROMPT,
    COMPARISON_CRITIC_AGENT_PROMPT,
    COMPARISON_ROOT_AGENT_PROMPT,
    KEYWORD_FINDING_AGENT_PROMPT,
    ROOT_PROMPT,
    SEARCH_RESULT_AGENT_PROMPT,
)
from .tools import (
    analyze_webpage_and_determine_action,
    click_element_with_text,
    enter_text_into_element,
    find_element_with_text,
    get_page_source,
    get_product_details_for_brand,
    go_to_url,
    scroll_down_screen,
    take_screenshot,
)

load_dotenv()

MODEL = "gemini-2.5-flash"

# --- Sub-agents ---

keyword_finding = (
    Agent("keyword_finding_agent", MODEL)
    .describe("A helpful agent to find keywords")
    .instruct(KEYWORD_FINDING_AGENT_PROMPT)
    .tool(get_product_details_for_brand)
)

search_results = (
    Agent("search_results_agent", MODEL)
    .describe("Get top 3 search results info for a keyword using web browsing")
    .instruct(SEARCH_RESULT_AGENT_PROMPT)
    .tool(go_to_url)
    .tool(take_screenshot)
    .tool(find_element_with_text)
    .tool(click_element_with_text)
    .tool(enter_text_into_element)
    .tool(scroll_down_screen)
    .tool(get_page_source)
    .tool(load_artifacts_tool)
    .tool(analyze_webpage_and_determine_action)
)

comparison_generator = (
    Agent("comparison_generator_agent", MODEL)
    .describe("A helpful agent to generate comparison.")
    .instruct(COMPARISON_AGENT_PROMPT)
)

comparison_critic = (
    Agent("comparison_critic_agent", MODEL)
    .describe("A helpful agent to critique comparison.")
    .instruct(COMPARISON_CRITIC_AGENT_PROMPT)
)

comparison_root = (
    Agent("comparison_root_agent", MODEL)
    .describe("A helpful agent to compare titles")
    .instruct(COMPARISON_ROOT_AGENT_PROMPT)
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

**Step 4: Create comparison doc and commit**

```bash
git add examples/brand_search/ docs/user-guide/adk-samples/brand-search.md
git commit -m "feat: port Brand Search Optimization sample to fluent API with comparison docs"
```

______________________________________________________________________

### Task 7: Port Travel Concierge

**Files:**

- Create: `examples/travel_concierge/agent.py`
- Create: `examples/travel_concierge/prompt.py`
- Create: `examples/travel_concierge/tools.py`
- Create: `docs/user-guide/adk-samples/travel-concierge.md`

This is the largest sample (20+ original files, 6 sub-agent groups). The fluent port consolidates everything into 3 files.

**Step 1: Create `examples/travel_concierge/prompt.py`**

Copy all prompts from the original's multiple prompt files into a single `prompt.py`. Constants include the root prompt, and prompts for all 6 sub-agent groups (inspiration, planning, booking, pre-trip, in-trip, post-trip) plus their nested sub-agents.

**Step 2: Create `examples/travel_concierge/tools.py`**

Copy the tool functions: `memorize`, `memorize_list`, `forget`, `map_tool`, and any other custom tools from the original. These remain unchanged.

**Step 3: Create `examples/travel_concierge/agent.py`**

The root agent delegates to 6 sub-agent groups, each of which uses `AgentTool` to wrap its own nested sub-agents. The fluent version uses `.delegate()` chains.

This file will be the largest (~100-120 LOC for agent definitions) but still dramatically smaller than the original's 20+ files.

**Step 4: Create comparison doc**

Create `docs/user-guide/adk-samples/travel-concierge.md`.

Key metrics:

- Native: 20+ Python files, 6 directories, multiple `__init__.py` re-exports
- Fluent: 3 files, flat directory
- The biggest win: eliminating the entire directory tree of `sub_agents/` with `__init__.py` re-exports

**Step 5: Commit**

```bash
git add examples/travel_concierge/ docs/user-guide/adk-samples/travel-concierge.md
git commit -m "feat: port Travel Concierge sample to fluent API with comparison docs"
```

______________________________________________________________________

### Task 8: Final integration and review

**Files:**

- Modify: `docs/user-guide/adk-samples/index.md` (update with actual metrics)
- Modify: `docs/user-guide/index.md` (add link to adk-samples section if needed)

**Step 1: Update index page with actual metrics**

After all ports are done, update the index page with real line counts and file counts from each port.

**Step 2: Verify all examples have correct `__init__.py`**

Each example must have `from . import agent` in `__init__.py` for `adk web` to work.

**Step 3: Final commit**

```bash
git add docs/user-guide/adk-samples/ examples/
git commit -m "docs: finalize ADK samples port index with metrics"
```
