# User Guide

Write agents in 1-3 lines. Get native ADK objects. Keep full control.

This guide takes you from "I know how to build a simple agent" to "I can design production multi-agent systems with data contracts, context engineering, middleware, and evaluation." Read sequentially for the full journey, or jump to the topic you need.

:::{admonition} Quick taste — every concept in 8 lines
:class: tip

```python
from adk_fluent import Agent, S, C

support = (
    S.capture("message")                                    # S: State transforms
    >> Agent("classify", "gemini-2.5-flash")
       .instruct("Classify intent.")                        # P: Prompt (via .instruct)
       .context(C.none())                                   # C: Context engineering
       .writes("intent")                                    # Data flow: named state keys
    >> Agent("resolve", "gemini-2.5-flash")
       .instruct("Resolve the {intent} issue.")             # {key} = reads from state
       .tool(lookup_customer)                                # Tools: plain functions
       .writes("resolution")
)
```
Each line maps to a concept you'll learn below. Hover over any builder method in your IDE to see its type signature.
:::

## Foundations

Start here if you're new to adk-fluent.

| Chapter | What you'll learn |
|---|---|
| [Architecture & Concepts](architecture-and-concepts.md) | How builders wrap ADK, the IR tree, and the compilation pipeline |
| [Best Practices](best-practices.md) | Opinionated guidance on when to use what |
| [Framework Comparison](comparison.md) | Side-by-side with LangGraph, CrewAI, and native ADK |

## Building Agents

The core of the library.

| Chapter | What you'll learn |
|---|---|
| [Builders](builders.md) | Constructor args, method chaining, `.build()`, typo detection, `.explain()`, serialization |
| [Expression Language](expression-language.md) | All 9 operators (`>>`, `\|`, `*`, `@`, `//`, `>>` with functions, `Route`, `race`, `dispatch`) |
| [Data Flow](data-flow.md) | `.writes()`, `.reads()`, `{key}` templates, state propagation between agents |
| [Prompts](prompts.md) | The P module: `P.role()`, `P.task()`, `P.constraint()`, section ordering, composition |
| [Execution](execution.md) | `.ask()`, `.stream()`, `.session()`, `.map()`, `.events()` |

## Advanced Capabilities

Where adk-fluent's power shows.

| Chapter | What you'll learn |
|---|---|
| [Callbacks](callbacks.md) | `.before_agent()`, `.after_model()`, `.guard()`, error callbacks |
| [Presets](presets.md) | Reusable configuration bundles with `.use()` |
| [State Transforms](state-transforms.md) | The S module: `S.pick()`, `S.merge()`, `S.guard()`, `S.branch()`, composition |
| [Structured Data](structured-data.md) | `@ Schema`, `.returns()`, `.produces()`, `.consumes()`, contract checking |
| [Context Engineering](context-engineering.md) | The C module: `C.none()`, `C.from_state()`, `C.window()`, token budgets |
| [Patterns](patterns.md) | `review_loop`, `map_reduce`, `cascade`, `fan_out_merge`, `conditional`, `supervised` |

## Infrastructure

Production concerns.

| Chapter | What you'll learn |
|---|---|
| [Visibility](visibility.md) | `.show()`, `.hide()`, `.transparent()`, topology control |
| [Transfer Control](transfer-control.md) | `.isolate()`, `.stay()`, `.no_peers()` |
| [Memory](memory.md) | `.memory()`, `.memory_auto_save()`, persistent agent memory |
| [IR & Backends](ir-and-backends.md) | `.to_ir()`, compilation, backend abstraction |
| [Execution Backends](execution-backends.md) | `.engine()`, ADK / Temporal / asyncio, capability matrix, backend selection |
| [Temporal Guide](temporal-guide.md) | Durable execution, crash recovery, determinism rules, Temporal patterns |
| [Middleware](middleware.md) | The M module: `M.retry()`, `M.log()`, `M.cost()`, `M.circuit_breaker()`, composition |
| [Guards](guards.md) | The G module: `G.pii()`, `G.toxicity()`, `G.schema()`, input/output validation |
| [Evaluation](evaluation.md) | The E module: `E.case()`, `E.criterion()`, eval suites, comparison reports |
| [Testing](testing.md) | `.mock()`, `.test()`, `check_contracts()`, `AgentHarness`, pytest integration |
| [A2A](a2a.md) | Remote agent-to-agent communication: `RemoteAgent`, `A2AServer`, discovery, resilience |
| [A2UI](a2ui.md) | Declarative agent UIs: `UI` namespace, components, operators, surfaces, presets |
| [Skills](skills.md) | Composable agent packages from SKILL.md files: `Skill`, `SkillRegistry`, `T.skill()` |

:::{admonition} Backend maturity at a glance
:class: tip

| Backend | Status | Key Feature |
|---------|--------|------------|
| **ADK** | **Stable** — production-ready, default | Native ADK objects, streaming, `adk web/run/deploy` |
| **Temporal** | **In Development** — API may change | Durable execution, crash recovery, distributed |
| **asyncio** | **In Development** — reference impl | Zero-dependency IR interpreter |
| **DBOS / Prefect** | **Conceptual** — not yet implemented | Under research |

Start with ADK. If you need durability, see [Execution Backends](execution-backends.md).
:::

## Reference

| Resource | Description |
|---|---|
| [Error Reference](error-reference.md) | Every error with cause and fix-it code |
| [ADK Samples](adk-samples/index.md) | Official ADK samples ported to adk-fluent |
| [Decision Guide](../decision-guide.md) | "Which pattern should I use?" flowchart |

```{toctree}
---
maxdepth: 2
hidden: true
---
architecture-and-concepts
best-practices
comparison
builders
expression-language
data-flow
prompts
execution
callbacks
presets
state-transforms
structured-data
context-engineering
patterns
visibility
transfer-control
memory
ir-and-backends
execution-backends
temporal-guide
middleware
guards
evaluation
testing
a2a
a2ui
skills
error-reference
adk-samples/index
```

## Interactive Visual References

Rich interactive diagrams — open in a new tab for the full experience, or explore the embedded previews below.

```{raw} html
<div class="visual-ref-grid">

  <div class="visual-ref-card" data-accent="var(--adk-accent)">
    <div class="visual-ref-icon">
      <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
        <rect x="4" y="8" width="40" height="32" rx="4" stroke="currentColor" stroke-width="2" fill="none"/>
        <line x1="4" y1="16" x2="44" y2="16" stroke="currentColor" stroke-width="1.5" opacity="0.4"/>
        <line x1="4" y1="24" x2="44" y2="24" stroke="currentColor" stroke-width="1.5" opacity="0.4"/>
        <line x1="4" y1="32" x2="44" y2="32" stroke="currentColor" stroke-width="1.5" opacity="0.4"/>
        <circle cx="12" cy="20" r="3" fill="#E65100"/>
        <rect x="18" y="18" width="16" height="4" rx="2" fill="#E65100" opacity="0.3"/>
        <circle cx="12" cy="28" r="3" fill="#0ea5e9"/>
        <rect x="18" y="26" width="12" height="4" rx="2" fill="#0ea5e9" opacity="0.3"/>
        <circle cx="12" cy="36" r="3" fill="#10b981"/>
        <rect x="18" y="34" width="20" height="4" rx="2" fill="#10b981" opacity="0.3"/>
      </svg>
    </div>
    <div class="visual-ref-content">
      <h4><a href="../module-lifecycle-reference.html" target="_blank" rel="noopener">Module Lifecycle Reference ↗</a></h4>
      <p>Where each module (S, C, P, A, M, T, E, G) fires during execution. Swim-lane timeline, interaction grid, and step-through walkthrough.</p>
      <div class="visual-ref-tags">
        <span class="vr-tag" style="--tag-color: #E65100">BUILD</span>
        <span class="vr-tag" style="--tag-color: #0ea5e9">PRE</span>
        <span class="vr-tag" style="--tag-color: #f59e0b">LLM</span>
        <span class="vr-tag" style="--tag-color: #10b981">POST</span>
        <span class="vr-tag" style="--tag-color: #e94560">TOOL</span>
      </div>
    </div>
  </div>

  <div class="visual-ref-card" data-accent="#e94560">
    <div class="visual-ref-icon">
      <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
        <rect x="4" y="6" width="12" height="12" rx="3" stroke="#e94560" stroke-width="2" fill="none"/>
        <text x="10" y="15" text-anchor="middle" fill="#e94560" font-size="9" font-weight="700" font-family="sans-serif">P</text>
        <rect x="18" y="6" width="12" height="12" rx="3" stroke="#0ea5e9" stroke-width="2" fill="none"/>
        <text x="24" y="15" text-anchor="middle" fill="#0ea5e9" font-size="9" font-weight="700" font-family="sans-serif">C</text>
        <rect x="32" y="6" width="12" height="12" rx="3" stroke="#10b981" stroke-width="2" fill="none"/>
        <text x="38" y="15" text-anchor="middle" fill="#10b981" font-size="9" font-weight="700" font-family="sans-serif">S</text>
        <path d="M10 22 L10 30 Q10 34 14 34 L34 34 Q38 34 38 30 L38 22" stroke="#FFB74D" stroke-width="1.5" fill="none" stroke-dasharray="3,3"/>
        <rect x="8" y="34" width="32" height="10" rx="3" stroke="#FFB74D" stroke-width="2" fill="none"/>
        <text x="24" y="42" text-anchor="middle" fill="#FFB74D" font-size="7" font-weight="600" font-family="sans-serif">LLM Assembly</text>
      </svg>
    </div>
    <div class="visual-ref-content">
      <h4><a href="../pcs-visual-reference.html" target="_blank" rel="noopener">P·C·S Visual Reference ↗</a></h4>
      <p>How Prompt, Context, and State modules compose to assemble what the LLM sees. Factory catalogs, composition rules, and assembly order.</p>
      <div class="visual-ref-tags">
        <span class="vr-tag" style="--tag-color: #e94560">Prompt</span>
        <span class="vr-tag" style="--tag-color: #0ea5e9">Context</span>
        <span class="vr-tag" style="--tag-color: #10b981">State</span>
      </div>
    </div>
  </div>

  <div class="visual-ref-card" data-accent="#f59e0b">
    <div class="visual-ref-icon">
      <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
        <circle cx="10" cy="24" r="6" stroke="#e94560" stroke-width="2" fill="none"/>
        <text x="10" y="27" text-anchor="middle" fill="#e94560" font-size="7" font-weight="700" font-family="sans-serif">A</text>
        <circle cx="38" cy="24" r="6" stroke="#0ea5e9" stroke-width="2" fill="none"/>
        <text x="38" y="27" text-anchor="middle" fill="#0ea5e9" font-size="7" font-weight="700" font-family="sans-serif">B</text>
        <line x1="16" y1="24" x2="30" y2="24" stroke="#f59e0b" stroke-width="2"/>
        <polygon points="30,21 34,24 30,27" fill="#f59e0b"/>
        <text x="24" y="20" text-anchor="middle" fill="#f59e0b" font-size="8" font-weight="700" font-family="monospace">&gt;&gt;</text>
        <circle cx="24" cy="38" r="5" stroke="#10b981" stroke-width="1.5" fill="none"/>
        <text x="24" y="41" text-anchor="middle" fill="#10b981" font-size="7" font-weight="700" font-family="sans-serif">C</text>
        <line x1="10" y1="30" x2="24" y2="33" stroke="#FFB74D" stroke-width="1.5"/>
        <line x1="38" y1="30" x2="24" y2="33" stroke="#FFB74D" stroke-width="1.5"/>
        <text x="7" y="38" text-anchor="middle" fill="#FFB74D" font-size="7" font-weight="700" font-family="monospace">|</text>
      </svg>
    </div>
    <div class="visual-ref-content">
      <h4><a href="../operator-algebra-reference.html" target="_blank" rel="noopener">Operator Algebra Reference ↗</a></h4>
      <p>All 9 operators with SVG flow diagrams, code examples, and composition rules. <code>>></code>, <code>|</code>, <code>*</code>, <code>@</code>, <code>//</code>, <code>Route</code>, and more.</p>
      <div class="visual-ref-tags">
        <span class="vr-tag" style="--tag-color: #e94560">Sequential</span>
        <span class="vr-tag" style="--tag-color: #0ea5e9">Parallel</span>
        <span class="vr-tag" style="--tag-color: #10b981">Loop</span>
        <span class="vr-tag" style="--tag-color: #f59e0b">Schema</span>
        <span class="vr-tag" style="--tag-color: #FFB74D">Fallback</span>
      </div>
    </div>
  </div>

  <div class="visual-ref-card" data-accent="#10b981">
    <div class="visual-ref-icon">
      <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
        <rect x="6" y="18" width="10" height="12" rx="2" stroke="#0ea5e9" stroke-width="1.5" fill="none"/>
        <text x="11" y="27" text-anchor="middle" fill="#0ea5e9" font-size="6" font-weight="700" font-family="sans-serif">R</text>
        <rect x="19" y="10" width="10" height="12" rx="2" stroke="#e94560" stroke-width="1.5" fill="none"/>
        <text x="24" y="19" text-anchor="middle" fill="#e94560" font-size="6" font-weight="700" font-family="sans-serif">O</text>
        <rect x="19" y="26" width="10" height="12" rx="2" stroke="#10b981" stroke-width="1.5" fill="none"/>
        <text x="24" y="35" text-anchor="middle" fill="#10b981" font-size="6" font-weight="700" font-family="sans-serif">W</text>
        <rect x="32" y="14" width="10" height="12" rx="2" stroke="#f59e0b" stroke-width="1.5" fill="none"/>
        <text x="37" y="23" text-anchor="middle" fill="#f59e0b" font-size="6" font-weight="700" font-family="sans-serif">I</text>
        <rect x="32" y="30" width="10" height="12" rx="2" stroke="#FFB74D" stroke-width="1.5" fill="none"/>
        <text x="37" y="39" text-anchor="middle" fill="#FFB74D" font-size="6" font-weight="700" font-family="sans-serif">C</text>
        <path d="M16 24 L19 16" stroke="#0ea5e9" stroke-width="1" opacity="0.5"/>
        <path d="M16 24 L19 32" stroke="#10b981" stroke-width="1" opacity="0.5"/>
      </svg>
    </div>
    <div class="visual-ref-content">
      <h4><a href="../data-flow-reference.html" target="_blank" rel="noopener">Data Flow Reference ↗</a></h4>
      <p>The five orthogonal data-flow concerns: <code>.reads()</code>, <code>.returns()</code>, <code>.writes()</code>, <code>.accepts()</code>, and <code>.produces()</code>. Timeline, confusion matrix, and decision flowchart.</p>
      <div class="visual-ref-tags">
        <span class="vr-tag" style="--tag-color: #0ea5e9">Context</span>
        <span class="vr-tag" style="--tag-color: #e94560">Output</span>
        <span class="vr-tag" style="--tag-color: #10b981">Storage</span>
        <span class="vr-tag" style="--tag-color: #f59e0b">Input</span>
        <span class="vr-tag" style="--tag-color: #FFB74D">Contract</span>
      </div>
    </div>
  </div>

  <div class="visual-ref-card" data-accent="#e94560">
    <div class="visual-ref-icon">
      <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
        <rect x="14" y="4" width="20" height="10" rx="3" stroke="#f59e0b" stroke-width="1.5" fill="none"/>
        <text x="24" y="12" text-anchor="middle" fill="#f59e0b" font-size="7" font-weight="600" font-family="sans-serif">Parent</text>
        <rect x="4" y="34" width="16" height="10" rx="3" stroke="#e94560" stroke-width="1.5" fill="none"/>
        <text x="12" y="42" text-anchor="middle" fill="#e94560" font-size="6" font-weight="600" font-family="sans-serif">sub</text>
        <rect x="28" y="34" width="16" height="10" rx="3" stroke="#0ea5e9" stroke-width="1.5" fill="none"/>
        <text x="36" y="42" text-anchor="middle" fill="#0ea5e9" font-size="6" font-weight="600" font-family="sans-serif">tool</text>
        <line x1="20" y1="14" x2="12" y2="34" stroke="#e94560" stroke-width="1.5"/>
        <line x1="28" y1="14" x2="36" y2="34" stroke="#0ea5e9" stroke-width="1.5" stroke-dasharray="4,2"/>
        <polygon points="11,31 13,31 12,34" fill="#e94560"/>
      </svg>
    </div>
    <div class="visual-ref-content">
      <h4><a href="../delegation-reference.html" target="_blank" rel="noopener">Delegation &amp; Transfer Reference ↗</a></h4>
      <p><code>.sub_agent()</code> vs <code>.agent_tool()</code> control flow, transfer control matrix (<code>.isolate()</code>, <code>.stay()</code>, <code>.no_peers()</code>), and common topologies.</p>
      <div class="visual-ref-tags">
        <span class="vr-tag" style="--tag-color: #e94560">Transfer</span>
        <span class="vr-tag" style="--tag-color: #0ea5e9">AgentTool</span>
        <span class="vr-tag" style="--tag-color: #10b981">Isolate</span>
        <span class="vr-tag" style="--tag-color: #f59e0b">Topology</span>
      </div>
    </div>
  </div>

  <div class="visual-ref-card" data-accent="#0ea5e9">
    <div class="visual-ref-icon">
      <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
        <circle cx="12" cy="24" r="8" stroke="#e94560" stroke-width="1.5" fill="none"/>
        <text x="12" y="27" text-anchor="middle" fill="#e94560" font-size="7" font-weight="700" font-family="sans-serif">S</text>
        <circle cx="36" cy="24" r="8" stroke="#0ea5e9" stroke-width="1.5" fill="none"/>
        <text x="36" y="27" text-anchor="middle" fill="#0ea5e9" font-size="7" font-weight="700" font-family="sans-serif">A</text>
        <line x1="20" y1="24" x2="28" y2="24" stroke="#FFB74D" stroke-width="1.5"/>
        <text x="24" y="20" text-anchor="middle" fill="#FFB74D" font-size="6" font-weight="600" font-family="sans-serif">vs</text>
        <line x1="12" y1="36" x2="12" y2="44" stroke="#e94560" stroke-width="1" opacity="0.4"/>
        <line x1="36" y1="36" x2="36" y2="44" stroke="#0ea5e9" stroke-width="1" opacity="0.4"/>
        <text x="12" y="48" text-anchor="middle" fill="#e94560" font-size="5" font-family="monospace">sync</text>
        <text x="36" y="48" text-anchor="middle" fill="#0ea5e9" font-size="5" font-family="monospace">async</text>
      </svg>
    </div>
    <div class="visual-ref-content">
      <h4><a href="../execution-modes-reference.html" target="_blank" rel="noopener">Execution Modes Reference ↗</a></h4>
      <p>Sync vs async execution: <code>.ask()</code> vs <code>.ask_async()</code>, streaming, environment compatibility matrix, and the RuntimeError trap.</p>
      <div class="visual-ref-tags">
        <span class="vr-tag" style="--tag-color: #e94560">Sync</span>
        <span class="vr-tag" style="--tag-color: #0ea5e9">Async</span>
        <span class="vr-tag" style="--tag-color: #10b981">Stream</span>
        <span class="vr-tag" style="--tag-color: #f59e0b">Batch</span>
      </div>
    </div>
  </div>

  <div class="visual-ref-card" data-accent="#FFB74D">
    <div class="visual-ref-icon">
      <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
        <circle cx="14" cy="14" r="5" stroke="#10b981" stroke-width="1.5" fill="none"/>
        <circle cx="34" cy="14" r="5" stroke="#10b981" stroke-width="1.5" fill="none"/>
        <circle cx="14" cy="34" r="5" stroke="#0ea5e9" stroke-width="1.5" fill="none"/>
        <circle cx="34" cy="34" r="5" stroke="#0ea5e9" stroke-width="1.5" fill="none"/>
        <line x1="19" y1="14" x2="29" y2="14" stroke="#10b981" stroke-width="1"/>
        <line x1="14" y1="19" x2="14" y2="29" stroke="#FFB74D" stroke-width="1" stroke-dasharray="3,2"/>
        <line x1="34" y1="19" x2="34" y2="29" stroke="#FFB74D" stroke-width="1" stroke-dasharray="3,2"/>
        <line x1="19" y1="34" x2="29" y2="34" stroke="#0ea5e9" stroke-width="1"/>
        <line x1="19" y1="17" x2="29" y2="31" stroke="#FFB74D" stroke-width="0.8" stroke-dasharray="2,2" opacity="0.5"/>
        <text x="24" y="27" text-anchor="middle" fill="#FFB74D" font-size="6" font-weight="600" font-family="sans-serif">A2A</text>
      </svg>
    </div>
    <div class="visual-ref-content">
      <h4><a href="../a2a-topology-reference.html" target="_blank" rel="noopener">A2A Topology Reference ↗</a></h4>
      <p>Local vs remote agents, A2A mesh topology, state bridging (<code>.sends()</code> / <code>.receives()</code>), resilience middleware, and discovery methods.</p>
      <div class="visual-ref-tags">
        <span class="vr-tag" style="--tag-color: #10b981">Local</span>
        <span class="vr-tag" style="--tag-color: #0ea5e9">Remote</span>
        <span class="vr-tag" style="--tag-color: #FFB74D">A2A</span>
        <span class="vr-tag" style="--tag-color: #f59e0b">Resilience</span>
      </div>
    </div>
  </div>

</div>
```
