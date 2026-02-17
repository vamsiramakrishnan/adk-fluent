"""
LLM Auditor — Sequential Pipeline with Callbacks

Ported from adk-samples: llm_auditor
Original uses SequentialAgent with critic + reviser sub-agents.

Usage:
    cd examples
    adk web llm_auditor
"""

from adk_fluent import Agent
from dotenv import load_dotenv
from google.adk.tools import google_search
from google.genai import types

from .prompt import CRITIC_PROMPT, END_OF_EDIT_MARK, REVISER_PROMPT

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)


# --- Callbacks ---

def _render_reference(callback_context, llm_response):
    """Append grounding references from search results to the model output."""
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


def _remove_end_of_edit_mark(callback_context, llm_response):
    """Strip the ---END-OF-EDIT--- sentinel and everything after it."""
    del callback_context
    if not llm_response.content or not llm_response.content.parts:
        return llm_response
    for idx, part in enumerate(llm_response.content.parts):
        if END_OF_EDIT_MARK in part.text:
            del llm_response.content.parts[idx + 1 :]
            part.text = part.text.split(END_OF_EDIT_MARK, 1)[0]
    return llm_response


# --- Agents ---

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

# >> creates a SequentialAgent — identical to
# SequentialAgent(name=..., sub_agents=[critic_agent, reviser_agent])
root_agent = (critic >> reviser).name("llm_auditor").describe(
    "Evaluates LLM-generated answers, verifies actual accuracy using the"
    " web, and refines the response to ensure alignment with real-world"
    " knowledge."
).build()
