# Dispatch & Join — Fire-and-Continue Background Execution

> **Modules in play:** `dispatch()` background tasks, `join()` barriers,
> `>>` sequential, named tasks, callbacks, progress streaming

## The Real-World Problem

Your content publishing pipeline writes a blog post, then needs to send an
email notification and optimize for SEO. But email and SEO don't depend on
each other, and neither blocks the main pipeline — the post should be
formatted and published *immediately* while email and SEO run in the background.
Only after publishing do you want to collect the SEO results to update metadata.

`FanOut` (`|`) won't work — it blocks until *all* branches complete. `race()`
won't work — it cancels the losers. You need **fire-and-continue**: launch
background tasks, keep going, and optionally wait later.

## The Fluent Solution

```python
from adk_fluent import Agent, Pipeline, dispatch, join

writer = Agent("content_writer", "gemini-2.5-flash").instruct("Write a blog post.")
email_sender = Agent("email_sender", "gemini-2.5-flash").instruct("Send email notification.")
seo_optimizer = Agent("seo_optimizer", "gemini-2.5-flash").instruct("Optimize for SEO.")
formatter = Agent("formatter", "gemini-2.5-flash").instruct("Format for the website.")
publisher = Agent("publisher", "gemini-2.5-flash").instruct("Publish the formatted content.")

# Pattern 1: Basic — fire background tasks, continue, then wait
basic_pipeline = (
    writer
    >> dispatch(email_sender, seo_optimizer)   # non-blocking
    >> formatter                                # runs immediately
    >> join()                                   # barrier: wait for all
    >> publisher
)

# Pattern 2: Named + selective join — wait for SEO before publishing,
# collect email results at the very end
named_pipeline = (
    writer
    >> dispatch(email_sender, seo_optimizer, names=["email", "seo"])
    >> formatter
    >> join("seo", timeout=30)     # wait only for SEO before publishing
    >> publisher
    >> join("email")               # collect email result at the end
)

# Pattern 3: Dispatch with callbacks
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

# Pattern 4: Progress streaming — partial results visible while running
progress_pipeline = (
    writer
    >> dispatch(seo_optimizer, progress_key="seo_progress")
    >> formatter    # can read state["seo_progress"] for live updates
    >> join()
)
```

## The Interplay Breakdown

**Why `dispatch()` instead of `|` (FanOut)?**
`|` creates a `ParallelAgent` that blocks until all branches complete. If
email takes 10 seconds and SEO takes 2 seconds, the pipeline waits 10
seconds before proceeding. `dispatch()` launches both as `asyncio.Task`s
and returns immediately — the formatter starts while email and SEO run
concurrently in the background.

**Why `join()` as a separate step?**
The barrier is explicit and positional. In `basic_pipeline`, `join()` appears
*after* the formatter — meaning formatting runs concurrently with background
tasks. Moving `join()` before the formatter would negate the benefit.

**Why named tasks + selective `join()`?**
Sometimes you need one background result before proceeding but can collect
another later. `join("seo")` waits only for the SEO optimizer (its result
might affect metadata), while `join("email")` at the end collects email
status for logging. This is impossible with `FanOut` — it's all-or-nothing.

**Why `progress_key`?**
Long-running background tasks can stream partial results via `progress_key`.
The main pipeline reads `state["seo_progress"]` for live updates without
waiting for completion. This is essential for user-facing progress bars
or dashboard updates.

**Why callbacks on dispatch?**
`on_complete` and `on_error` provide hooks for monitoring without blocking.
Log completion times, send alerts on failure, update metrics — all without
adding agents to the pipeline.

## Running on Different Backends

::::{tab-set}
:::{tab-item} ADK (default)
```python
response = basic_pipeline.ask("Write a blog post about AI safety")
```
:::
:::{tab-item} Temporal (in dev)
```python
from temporalio.client import Client
client = await Client.connect("localhost:7233")

# dispatch() → Temporal child workflow (fire-and-forget)
# join() → await child workflow handle
# Background tasks survive main pipeline crashes
durable = basic_pipeline.engine("temporal", client=client, task_queue="content")
response = await durable.ask_async("Write a blog post about AI safety")
```
:::
:::{tab-item} asyncio (in dev)
```python
response = await basic_pipeline.engine("asyncio").ask_async("Write a blog post")
```
:::
::::

## Pipeline Topology

```
writer ──► dispatch(email_sender, seo_optimizer)   [background]
           │
           ├──► formatter ──► join() ──► publisher  [main pipeline]
           │
           └──► email_sender ─┐
                seo_optimizer ─┘  [background tasks]
```
