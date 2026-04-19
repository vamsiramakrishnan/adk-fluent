# Backends & execution

What `.build()` actually does, what runs the resulting graph, and how
to swap the runtime without rewriting the agents.

```{mermaid}
flowchart LR
    F[Fluent builder<br/>Agent, Pipeline,<br/>FanOut, Loop] --> IR[IR tree<br/>inspectable,<br/>serialisable]
    IR --> N[Native ADK<br/>LlmAgent, Runner]
    IR --> T[Temporal<br/>durable workflow]
    IR --> X[Custom backend<br/>asyncio / DBOS /<br/>Prefect]

    classDef f fill:#e3f2fd,stroke:#1565c0,color:#0d47a1
    classDef b fill:#fff3e0,stroke:#e65100,color:#bf360c
    class F,IR f
    class N,T,X b
```

## Chapters

| Chapter | Read when |
|---|---|
| [IR & backends](ir-and-backends.md) | You want to know what `.build()` produces under the hood, or you're implementing a custom backend. |
| [Execution backends](execution-backends.md) | Your agents need durable execution, horizontal scaling, or a scheduler outside the Python process. |
| [Temporal guide](temporal-guide.md) | You've picked Temporal and want the step-by-step wiring: workflow definitions, activities, signalling. |

:::{tip} You almost always want the default
The default ADK backend — local, in-process — handles 95% of
production workloads including streaming, sessions, and multi-agent
topologies. Reach for Temporal or DBOS only when you need durable
execution across process restarts or horizontal fan-out.
:::
