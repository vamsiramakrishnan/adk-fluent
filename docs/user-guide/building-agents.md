# Building agents

The body of an agent: what it says, how it runs, how data shaped like
anything other than a string gets in and out.

```{mermaid}
flowchart TB
    subgraph instruction[What the LLM sees]
        P[Prompts<br/>P namespace]
        C[Context<br/>C namespace]
    end
    subgraph runtime[How it runs]
        E[Execution<br/>.ask / .stream / .map]
        K[Callbacks<br/>before_*/after_*]
        R[Presets<br/>reusable bundles]
    end
    subgraph data[What flows through]
        S[State transforms<br/>S namespace]
        D[Structured data<br/>.returns Schema]
    end

    P --> E
    C --> E
    E --> K
    D --> S

    classDef inst fill:#fce4ec,stroke:#ad1457,color:#880e4f
    classDef run fill:#e8f5e9,stroke:#2e7d32,color:#1b5e20
    classDef dat fill:#fff3e0,stroke:#e65100,color:#bf360c
    class P,C inst
    class E,K,R run
    class S,D dat
```

## Chapters

| Chapter | Read it when |
|---|---|
| [Prompts](prompts.md) | You want role + task + constraints + examples in one place (`P.role()` + `P.task()` + …). |
| [Execution](execution.md) | You need `.ask()` vs `.ask_async()`, streaming, sessions, or batched `.map()`. |
| [Callbacks](callbacks.md) | You need to audit, retry, or mutate inputs/outputs at `before_*`/`after_*` boundaries. |
| [Presets](presets.md) | The same model/instruction/tool bundle is showing up in five different agents. |
| [State transforms](state-transforms.md) | You need to reshape state keys between steps (`S.pick`, `S.rename`, `S.merge`). |
| [Structured data](structured-data.md) | You want the LLM to emit JSON that matches a Pydantic schema, not prose. |
| [Context engineering](context-engineering.md) | The agent is seeing too much (or too little) conversation history. |

New here? Finish [Foundations](foundations.md) first — this tier assumes
you know what a builder and a state key are.
