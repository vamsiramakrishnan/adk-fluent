# LLM Auditor

A sequential pipeline that audits LLM-generated answers for factual accuracy using web search, then minimally revises the text to correct any errors.

## Architecture

critic_agent (verify claims via search) → reviser_agent (fix inaccuracies)

## Native ADK

The original uses 5 files across 3 directories:

```
llm_auditor/
├── __init__.py
├── agent.py
└── sub_agents/
    ├── critic/
    │   ├── __init__.py
    │   ├── agent.py
    │   └── prompt.py
    └── reviser/
        ├── __init__.py
        ├── agent.py
        └── prompt.py
```

<details><summary>llm_auditor/sub_agents/critic/prompt.py (click to expand)</summary>

```python
CRITIC_PROMPT = """\
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
```

</details>

<details><summary>llm_auditor/sub_agents/reviser/prompt.py (click to expand)</summary>

```python
REVISER_PROMPT = """\
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

Here are some examples of the task:

=== Example 1 ===

Question: Who was the first president of the US?

Answer: George Washington was the first president of the United States.

Findings:

  * Claim 1: George Washington was the first president of the United States.
      * Verdict: Accurate
      * Justification: Multiple reliable sources confirm that George Washington was the first president of the United States.
  * Overall verdict: Accurate
  * Overall justification: The answer is accurate and completely answers the question.

Your expected response:

George Washington was the first president of the United States.
---END-OF-EDIT---

=== Example 2 ===

Question: What is the shape of the sun?

Answer: The sun is cube-shaped and very hot.

Findings:

  * Claim 1: The sun is cube-shaped.
      * Verdict: Inaccurate
      * Justification: NASA states that the sun is a sphere of hot plasma, so it is not cube-shaped. It is a sphere.
  * Claim 2: The sun is very hot.
      * Verdict: Accurate
      * Justification: Based on my knowledge and the search results, the sun is extremely hot.
  * Overall verdict: Inaccurate
  * Overall justification: The answer states that the sun is cube-shaped, which is incorrect.

Your expected response:

The sun is sphere-shaped and very hot.
---END-OF-EDIT---

Here are the question-answer pair and the reviewer-provided findings:
"""
```

</details>

```python
# llm_auditor/agent.py
from google.adk.agents import SequentialAgent
from .sub_agents.critic import critic_agent
from .sub_agents.reviser import reviser_agent

llm_auditor = SequentialAgent(
    name="llm_auditor",
    description=(
        "Evaluates LLM-generated answers, verifies actual accuracy using the"
        " web, and refines the response to ensure alignment with real-world"
        " knowledge."
    ),
    sub_agents=[critic_agent, reviser_agent],
)
root_agent = llm_auditor
```

```python
# llm_auditor/sub_agents/critic/agent.py
from google.adk import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse
from google.adk.tools import google_search
from google.genai import types
from . import prompt

def _render_reference(callback_context, llm_response):
    del callback_context
    if (not llm_response.content or not llm_response.content.parts or not llm_response.grounding_metadata):
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
            all_text = "\n".join(part.text for part in llm_response.content.parts)
            llm_response.content.parts[0].text = all_text
            del llm_response.content.parts[1:]
    return llm_response

critic_agent = Agent(
    model="gemini-2.5-flash",
    name="critic_agent",
    instruction=prompt.CRITIC_PROMPT,
    tools=[google_search],
    after_model_callback=_render_reference,
)
```

```python
# llm_auditor/sub_agents/reviser/agent.py
from google.adk import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse
from . import prompt

_END_OF_EDIT_MARK = "---END-OF-EDIT---"

def _remove_end_of_edit_mark(callback_context, llm_response):
    del callback_context
    if not llm_response.content or not llm_response.content.parts:
        return llm_response
    for idx, part in enumerate(llm_response.content.parts):
        if _END_OF_EDIT_MARK in part.text:
            del llm_response.content.parts[idx + 1:]
            part.text = part.text.split(_END_OF_EDIT_MARK, 1)[0]
    return llm_response

reviser_agent = Agent(
    model="gemini-2.5-flash",
    name="reviser_agent",
    instruction=prompt.REVISER_PROMPT,
    after_model_callback=_remove_end_of_edit_mark,
)
```

## Fluent API

2 files, flat directory:

```python
# agent.py
from google.adk.tools import google_search
from google.genai import types

from adk_fluent import Agent
from dotenv import load_dotenv

from . import prompt

load_dotenv()


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


_END_OF_EDIT_MARK = "---END-OF-EDIT---"


def _remove_end_of_edit_mark(callback_context, llm_response):
    """Strip the ---END-OF-EDIT--- sentinel and everything after it."""
    del callback_context
    if not llm_response.content or not llm_response.content.parts:
        return llm_response
    for idx, part in enumerate(llm_response.content.parts):
        if _END_OF_EDIT_MARK in part.text:
            del llm_response.content.parts[idx + 1 :]
            part.text = part.text.split(_END_OF_EDIT_MARK, 1)[0]
    return llm_response


critic = (
    Agent("critic_agent")
    .model("gemini-2.5-flash")
    .instruct(prompt.CRITIC_PROMPT)
    .tool(google_search)
    .after_model(_render_reference)
)

reviser = (
    Agent("reviser_agent")
    .model("gemini-2.5-flash")
    .instruct(prompt.REVISER_PROMPT)
    .after_model(_remove_end_of_edit_mark)
)

llm_auditor = (critic >> reviser).name("llm_auditor").describe(
    "Evaluates LLM-generated answers, verifies actual accuracy using the"
    " web, and refines the response to ensure alignment with real-world"
    " knowledge."
)

root_agent = llm_auditor.build()
```

## What Changed

- `SequentialAgent(sub_agents=[critic, reviser])` → `critic >> reviser`
- `after_model_callback=fn` → `.after_model(fn)`
- `instruction=prompt.X` → `.instruct(X)`
- `tools=[google_search]` → `.tool(google_search)`
- 5 files across 3 directories → 2 files in 1 directory
- No `__init__.py` re-export chain

## Metrics

| Metric                            | Native | Fluent | Reduction |
| --------------------------------- | ------ | ------ | --------- |
| Agent definition files            | 3      | 1      | 67%       |
| Total files                       | 8      | 3      | 63%       |
| Directories                       | 4      | 1      | 75%       |
| `import` statements (agent files) | 11     | 5      | 55%       |
