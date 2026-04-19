# Foundations

Start here. These four chapters give you the mental model and the
minimum API you need before touching anything else.

| Read in order | What you learn |
|---|---|
| [Architecture & core concepts](architecture-and-concepts.md) | The three ADK channels — conversation, state, instruction templating — and why that shapes every builder method. |
| [Builders](builders.md) | The `Agent`, `Pipeline`, `FanOut`, `Loop` builders and how `.build()` produces native ADK objects. |
| [Expression language](expression-language.md) | The `>>`, `\|`, `*`, `//`, `@` operators as a quick, immutable alternative to explicit builders. |
| [Data flow](data-flow.md) | The five orthogonal data-flow concerns — context, input, output, storage, contract — and which method owns each. |

After these four pages you can build any linear or parallel
workflow. Return here and pick the next tier only when you hit a
concrete need it solves.
