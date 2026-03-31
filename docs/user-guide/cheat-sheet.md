# Cheat Sheet

:::{admonition} At a Glance
:class: tip

- One-page quick reference for all operators, modules, and key methods
- Print this page and pin it to your monitor
- Every entry links to its full documentation
:::

## Expression Operators

| Operator | Meaning | Result | Example |
|----------|---------|--------|---------|
| `>>` | Sequence | `SequentialAgent` | `a >> b >> c` |
| `>> fn` | Function step | `FnAgent` | `a >> my_func >> b` |
| `\|` | Parallel | `ParallelAgent` | `a \| b \| c` |
| `* n` | Loop (fixed) | `LoopAgent` | `(a >> b) * 3` |
| `* until(pred)` | Loop (conditional) | `LoopAgent` | `(a >> b) * until(pred, max=5)` |
| `@` | Typed output | `output_schema` | `a @ MyModel` |
| `//` | Fallback | First success | `fast // strong` |
| `Route(key)` | Deterministic branch | Custom | `Route("k").eq("v", agent)` |

## Agent Builder --- Core Methods

| Method | Purpose | ADK Field |
|--------|---------|-----------|
| `.model(str)` | Set LLM model | `model` |
| `.instruct(str \| P)` | System prompt | `instruction` |
| `.describe(str)` | Metadata (NOT sent to LLM) | `description` |
| `.static(str)` | Cached instruction (enables context caching) | `instruction` → system |
| `.tool(fn)` | Add a tool | `tools` |
| `.tools(list \| T)` | Set/replace all tools | `tools` |
| `.build()` | Compile to native ADK object | --- |

## Agent Builder --- Data Flow

| Method | Concern | Effect |
|--------|---------|--------|
| `.reads(*keys)` | Context | Inject state keys, suppress history |
| `.context(C)` | Context | Fine-grained history control |
| `.accepts(Schema)` | Input | Tool-mode input validation |
| `.returns(Schema)` | Output | Constrain to structured JSON |
| `.writes(key)` | Storage | Store response in state |
| `.produces(Schema)` | Contract | Static annotation (no runtime effect) |
| `.consumes(Schema)` | Contract | Static annotation (no runtime effect) |

## Agent Builder --- Flow Control

| Method | Purpose |
|--------|---------|
| `.sub_agent(agent)` | Add transfer target (LLM decides when) |
| `.agent_tool(agent)` | Wrap agent as tool (parent stays in control) |
| `.isolate()` | Prevent all transfers (most predictable) |
| `.stay()` | Prevent transfer to parent |
| `.no_peers()` | Prevent transfer to siblings |
| `.loop_until(pred, max=)` | Loop while predicate is false |
| `.proceed_if(pred)` | Skip if predicate is false |
| `.timeout(seconds)` | Wrap with time limit |

## Agent Builder --- Callbacks

| Method | Timing |
|--------|--------|
| `.before_agent(fn)` | Before agent execution |
| `.after_agent(fn)` | After agent execution |
| `.before_model(fn)` | Before each LLM call |
| `.after_model(fn)` | After each LLM call |
| `.before_tool(fn)` | Before each tool call |
| `.after_tool(fn)` | After each tool call |
| `.guard(fn \| G)` | Output validation (after_model) |
| `.on_model_error(fn)` | LLM error handler |
| `.on_tool_error(fn)` | Tool error handler |

## Agent Builder --- Execution

| Method | Mode | Async? |
|--------|------|--------|
| `.build()` | Compile to ADK | No |
| `.ask(prompt)` | One-shot sync | No |
| `.ask_async(prompt)` | One-shot async | Yes |
| `.stream(prompt)` | Streaming iterator | Yes |
| `.events(prompt)` | Raw ADK events | Yes |
| `.session()` | Multi-turn chat | Yes (context manager) |
| `.map(prompts)` | Batch sync | No |
| `.map_async(prompts)` | Batch async | Yes |
| `.test(prompt, contains=)` | Smoke test | No |
| `.mock(responses)` | Replace LLM | No |

## Agent Builder --- Introspection

| Method | Returns |
|--------|---------|
| `.explain()` | Full builder state summary |
| `.validate()` | Early error detection (chainable) |
| `.data_flow()` | Five-concern snapshot |
| `.llm_anatomy()` | What the LLM sees |
| `.to_ir()` | IR tree node |
| `.to_mermaid()` | Mermaid diagram |
| `.clone(name)` | Deep copy with new name |
| `.with_(**overrides)` | Immutable variant |

## S --- State Transforms

| Factory | Effect | Type |
|---------|--------|------|
| `S.pick(*keys)` | Keep only named keys | Replacement |
| `S.drop(*keys)` | Remove named keys | Replacement |
| `S.rename(**kw)` | Rename keys | Replacement |
| `S.set(**kv)` | Set values | Delta |
| `S.default(**kv)` | Fill missing keys | Delta |
| `S.merge(*keys, into=)` | Combine keys | Delta |
| `S.transform(key, fn)` | Apply function | Delta |
| `S.compute(**fns)` | Derive new keys | Delta |
| `S.guard(pred)` | Assert invariant | Inspection |
| `S.log(*keys)` | Debug print | Inspection |

Compose: `>>` (chain), `+` (combine)

## C --- Context Engineering

| Factory | LLM Sees |
|---------|----------|
| `C.default()` | All history |
| `C.none()` | Instruction only |
| `C.user_only()` | User messages only |
| `C.window(n=)` | Last N turn-pairs |
| `C.from_state(*keys)` | Named state keys |
| `C.from_agents(*names)` | User + named agents |
| `C.exclude_agents(*names)` | Everything except named |
| `C.template(str)` | Rendered template |
| `C.budget(max_tokens=)` | Token-limited |
| `C.summarize()` | LLM-summarized |

Compose: `+` (union), `|` (pipe)

## P --- Prompt Composition

| Factory | Section |
|---------|---------|
| `P.role(text)` | Agent persona |
| `P.context(text)` | Background |
| `P.task(text)` | Primary objective |
| `P.constraint(*rules)` | Rules |
| `P.format(text)` | Output format |
| `P.example(input=, output=)` | Few-shot |
| `P.section(name, text)` | Custom section |
| `P.when(pred, block)` | Conditional |
| `P.from_state(*keys)` | Dynamic state |
| `P.template(text)` | Placeholders |

Compose: `+` (union), `|` (pipe). Order: role → context → task → constraint → format → example.

## M --- Middleware

| Factory | Purpose |
|---------|---------|
| `M.retry(max_attempts=)` | Retry with backoff |
| `M.log()` | Structured logging |
| `M.cost()` | Token usage tracking |
| `M.latency()` | Per-agent latency |
| `M.circuit_breaker(max_fails=)` | Circuit breaker |
| `M.timeout(seconds)` | Per-agent timeout |
| `M.cache(ttl=)` | Response caching |
| `M.fallback_model(model)` | Fallback model |

Compose: `|` (chain)

## T --- Tool Composition

| Factory | Purpose |
|---------|---------|
| `T.fn(callable)` | Wrap function |
| `T.agent(agent)` | Wrap agent as tool |
| `T.google_search()` | Google Search |
| `T.mcp(server)` | MCP server |
| `T.openapi(spec)` | OpenAPI spec |
| `T.mock(responses)` | Mock tool |
| `T.confirm(prompt=)` | Human confirmation |
| `T.timeout(seconds)` | Tool timeout |

Compose: `|` (chain)

## G --- Guards

| Factory | Purpose |
|---------|---------|
| `G.pii(detector=)` | PII detection/redaction |
| `G.toxicity(threshold=)` | Content safety |
| `G.length(max=)` | Max response length |
| `G.schema(model)` | Validate against Pydantic |
| `G.guard(fn)` | Custom guard function |

Compose: `|` (chain)

## Composition Patterns

| Pattern | Equivalent | Use Case |
|---------|-----------|----------|
| `review_loop(worker, reviewer)` | `(w >> r) * until(...)` | Iterative refinement |
| `cascade(a, b, c)` | `a // b // c` | Cost-optimized fallback |
| `fan_out_merge(*agents)` | `(a \| b) >> S.merge(...)` | Parallel + combine |
| `chain(*agents)` | `a >> b >> c` | Sequential with wiring |
| `conditional(pred, a, b)` | `gate(pred)` | If/else branching |
| `supervised(worker, supervisor)` | `(w >> s) * until(approved)` | Approval workflow |
| `map_reduce(mapper, reducer)` | `map_over(key)` | Process list items |

---

:::{seealso}
- {doc}`concept-map` --- visual map of all concepts
- {doc}`glossary` --- term definitions
- {doc}`../generated/api/index` --- full API reference
:::
