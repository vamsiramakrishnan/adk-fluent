# Compression

The `adk_fluent._compression` package is adk-fluent's **message-level
compression** mechanism. It complements `C.*` transforms and the
`_budget` package:

- `C.*` shapes the context that the LLM sees **on a single turn**.
- `_budget` tracks cumulative usage and fires threshold callbacks **at
  the session level**.
- `_compression` rewrites the persistent message history **when it
  exceeds a threshold**.

The split matters: compression destroys information, so you want a
clear trigger (budget threshold, token count) and a clear *veto* point
(the `pre_compact` hook) before the rewrite runs.

## The two pieces

### `CompressionStrategy`

A frozen description of *how* to compress. Three constructors:

```python
CompressionStrategy.keep_recent(n=10)          # keep last N turn-pairs
CompressionStrategy.drop_old(keep_turns=5)     # drop oldest, keep last
CompressionStrategy.summarize(model="gemini-2.5-flash")
```

System messages (`role == "system"`) are always preserved. The
`summarize` method is a contract: the compressor passes older messages
to a summariser callable and replaces them with a single summary
message.

### `ContextCompressor`

```python
ContextCompressor(
    threshold: int = 100_000,
    strategy: CompressionStrategy | None = None,
    on_compress: Callable[[int], None] | None = None,
    *,
    hook_registry: HookRegistry | None = None,
)
```

Two entry points:

- `compress_messages(messages)` — sync. For `summarize` it falls back to
  `keep_recent` because LLM summarisation is async.
- `compress_messages_async(messages, summarizer=...)` — async. Use this
  when you want real summaries.

Both honour the `pre_compact` hook.

## Quick start

```python
from adk_fluent import ContextCompressor, CompressionStrategy

compressor = ContextCompressor(
    threshold=100_000,
    strategy=CompressionStrategy.keep_recent(n=10),
    on_compress=lambda tokens: print(f"compressed at {tokens} tokens"),
)

if compressor.should_compress(current_tokens=120_000):
    messages = compressor.compress_messages(messages)
```

## `pre_compact` hook integration

Wire a `HookRegistry` to get fine-grained control over every
compression pass. This mirrors the Claude Agent SDK's `PreCompact` hook:

```python
from adk_fluent import ContextCompressor, H
from adk_fluent._hooks import HookDecision, HookEvent

def audit(ctx):
    print(f"about to compress {ctx.extra['token_count']} tokens")
    return HookDecision.allow()

registry = H.hooks().on(HookEvent.PRE_COMPACT, audit)
compressor = ContextCompressor(threshold=100_000).with_hooks(registry)
```

The hook can return any of:

| Decision | Effect |
| --- | --- |
| `HookDecision.allow()` | Compression proceeds with the configured strategy. |
| `HookDecision.deny(reason=...)` | Compression is cancelled; the original messages are returned unchanged. |
| `HookDecision.replace(output=...)` | Hook supplies the compressed message list directly. The configured strategy is **not** run. |
| `HookDecision.modify(...)` | Currently supported via `ctx.extra["messages"]` — the strategy runs on the rewritten input. |

The `HookContext` receives:

- `event` — `HookEvent.PRE_COMPACT`
- `extra.messages` — a shallow copy of the message list
- `extra.token_count` — the pre-compression token estimate
- `extra.strategy` — the strategy method name

### Use cases for `pre_compact`

- **Audit logging** — write the pre-compression transcript to disk
  before it's destroyed.
- **Veto on sensitive content** — refuse to compress messages that
  contain unresolved tool calls or pending user input.
- **Custom compression** — replace the built-in strategies entirely
  with a project-specific summariser.
- **Slack/PagerDuty notification** — alert the operator before the
  agent self-compresses in a production session.

## Bridge to `BudgetMonitor`

`ContextCompressor.to_monitor()` returns a `BudgetMonitor` wired to
fire `on_compress` at 95% of the compressor's threshold. Use this when
you want a single call to tie token tracking and compression together:

```python
compressor = ContextCompressor(threshold=150_000)
compressor.on_compress = lambda tokens: run_compression()

monitor = compressor.to_monitor()
agent = Agent("coder").after_model(monitor.after_model_hook())
```

## Testing

Both the compressor and hook integration are plain Python, so tests
don't need a live model. Use `HookRegistry` directly and assert on the
output:

```python
from adk_fluent import ContextCompressor, CompressionStrategy
from adk_fluent._hooks import HookDecision
from adk_fluent._hooks._events import HookEvent
from adk_fluent._hooks._registry import HookRegistry

registry = HookRegistry()
registry.on(HookEvent.PRE_COMPACT, lambda ctx: HookDecision.deny("nope"))

compressor = ContextCompressor(
    threshold=10,
    strategy=CompressionStrategy.keep_recent(1),
    hook_registry=registry,
)

msgs = [{"role": "user", "content": f"msg-{i}"} for i in range(20)]
out = compressor.compress_messages(msgs)
assert out == msgs  # hook vetoed
assert compressor.compression_count == 0
```

## Design notes

- The compressor is **sync-first**. Message rewriting is CPU-bound and
  should not require an event loop. The async variant exists only for
  LLM-backed summarisation.
- `CompressionStrategy` is frozen — you can hash it, diff it, and share
  it across threads.
- The `pre_compact` hook dispatch uses `asyncio.run` from sync
  compression only when no event loop is already running. Inside a
  running loop the sync path skips the hook and falls straight to the
  strategy. Use `compress_messages_async` when you need guaranteed
  hook dispatch.
- The compressor does not call a tokenizer. `estimate_tokens()` uses a
  ~4 chars-per-token heuristic; swap in a real tokenizer at the caller
  when precision matters.
