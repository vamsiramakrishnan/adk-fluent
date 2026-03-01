# StreamRunner: Continuous Userless Agent Execution

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

*How to register lifecycle callbacks with accumulation semantics.*

_Source: `60_stream_runner.py`_

## Equivalence

```python
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
```
