# Safety & observability

Guardrails around production agents: output validation, middleware
for retries/tracing/cost, and evaluation for regression testing.

| Chapter | What it gives you |
|---|---|
| [Middleware](middleware.md) | `M` namespace: retry, log, cost, latency, circuit-breaker. |
| [Guards](guards.md) | `G` namespace: PII, toxicity, length, schema — output validation. |
| [Evaluation](evaluation.md) | `E` namespace and `.eval()` / `.eval_suite()` for judge-based scoring. |
| [Testing](testing.md) | Inline `.test()` smoke tests and `.mock()` for deterministic LLM substitutes. |

These chapters pair well with [Patterns & control flow](patterns-and-control-flow.md) —
most production deployments combine the two tiers.
