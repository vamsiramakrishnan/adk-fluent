"""
Dispatch & Join: Fire-and-Continue Background Execution

Demonstrates the dispatch/join primitives for non-blocking background
agent execution.  Unlike FanOut (which blocks until all complete) or
race (which takes first and cancels rest), dispatch fires agents as
background tasks and lets the pipeline continue immediately.

Pipeline topology:
    writer
        >> dispatch(email_sender, seo_optimizer)   -- fire-and-continue
        >> formatter                                -- runs immediately
        >> join()                                   -- barrier: wait for all
        >> publisher

    Selective join:
        writer >> dispatch(email, seo) >> formatter >> join("seo") >> publisher >> join("email")

Key concepts:
  - dispatch(*agents): launches agents as asyncio.Tasks, pipeline continues
  - join(): barrier that waits for dispatched tasks to complete
  - join("name"): selective join -- wait for specific tasks only
  - .dispatch(name="x"): method form for any builder
  - Named tasks, callbacks, timeout, progress streaming

Converted from cookbook example: 59_dispatch_join.py

Usage:
    cd examples
    adk web dispatch_join
"""

from adk_fluent import Agent, Pipeline, dispatch, join
from adk_fluent._primitive_builders import BackgroundTask, _JoinBuilder
from adk_fluent._base import BuilderBase
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# Scenario: A content publishing pipeline that fires off email notification
# and SEO optimization in the background while the main pipeline continues
# with formatting and publishing.

writer = Agent("content_writer").model("gemini-2.5-flash").instruct("Write a blog post about the given topic.")
email_sender = (
    Agent("email_sender").model("gemini-2.5-flash").instruct("Send email notification about the new content.")
)
seo_optimizer = Agent("seo_optimizer").model("gemini-2.5-flash").instruct("Optimize the content for search engines.")
formatter = Agent("formatter").model("gemini-2.5-flash").instruct("Format the content for the website.")
publisher = Agent("publisher").model("gemini-2.5-flash").instruct("Publish the formatted content.")

# 1. Basic dispatch: fire-and-continue
basic_pipeline = (
    writer
    >> dispatch(email_sender, seo_optimizer)  # non-blocking background tasks
    >> formatter  # runs immediately, doesn't wait
    >> join()  # barrier: wait for all dispatched
    >> publisher
)

# 2. Named dispatch with selective join
named_pipeline = (
    writer
    >> dispatch(
        email_sender,
        seo_optimizer,
        names=["email", "seo"],
    )
    >> formatter
    >> join("seo", timeout=30)  # wait only for SEO before publishing
    >> publisher
    >> join("email")  # collect email result at the end
)

# 3. Method form: .dispatch() on any builder
bg_email = email_sender.dispatch(name="email")
bg_pipeline = (writer >> formatter).dispatch(name="content")
method_workflow = bg_email >> bg_pipeline >> publisher >> join()

# 4. Dispatch with callbacks
callback_results = []
callback_pipeline = (
    writer
    >> dispatch(
        email_sender,
        on_complete=lambda name, result: callback_results.append((name, "ok")),
        on_error=lambda name, exc: callback_results.append((name, "error")),
    )
    >> formatter
    >> join()
)

# 5. Dispatch with progress streaming
progress_pipeline = (
    writer
    >> dispatch(
        seo_optimizer,
        progress_key="seo_progress",  # partial results stream here as agent runs
    )
    >> formatter  # can read state["seo_progress"] for live updates
    >> join()
)

root_agent = progress_pipeline.build()
