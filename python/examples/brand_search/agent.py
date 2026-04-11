"""
Brand Search Optimization — Router with Nested Sub-agents

Ported from adk-samples: brand-search-optimization
Original uses a root router agent with 3 sub-agents, one of which
(comparison_root) itself contains 2 nested sub-agents (generator + critic).

Usage:
    cd examples
    adk web brand_search
"""

from adk_fluent import Agent
from dotenv import load_dotenv

from .prompt import (
    COMPARISON_CRITIC_PROMPT,
    COMPARISON_PROMPT,
    COMPARISON_ROOT_PROMPT,
    KEYWORD_FINDING_PROMPT,
    ROOT_PROMPT,
    SEARCH_RESULTS_PROMPT,
)
from .tools import (
    analyze_webpage,
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
    .sub_agents(
        [
            keyword_finding.build(),
            search_results.build(),
            comparison_root.build(),
        ]
    )
    .build()
)
