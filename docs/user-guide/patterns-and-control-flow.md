# Patterns & control flow

Composition, delegation, visibility, memory — how multiple agents
cooperate without stepping on each other.

```{mermaid}
flowchart LR
    P[Patterns<br/>review_loop, map_reduce,<br/>cascade, fan_out_merge] --> T[Transfer control<br/>sub_agent vs agent_tool]
    T --> V[Visibility<br/>what surfaces in<br/>the topology]
    V --> M[Memory<br/>persistence across<br/>sessions]

    classDef node fill:#ede7f6,stroke:#4527a0,color:#311b92
    class P,T,V,M node
```

## Chapters

| Chapter | Reach for it when |
|---|---|
| [Patterns](patterns.md) | You're writing the same compose-shape for the third time — use a higher-order constructor instead. |
| [Transfer control](transfer-control.md) | You need to delegate to a specialist — and you're unsure whether to call it as a tool or hand off control. |
| [Visibility](visibility.md) | Your topology diagram or audit log is cluttered with plumbing agents. |
| [Memory](memory.md) | You need continuity beyond one session — user preferences, past conversations, long-term state. |

Know the builders first — start with [Foundations](foundations.md) if
you haven't.

:::{tip} Pattern or raw builder?
Higher-order patterns (`review_loop`, `map_reduce`) are syntactic
sugar over `Pipeline` / `Loop` / `FanOut`. Start with the raw
builder; reach for a pattern only when you've written the same shape
twice. Patterns encode conventions, not capabilities.
:::
