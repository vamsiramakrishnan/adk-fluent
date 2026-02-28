"""StreamRunner: Continuous Userless Agent Execution

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
"""

# --- Source factories ---
from adk_fluent.source import Inbox, Source

# 1. from_iter: sync iterable → async stream
items = ["order_1", "order_2", "order_3"]
# Source.from_iter(items) returns an AsyncIterator[str]

# 2. callback / Inbox: push-based source
inbox = Source.callback()
assert isinstance(inbox, Inbox)
inbox.push("event_1")
inbox.push("event_2")
assert inbox.pending == 2
inbox.close()

# 3. Inbox with backpressure
bounded_inbox = Source.callback(maxsize=10)
assert isinstance(bounded_inbox, Inbox)

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
assert stats.processed == 0
assert stats.errors == 0
assert stats.in_flight == 0
assert stats.throughput == 0.0  # initially zero

# Session strategies
keyed_runner = (
    StreamRunner(processor)
    .source(Source.from_iter(["order_1"]))
    .session_key(lambda item: item.split("_")[0])  # session per prefix
)
assert keyed_runner._session_strategy == "keyed"

shared_runner = StreamRunner(processor).source(Source.from_iter(["order_1"])).session_strategy("shared")
assert shared_runner._session_strategy == "shared"

# --- Agent shortcut: .run_on() ---
# processor.run_on(source, concurrency=10) is a shortcut for
# StreamRunner(processor).source(source).concurrency(10).start()
# (Requires async context to actually run)

# --- ASSERT ---

# Source.callback() returns Inbox
inbox2 = Source.callback()
assert isinstance(inbox2, Inbox)

# Inbox push/close
inbox2.push("a")
inbox2.push("b")
assert inbox2.pending == 2
inbox2.close()

# StreamRunner is fluent
assert isinstance(runner, StreamRunner)
assert runner._concurrency == 5
assert runner._session_strategy == "per_item"
assert runner._shutdown_timeout == 10

# Session key implies keyed strategy
assert keyed_runner._session_strategy == "keyed"
assert keyed_runner._session_key_fn is not None

# Stats dataclass works
stats2 = StreamStats()
stats2.processed = 10
stats2.errors = 1
assert stats2.processed == 10
assert stats2.errors == 1
assert stats2.throughput > 0  # time has passed since creation

# StreamRunner requires source to start
import asyncio

try:
    asyncio.run(StreamRunner(processor).start())
    assert False, "Should have raised ValueError"
except ValueError as e:
    assert "No source configured" in str(e)
