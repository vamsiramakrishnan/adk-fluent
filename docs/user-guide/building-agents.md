# Building agents

Chapters for writing the body of an agent: prompts, execution,
callbacks, presets, and how structured data moves in and out.

| Chapter | When you need it |
|---|---|
| [Prompts](prompts.md) | Compose system prompts with the `P` namespace (role, task, constraints, examples). |
| [Execution](execution.md) | `.ask()` vs `.ask_async()`, streaming, sessions, batch. |
| [Callbacks](callbacks.md) | `before_*` / `after_*` hooks for auditing, retries, injection. |
| [Presets](presets.md) | Bundle model, instruction, tools, callbacks into a reusable `Preset`. |
| [State transforms](state-transforms.md) | The `S` namespace: pick/drop/rename/merge session-state keys. |
| [Structured data](structured-data.md) | `.returns(Schema)` for JSON-constrained LLM output. |
| [Context engineering](context-engineering.md) | The `C` namespace: what the LLM actually sees, turn by turn. |

If you have not read the [Foundations tier](foundations.md), read
that first.
