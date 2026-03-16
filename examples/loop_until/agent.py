"""
Resume Refinement Loop with Conditional Exit

Pipeline topology:
    ( resume_writer >> resume_reviewer ) * until(quality_score == "excellent")

Converted from cookbook example: 20_loop_until.py

Usage:
    cd examples
    adk web loop_until
"""

from adk_fluent import Agent, Loop
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# loop_until: refine a resume draft until the quality reviewer approves it
resume_writer = (
    Agent("resume_writer")
    .model("gemini-2.5-flash")
    .instruct(
        "Write or improve a professional resume based on the candidate's "
        "experience. Incorporate feedback from previous reviews."
    )
    .writes("quality_score")
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
        .writes("tone_approved")
    )
    .until(lambda s: s.get("tone_approved") == "yes")
    .max_iterations(10)
)

root_agent = cover_letter_loop.build()
