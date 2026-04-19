# Foundations

The mental model. Read this tier once, top to bottom, and every other
builder method in the library will slot into place.

```{mermaid}
flowchart LR
    A[Architecture<br/>& concepts] --> B[Builders]
    B --> C[Expression<br/>language]
    B --> D[Data flow]
    C -.alternative syntax.-> B
    D -.which method<br/>does what.-> B

    classDef core fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#0d47a1
    class A,B,C,D core
```

## Read in order

| | Chapter | The one thing it teaches |
|---|---|---|
| 1 | [Architecture & concepts](architecture-and-concepts.md) | ADK has three channels — **conversation**, **state**, **instruction** — and every builder method touches exactly one of them. |
| 2 | [Builders](builders.md) | `Agent`, `Pipeline`, `FanOut`, `Loop`. `.build()` returns a real `LlmAgent` — not a wrapper. |
| 3 | [Expression language](expression-language.md) | `>>`, `\|`, `*`, `//`, `@` — immutable sub-expressions that compose without builders. |
| 4 | [Data flow](data-flow.md) | Five orthogonal concerns: **context**, **input**, **output**, **storage**, **contract**. One method per concern. Confusion disappears. |

After this tier you can ship any linear or parallel workflow. Pick the
next tier when — and only when — you hit a concrete need it solves.
