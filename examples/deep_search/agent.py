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
from google.genai import types as genai_types

from .prompt import (
    EscalationChecker,
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
    .output_schema(Feedback)
    .disallow_transfer_to_parent(True)
    .disallow_transfer_to_peers(True)
    .outputs("research_evaluation")
)

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

refinement_loop = (
    Loop("iterative_refinement_loop")
    .max_iterations(MAX_ITERATIONS)
    .step(research_evaluator)
    .step(EscalationChecker(name="escalation_checker"))
    .step(enhanced_search)
)

research_pipeline = (
    Pipeline("research_pipeline")
    .describe("Executes research with iterative refinement and composes cited report.")
    .step(section_planner)
    .step(section_researcher)
    .step(refinement_loop)
    .step(report_composer)
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
