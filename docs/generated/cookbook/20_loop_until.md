# Resume Refinement Loop with Conditional Exit

*How to create looping agent workflows.*

_Source: `20_loop_until.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
# Native ADK has no built-in conditional loop exit. You'd need to:
#   1. Create a custom BaseAgent that evaluates a predicate
#   2. Yield Event(actions=EventActions(escalate=True)) to exit
#   3. Manually wire it into the LoopAgent's sub_agents
# This is ~30 lines of boilerplate per loop condition.
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, Loop

# loop_until: refine a resume draft until the quality reviewer approves it
resume_writer = (
    Agent("resume_writer")
    .model("gemini-2.5-flash")
    .instruct(
        "Write or improve a professional resume based on the candidate's "
        "experience. Incorporate feedback from previous reviews."
    )
    .outputs("quality_score")
)
resume_reviewer = (
    Agent("resume_reviewer")
    .model("gemini-2.5-flash")
    .instruct(
        "Review the resume for clarity, impact, and ATS compatibility. Set quality_score to 'excellent' when satisfied."
    )
)

refinement = (resume_writer >> resume_reviewer).loop_until(
    lambda s: s.get("quality_score") == "excellent", max_iterations=5
)

# .until() on a Loop -- alternative syntax for complex multi-step loops
cover_letter_loop = (
    Loop("cover_letter_polish")
    .step(
        Agent("drafter")
        .model("gemini-2.5-flash")
        .instruct("Draft or revise a cover letter tailored to the job description.")
    )
    .step(
        Agent("tone_checker")
        .model("gemini-2.5-flash")
        .instruct("Check the cover letter tone. Set 'tone_approved' to 'yes' when professional.")
        .outputs("tone_approved")
    )
    .until(lambda s: s.get("tone_approved") == "yes")
    .max_iterations(10)
)
```
:::
::::

## Equivalence

```python
from adk_fluent.workflow import Loop as LoopBuilder

# loop_until creates a Loop builder
assert isinstance(refinement, LoopBuilder)

# The loop has _until_predicate stored for checkpoint injection at build time
assert refinement._config.get("_until_predicate") is not None
assert refinement._config.get("max_iterations") == 5

# .until() on Loop sets the predicate
assert cover_letter_loop._config.get("_until_predicate") is not None
assert cover_letter_loop._config.get("max_iterations") == 10

# Build verifies the checkpoint agent is injected
built = refinement.build()
# Last sub_agent should be the checkpoint that checks quality_score
checkpoint = built.sub_agents[-1]
assert checkpoint.name == "_until_check"
```

:::{seealso}
API reference: [Loop](../api/workflow.md#builder-Loop)
:::
