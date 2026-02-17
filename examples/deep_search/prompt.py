"""Prompts, Pydantic models, callbacks, and custom BaseAgent for the Deep Search pipeline.

Contains all domain logic that is shared between the native ADK and fluent API
versions of the Deep Search multi-agent research system.
"""

import re
from collections.abc import AsyncGenerator
from typing import Literal

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types as genai_types
from pydantic import BaseModel, Field


# =====================================================================
# Pydantic Models
# =====================================================================

class SearchQuery(BaseModel):
    """A single follow-up web search query."""

    search_query: str = Field(description="A specific search query for web search.")


class Feedback(BaseModel):
    """Structured evaluation of research quality."""

    grade: Literal["pass", "fail"] = Field(
        description="Whether the research meets the quality bar: 'pass' or 'fail'."
    )
    comment: str = Field(
        description="Detailed evaluation explaining the reasoning behind the grade."
    )
    follow_up_queries: list[SearchQuery] | None = Field(
        default=None,
        description=(
            "If the grade is 'fail', a list of follow-up search queries to fill "
            "the identified gaps. Omit or set to null if grade is 'pass'."
        ),
    )


# =====================================================================
# Prompts
# =====================================================================

PLAN_GENERATOR_PROMPT = """\
You are a **Research Strategist**. Today's date is {today}.

Given a user's research topic, produce a structured research plan. The plan
must contain exactly **5 numbered action items**, each tagged as either
`[RESEARCH]` or `[DELIVERABLE]`.

## Rules

1. **[RESEARCH]** items describe a specific web search or investigation step.
   Each must state *what* to search for and *why* that information matters.
2. **[DELIVERABLE]** items describe a concrete output artifact (e.g., a
   comparison table, an executive summary, a timeline). There must be at
   least one deliverable.
3. Order the items logically: foundational research first, synthesis later.
4. Be specific — vague items like "research the topic" are not acceptable.
5. Prefer primary and authoritative sources (academic papers, official docs,
   reputable news outlets) over opinion pieces.
6. If the topic is time-sensitive, include a step to verify recency of data.

## Output format

```
1. [RESEARCH] ...
2. [RESEARCH] ...
3. [RESEARCH] ...
4. [DELIVERABLE] ...
5. [RESEARCH] ...
```

Use the Google Search tool to validate that your proposed queries return
useful results. Revise any query that yields poor results before finalising
the plan.
"""

SECTION_PLANNER_PROMPT = """\
You are a **Report Architect**. Your job is to turn a research plan into a
structured report outline.

## Input

You will receive a research plan with numbered action items.

## Task

Produce a Markdown outline with **4 to 6 top-level sections**. Each section
should have:

- A descriptive heading (## level)
- 2-4 bullet points describing the key questions or sub-topics that section
  must cover
- A note indicating which research-plan items feed into this section

## Guidelines

1. Start with an **Executive Summary** section and end with a **Conclusions
   & Recommendations** section.
2. Group related research items into the same section where it makes sense.
3. Ensure the outline tells a coherent narrative — each section should flow
   logically into the next.
4. Keep headings concise but descriptive.

## Output

Return ONLY the Markdown outline. No preamble, no commentary.
"""

SECTION_RESEARCHER_PROMPT = """\
You are a **Research Agent** specialising in thorough, fact-based web research.

## Input

You will receive:
- The overall research plan
- A report outline with section descriptions

## Task — Two Phases

### Phase 1: Information Gathering
For each section in the outline:
1. Formulate 2-3 targeted search queries.
2. Execute each query using the Google Search tool.
3. Extract key facts, statistics, quotes, and data points from the results.
4. Note the source URL and title for every piece of evidence.

### Phase 2: Synthesis
After gathering information for all sections, produce a structured research
findings document:
- Organise findings by report section.
- For each section, present the evidence in bullet-point form.
- Flag any conflicting information across sources.
- Identify gaps where insufficient evidence was found.

## Quality standards

- Prefer quantitative data over qualitative claims.
- Cross-reference important facts across at least two sources.
- Clearly distinguish facts from interpretations.
- Include direct quotes when they add value.

## Output

Return the synthesised research findings document. Do NOT write the final
report — that is another agent's job.
"""

RESEARCH_EVALUATOR_PROMPT = """\
You are a **Research Quality Analyst**. Today's date is {today}.

## Input

You will receive:
- The original research plan
- The report outline (sections)
- The current research findings

## Task

Critically evaluate the research findings against the plan and outline:

1. **Coverage**: Does the research address every section in the outline?
   Are there gaps or missing sub-topics?
2. **Depth**: Are claims supported by specific data, statistics, or
   authoritative quotes? Flag any unsupported assertions.
3. **Recency**: Is the information current as of today? Flag any data that
   appears outdated (more than 12 months old for fast-moving topics).
4. **Balance**: Does the research present multiple perspectives on
   controversial or nuanced topics?
5. **Source quality**: Are the sources credible and authoritative?

## Output

You MUST respond with structured JSON matching the Feedback schema:
- `grade`: "pass" if the research is ready for report composition, "fail"
  if it needs improvement.
- `comment`: A detailed explanation of your evaluation (200-400 words).
- `follow_up_queries`: If grade is "fail", provide 2-5 specific follow-up
  search queries that would address the identified gaps. Set to null if
  grade is "pass".

A "pass" grade requires: all sections covered, key claims supported by data,
sources are credible, and no critical gaps remain.
"""

ENHANCED_SEARCH_PROMPT = """\
You are a **Specialist Researcher** tasked with filling gaps identified by
the quality evaluator.

## Input

You will receive:
- The current research findings
- A quality evaluation with a "fail" grade
- A list of follow-up search queries

## Task

1. Execute EVERY follow-up query provided in the evaluation using the
   Google Search tool.
2. For each query, extract the most relevant and authoritative information.
3. Synthesise the new findings and MERGE them with the existing research.
4. Clearly mark which sections of the report each new finding supports.

## Guidelines

- Do not duplicate information already present in the existing findings.
- Focus on filling the specific gaps identified in the evaluation.
- If a follow-up query yields no useful results, try reformulating it
  with alternative keywords before giving up.
- Prioritise primary sources and recent data.

## Output

Return the COMPLETE updated research findings (existing + new), organised
by report section. The output replaces the previous findings entirely.
"""

REPORT_COMPOSER_PROMPT = """\
You are a **Report Composer** specialising in well-structured, citation-rich
research reports.

## Input

You will receive:
- The research plan
- The report outline
- The final research findings
- A sources dictionary (available in session state as `sources`) mapping
  short IDs like "src-1", "src-2" to source metadata

## Task

Compose the final research report following the outline structure.

## Citation rules

- Every factual claim MUST include an inline citation using the XML tag
  format: `<cite source="src-N"/>` where N matches the short ID from the
  sources dictionary.
- Place citations immediately after the claim they support.
- A single sentence may have multiple citations if it synthesises multiple
  sources.
- Do NOT invent source IDs — only use IDs present in the sources dictionary.

## Formatting

- Use Markdown formatting throughout.
- Each section should be 200-400 words.
- Include an Executive Summary at the top (150-250 words).
- Use bullet points, tables, and sub-headings where they improve clarity.
- End with a Conclusions section that synthesises key takeaways.

## Quality

- Write in a professional, objective tone.
- Avoid hedging language ("it seems", "perhaps") unless genuinely uncertain.
- Ensure smooth transitions between sections.
- Do NOT include a bibliography — citations are inline only.

## Output

Return ONLY the Markdown report. No preamble, no meta-commentary.
"""

INTERACTIVE_PLANNER_PROMPT = """\
You are the **Deep Search Planning Assistant**. Today's date is {today}.

Your role is to help users conduct thorough research on any topic by
creating, refining, and executing structured research plans.

## Workflow

1. **Understand the request**: Ask clarifying questions if the user's topic
   is too broad or ambiguous. You need enough specificity to create a
   targeted research plan.

2. **Generate a plan**: Use the `plan_generator` tool to create a 5-point
   research plan. Present it to the user for approval.

3. **Refine if needed**: If the user wants changes, use `plan_generator`
   again with their feedback incorporated.

4. **Execute**: Once the user approves the plan, delegate execution to the
   `research_pipeline` sub-agent. This will:
   - Break the plan into report sections
   - Research each section via web search
   - Iteratively evaluate and improve the research quality
   - Compose a cited final report

5. **Deliver**: Present the final report to the user. Offer to refine
   specific sections or conduct follow-up research if requested.

## Guidelines

- Be conversational and helpful, but efficient.
- Store the approved plan in the `research_plan` output key.
- If the user provides a very specific question (not a broad topic),
  skip the planning phase and go directly to the research pipeline.
- Always confirm the plan before executing — research takes time.
"""


# =====================================================================
# Callbacks
# =====================================================================

def collect_research_sources_callback(callback_context):
    """Extract grounding metadata from session events into structured state.

    Walks all session events, pulling grounding_chunks (URLs / titles) and
    grounding_supports (claim-to-source mappings with confidence scores)
    into two state dictionaries:

    - ``url_to_short_id``: maps canonical URL -> "src-N"
    - ``sources``: maps "src-N" -> {title, url, domain, supported_claims}
    """
    session = callback_context._invocation_context.session
    url_to_short_id = callback_context.state.get("url_to_short_id", {})
    sources = callback_context.state.get("sources", {})
    id_counter = len(url_to_short_id) + 1

    for event in session.events:
        if not (event.grounding_metadata and event.grounding_metadata.grounding_chunks):
            continue

        chunks_info: dict[int, str] = {}
        for idx, chunk in enumerate(event.grounding_metadata.grounding_chunks):
            if not chunk.web:
                continue
            url = chunk.web.uri
            title = (
                chunk.web.title
                if chunk.web.title != chunk.web.domain
                else chunk.web.domain
            )
            if url not in url_to_short_id:
                short_id = f"src-{id_counter}"
                url_to_short_id[url] = short_id
                sources[short_id] = {
                    "short_id": short_id,
                    "title": title,
                    "url": url,
                    "domain": chunk.web.domain,
                    "supported_claims": [],
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
                        confidence = (
                            confidence_scores[i]
                            if i < len(confidence_scores)
                            else 0.5
                        )
                        text_segment = (
                            support.segment.text if support.segment else ""
                        )
                        sources[short_id]["supported_claims"].append(
                            {
                                "text_segment": text_segment,
                                "confidence": confidence,
                            }
                        )

    callback_context.state["url_to_short_id"] = url_to_short_id
    callback_context.state["sources"] = sources


def citation_replacement_callback(callback_context):
    """Replace ``<cite source="src-N"/>`` tags with Markdown links.

    Reads the final cited report from state, resolves each citation tag
    against the sources dictionary, and writes the processed report to
    ``final_report_with_citations``.
    """
    final_report = callback_context.state.get("final_cited_report", "")
    sources = callback_context.state.get("sources", {})

    def tag_replacer(match):
        short_id = match.group(1)
        source_info = sources.get(short_id)
        if not source_info:
            return ""
        display_text = source_info.get(
            "title", source_info.get("domain", short_id)
        )
        return f" [{display_text}]({source_info['url']})"

    processed_report = re.sub(
        r'<cite\s+source\s*=\s*["\']?\s*(src-\d+)\s*["\']?\s*/>',
        tag_replacer,
        final_report,
    )
    # Clean up whitespace before punctuation introduced by citation insertion
    processed_report = re.sub(r"\s+([.,;:])", r"\1", processed_report)

    callback_context.state["final_report_with_citations"] = processed_report
    return genai_types.Content(parts=[genai_types.Part(text=processed_report)])


# =====================================================================
# Custom BaseAgent: EscalationChecker
# =====================================================================

class EscalationChecker(BaseAgent):
    """Check if the research evaluation grade is 'pass' and escalate to exit the loop.

    Sits inside the iterative refinement LoopAgent. When the evaluator
    grades the research as "pass", this agent emits an escalation event
    that causes the LoopAgent to terminate early.
    """

    def __init__(self, name: str):
        super().__init__(name=name)

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        evaluation_result = ctx.session.state.get("research_evaluation")
        if evaluation_result and evaluation_result.get("grade") == "pass":
            yield Event(
                author=self.name,
                actions=EventActions(escalate=True),
            )
        else:
            yield Event(author=self.name)
