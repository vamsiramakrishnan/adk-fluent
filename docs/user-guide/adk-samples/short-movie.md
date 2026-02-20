# Short Movie Agents

A director agent orchestrates four specialized sub-agents to guide the user through creating a short, animated campfire story: story generation, screenplay writing, storyboard visualization (Vertex AI Imagen), and video generation (Veo 3.0).

## Architecture

```
director_agent (root)
  +-- story_agent        (generates campfire stories)
  +-- screenplay_agent   (converts story to screenplay format)
  +-- storyboard_agent   (generates images via Imagen)
  +-- video_agent        (generates video clips via Veo)
```

The director guides the user step-by-step, delegating to each sub-agent in sequence and seeking user approval before proceeding to the next stage.

## Native ADK

The original uses 8+ files across multiple directories, with prompts stored as separate `.txt` files loaded at runtime:

```
short-movie/
├── __init__.py
├── agent.py                  # director / root agent
├── story_agent.py
├── screenplay_agent.py
├── storyboard_agent.py
├── video_agent.py
└── utils/
    ├── __init__.py
    ├── utils.py              # load_prompt_from_file()
    └── prompts/
        ├── director_agent.txt
        ├── story_agent.txt
        ├── story_agent_desc.txt
        ├── screenplay_agent.txt
        ├── storyboard_agent.txt
        └── video_agent.txt
```

<details><summary>agent.py — director / root agent (click to expand)</summary>

```python
from google.adk.agents import Agent
from .screenplay_agent import screenplay_agent
from .story_agent import story_agent
from .storyboard_agent import storyboard_agent
from .video_agent import video_agent
from .utils.utils import load_prompt_from_file

MODEL = "gemini-2.5-flash"

root_agent = Agent(
    name="director_agent",
    model=MODEL,
    description="Orchestrates the creation of a short, animated campfire story...",
    instruction=load_prompt_from_file("director_agent.txt"),
    sub_agents=[story_agent, screenplay_agent, storyboard_agent, video_agent],
)
```

</details>

<details><summary>story_agent.py (click to expand)</summary>

```python
from google.adk.agents import Agent
from .utils.utils import load_prompt_from_file

MODEL = "gemini-2.5-flash"

story_agent = Agent(
    model=MODEL,
    name="story_agent",
    description=load_prompt_from_file("story_agent_desc.txt"),
    instruction=load_prompt_from_file("story_agent.txt"),
    output_key="story",
)
```

</details>

<details><summary>screenplay_agent.py (click to expand)</summary>

```python
from google.adk.agents import Agent
from .utils.utils import load_prompt_from_file

MODEL = "gemini-2.5-flash"

screenplay_agent = Agent(
    model=MODEL,
    name="screenplay_agent",
    description="Agent responsible for writing a screenplay based on a story",
    instruction=load_prompt_from_file("screenplay_agent.txt"),
    output_key="screenplay",
)
```

</details>

<details><summary>storyboard_agent.py — with Imagen tool (click to expand)</summary>

```python
from google.adk.agents import Agent
from .utils.utils import load_prompt_from_file

MODEL = "gemini-2.5-flash"

def storyboard_generate(prompt, scene_number, tool_context):
    """Generate storyboard image via Vertex AI Imagen 4.0 Ultra."""
    # ... Vertex AI Imagen API call ...

storyboard_agent = Agent(
    model=MODEL,
    name="storyboard_agent",
    description="Agent responsible for creating storyboards...",
    instruction=load_prompt_from_file("storyboard_agent.txt"),
    output_key="storyboard",
    tools=[storyboard_generate],
)
```

</details>

<details><summary>video_agent.py — with Veo tool (click to expand)</summary>

```python
from google.adk.agents import Agent
from .utils.utils import load_prompt_from_file

MODEL = "gemini-2.5-flash"

def video_generate(prompt, scene_number, image_link, screenplay, tool_context):
    """Generate video clip via Veo 3.0."""
    # ... Google GenAI Veo API call ...

video_agent = Agent(
    model=MODEL,
    name="video_agent",
    description="Agent responsible for creating videos...",
    instruction=load_prompt_from_file("video_agent.txt"),
    output_key="video",
    tools=[video_generate],
)
```

</details>

## Fluent API

3 files, flat directory:

```
short_movie/
├── __init__.py
├── agent.py
├── prompt.py
└── tools.py
```

```python
# prompt.py — all prompts as Python constants
DIRECTOR_PROMPT = """\
**Role:** Director Agent
...
"""

STORY_DESC = "Agent responsible for generating engaging campfire stories..."

STORY_PROMPT = """\
**Name:** Scout Leader
...
"""

SCREENPLAY_PROMPT = """\
**Role:** Screenplay Writer
...
"""

STORYBOARD_PROMPT = """\
**Role:** Storyboard Artist
...
"""

VIDEO_PROMPT = """\
**Role:** Video Director
...
"""
```

```python
# tools.py — stub tool functions (require Vertex AI credentials in production)
import logging

logger = logging.getLogger(__name__)

def storyboard_generate(prompt: str, scene_number: int) -> list[str]:
    """Generate a storyboard image for a scene using Vertex AI Imagen."""
    logger.info(f"Generating storyboard for scene {scene_number}: {prompt[:80]}...")
    return [f"https://storage.example.com/scene_{scene_number}_storyboard.png"]

def video_generate(prompt: str, scene_number: int, image_link: str, screenplay: str) -> list[str]:
    """Generate a video clip for a scene using Veo 3.0."""
    logger.info(f"Generating video for scene {scene_number}: {prompt[:80]}...")
    return [f"https://storage.example.com/scene_{scene_number}_video.mp4"]
```

```python
# agent.py
from adk_fluent import Agent
from dotenv import load_dotenv

from .prompt import (
    DIRECTOR_PROMPT, SCREENPLAY_PROMPT, STORYBOARD_PROMPT,
    STORY_DESC, STORY_PROMPT, VIDEO_PROMPT,
)
from .tools import storyboard_generate, video_generate

load_dotenv()

MODEL = "gemini-2.5-flash"

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
    .describe("Agent responsible for creating storyboard images for each scene "
              "in the screenplay using Vertex AI Imagen.")
    .instruct(STORYBOARD_PROMPT)
    .outputs("storyboard")
    .tool(storyboard_generate)
)

video = (
    Agent("video_agent", MODEL)
    .describe("Agent responsible for creating video clips for each scene "
              "using Veo 3.0 with storyboard images as reference.")
    .instruct(VIDEO_PROMPT)
    .outputs("video")
    .tool(video_generate)
)

root_agent = (
    Agent("director_agent", MODEL)
    .describe("Orchestrates the creation of a short, animated campfire story by "
              "coordinating story, screenplay, storyboard, and video sub-agents.")
    .instruct(DIRECTOR_PROMPT)
    .sub_agents([
        story.build(), screenplay.build(),
        storyboard.build(), video.build(),
    ])
    .build()
)
```

## What Changed

- 5 separate agent files collapsed into a single `agent.py` with inline builder chains
- 6 `.txt` prompt files replaced by Python constants in `prompt.py`
- `load_prompt_from_file()` utility eliminated entirely
- `utils/` directory removed
- `Agent(name=..., model=..., instruction=..., output_key=...)` replaced by `Agent("name", MODEL).instruct(...).outputs(...)`
- `tools=[fn]` replaced by `.tool(fn)` with append semantics
- `sub_agents=[...]` parameter replaced by `.sub_agents([...])` method
- `ToolContext` parameter simplified in stub tool signatures

## Metrics

| Metric                            | Native   | Fluent  | Reduction |
| --------------------------------- | -------- | ------- | --------- |
| Agent definition files            | 5        | 1       | 80%       |
| Prompt files                      | 6 (.txt) | 1 (.py) | 83%       |
| Total files                       | 14       | 4       | 71%       |
| Directories                       | 4        | 1       | 75%       |
| `import` statements (agent files) | 12       | 4       | 67%       |
