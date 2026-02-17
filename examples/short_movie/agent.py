"""
Short Movie Agents — Campfire Story Creator

Ported from adk-samples/python/agents/short-movie to the fluent API.

A director agent orchestrates four sub-agents to guide the user through
creating a short animated campfire story: story generation, screenplay
writing, storyboard visualization (Imagen), and video generation (Veo).

Usage:
    cd examples
    adk web short_movie
"""

from adk_fluent import Agent
from dotenv import load_dotenv

from .prompt import (
    DIRECTOR_PROMPT,
    SCREENPLAY_PROMPT,
    STORYBOARD_PROMPT,
    STORY_DESC,
    STORY_PROMPT,
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
    .describe("Agent responsible for writing a screenplay based on a story.")
    .instruct(SCREENPLAY_PROMPT)
    .outputs("screenplay")
)

storyboard = (
    Agent("storyboard_agent", MODEL)
    .describe(
        "Agent responsible for creating storyboard images for each scene "
        "in the screenplay using Vertex AI Imagen."
    )
    .instruct(STORYBOARD_PROMPT)
    .outputs("storyboard")
    .tool(storyboard_generate)
)

video = (
    Agent("video_agent", MODEL)
    .describe(
        "Agent responsible for creating video clips for each scene "
        "using Veo 3.0 with storyboard images as reference."
    )
    .instruct(VIDEO_PROMPT)
    .outputs("video")
    .tool(video_generate)
)

# --- Director (root) ---

root_agent = (
    Agent("director_agent", MODEL)
    .describe(
        "Orchestrates the creation of a short, animated campfire story by "
        "coordinating story, screenplay, storyboard, and video sub-agents."
    )
    .instruct(DIRECTOR_PROMPT)
    .sub_agents([
        story.build(),
        screenplay.build(),
        storyboard.build(),
        video.build(),
    ])
    .build()
)
