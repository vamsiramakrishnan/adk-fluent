"""
StreamRunner: Continuous Userless Agent Execution

Demonstrates the Source and StreamRunner for processing continuous
data streams without a human in the loop.

Key concepts:
  - Source.from_iter(): wrap a sync iterable as an async stream
  - Source.from_async(): pass through an async generator
  - Source.poll(): poll a function at intervals
  - Source.callback() / Inbox: push-based source for webhooks
  - StreamRunner: bridges AsyncIterator → ADK runner.run_async()
  - Session strategies: per_item, shared, keyed
  - Callbacks: on_result, on_error (dead-letter queue)
  - StreamStats: live counters (processed, errors, throughput)

Converted from cookbook example: 60_stream_runner.py

Usage:
    cd examples
    adk web stream_runner
"""

# --- Source factories ---
from adk_fluent.source import Inbox, Source

# 1. from_iter: sync iterable → async stream
items = ["order_1", "order_2", "order_3"]
# Source.from_iter(items) returns an AsyncIterator[str]

# 2. callback / Inbox: push-based source
inbox = Source.callback()
inbox.push("event_1")
inbox.push("event_2")
inbox.close()

# 3. Inbox with backpressure
bounded_inbox = Source.callback(maxsize=10)

# --- StreamRunner configuration ---
from adk_fluent import Agent
from adk_fluent.stream import StreamRunner, StreamStats

processor = Agent("order_processor").model("gemini-2.5-flash").instruct("Process the incoming order event.")

# Full fluent configuration
results = []
errors = []
runner = (
    StreamRunner(processor)
    .source(Source.from_iter(["order_1", "order_2"]))
    .concurrency(5)
    .session_strategy("per_item")
    .on_result(lambda item, result: results.append((item, result)))
    .on_error(lambda item, exc: errors.append((item, str(exc))))
    .graceful_shutdown(timeout=10)
)

# StreamStats is a simple dataclass
stats = StreamStats()

# Session strategies
keyed_runner = (
    StreamRunner(processor)
    .source(Source.from_iter(["order_1"]))
    .session_key(lambda item: item.split("_")[0])  # session per prefix
)

shared_runner = StreamRunner(processor).source(Source.from_iter(["order_1"])).session_strategy("shared")

# --- Agent shortcut: .run_on() ---
# processor.run_on(source, concurrency=10) is a shortcut for
# StreamRunner(processor).source(source).concurrency(10).start()
# (Requires async context to actually run)

# --- ASSERT ---

# Source.callback() returns Inbox
inbox2 = Source.callback()

# Inbox push/close
inbox2.push("a")
inbox2.push("b")
inbox2.close()

# StreamRunner is fluent

# Session key implies keyed strategy

# Stats dataclass works
stats2 = StreamStats()
stats2.processed = 10
stats2.errors = 1

# StreamRunner requires source to start
import asyncio
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

try:
    asyncio.run(StreamRunner(processor).start())
except ValueError as e:

root_agent = stats2.build()
