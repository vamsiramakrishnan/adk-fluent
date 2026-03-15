# User Guide

This guide covers every aspect of adk-fluent in depth. Read sequentially for
a complete understanding, or jump to the topic you need.

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
| [Middleware](middleware.md) | The M module: `M.retry()`, `M.log()`, `M.cost()`, `M.circuit_breaker()`, composition |
| [Guards](guards.md) | The G module: `G.pii()`, `G.toxicity()`, `G.schema()`, input/output validation |
| [Evaluation](evaluation.md) | The E module: `E.case()`, `E.criterion()`, eval suites, comparison reports |
| [Testing](testing.md) | `.mock()`, `.test()`, `check_contracts()`, `AgentHarness`, pytest integration |

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
middleware
guards
evaluation
testing
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
        <circle cx="12" cy="20" r="3" fill="#6366f1"/>
        <rect x="18" y="18" width="16" height="4" rx="2" fill="#6366f1" opacity="0.3"/>
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
        <span class="vr-tag" style="--tag-color: #6366f1">BUILD</span>
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
        <path d="M10 22 L10 30 Q10 34 14 34 L34 34 Q38 34 38 30 L38 22" stroke="#a78bfa" stroke-width="1.5" fill="none" stroke-dasharray="3,3"/>
        <rect x="8" y="34" width="32" height="10" rx="3" stroke="#a78bfa" stroke-width="2" fill="none"/>
        <text x="24" y="42" text-anchor="middle" fill="#a78bfa" font-size="7" font-weight="600" font-family="sans-serif">LLM Assembly</text>
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
        <line x1="10" y1="30" x2="24" y2="33" stroke="#a78bfa" stroke-width="1.5"/>
        <line x1="38" y1="30" x2="24" y2="33" stroke="#a78bfa" stroke-width="1.5"/>
        <text x="7" y="38" text-anchor="middle" fill="#a78bfa" font-size="7" font-weight="700" font-family="monospace">|</text>
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
        <span class="vr-tag" style="--tag-color: #a78bfa">Fallback</span>
      </div>
    </div>
  </div>

</div>
```
