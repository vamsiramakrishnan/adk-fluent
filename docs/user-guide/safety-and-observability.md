# Safety & observability

The production perimeter: what the agent outputs, what it costs, what
it logs, and how you prove it still works a week from now.

```{mermaid}
flowchart LR
    I[input] --> MW[Middleware<br/>M.retry, M.cost,<br/>M.trace, M.timeout]
    MW --> A[agent]
    A --> G[Guards<br/>G.pii, G.toxicity,<br/>G.length, G.schema]
    G --> O[output]
    A -.telemetry.-> OBS[(logs, traces,<br/>metrics)]
    A -.regressions.-> EV[Evaluation<br/>E.case, .eval_suite]

    classDef gate fill:#ffebee,stroke:#c62828,color:#b71c1c
    classDef obs fill:#e8f5e9,stroke:#2e7d32,color:#1b5e20
    class MW,G gate
    class OBS,EV obs
```

## Chapters

| Chapter | Use it for |
|---|---|
| [Middleware](middleware.md) | Cross-cutting concerns that wrap every agent call: retry, timeout, logging, cost, circuit-breaker. |
| [Guards](guards.md) | Output validation that *must* run before the response leaves the agent — PII, toxicity, max-length, schema. |
| [Evaluation](evaluation.md) | LLM-as-judge scoring, criterion scoring, eval suites for regression testing. |
| [Testing](testing.md) | Deterministic substitutes: `.mock()` replaces the LLM; `.test()` asserts inline; both are CI-safe. |

Pair this tier with [Patterns & control flow](patterns-and-control-flow.md) —
production deployments almost always combine the two.

:::{tip} Middleware vs guards: two different jobs
**Middleware** (`M.*`) wraps the *call*: retries on network blips,
cost accounting, latency metrics. **Guards** (`G.*`) validate the
*response*: "does this output contain PII?", "is it under 500 chars?".
Don't put retry logic in a guard, and don't put PII detection in
middleware — they run in different lifecycle phases.
:::
