# adk-fluent

Fluent Python and TypeScript builders for Google's [Agent Development Kit](https://google.github.io/adk-docs/).

The builders return native ADK objects. The repository generates the Python and TypeScript surfaces from a shared manifest so the two packages can be checked for API parity.

<p align="center">
  <a href="https://pypi.org/project/adk-fluent/"><img alt="PyPI" src="https://img.shields.io/pypi/v/adk-fluent?label=PyPI&color=3775A9"></a>
  <a href="https://www.npmjs.com/package/adk-fluent-ts"><img alt="npm" src="https://img.shields.io/npm/v/adk-fluent-ts?label=npm&color=CB3837"></a>
  <a href="https://github.com/vamsiramakrishnan/adk-fluent/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/vamsiramakrishnan/adk-fluent/ci.yml?branch=master&label=CI"></a>
  <a href="https://vamsiramakrishnan.github.io/adk-fluent/"><img alt="Docs" src="https://img.shields.io/badge/docs-latest-0A7EC2"></a>
</p>

## Packages

| Package | Language | Source |
| --- | --- | --- |
| `adk-fluent` | Python 3.11+ | [`python/`](python/) |
| `adk-fluent-ts` | TypeScript | [`ts/`](ts/) |

Shared manifests, seeds, scanners, and generators live under [`shared/`](shared/).

## Python install

```bash
pip install adk-fluent
```

Create and run a text agent:

```python
from adk_fluent import Agent

agent = (
    Agent("helper", "gemini-2.5-flash")
    .instruct("Answer in one sentence.")
)

print(agent.ask("What is ADK?"))
```

`.ask()` manages the runner/session path for simple calls.

Use `.build()` when you need the native ADK object:

```python
native_agent = (
    Agent("helper", "gemini-2.5-flash")
    .instruct("Answer in one sentence.")
    .build()
)
```

## TypeScript install

```bash
npm install adk-fluent-ts
```

Example:

```ts
import { Agent } from "adk-fluent-ts";

const pipeline = new Agent("writer", "gemini-2.5-flash")
  .instruct("Write a draft about {topic}.")
  .writes("draft")
  .then(
    new Agent("reviewer", "gemini-2.5-flash")
      .instruct("Review the draft: {draft}")
      .writes("feedback"),
  )
  .build();
```

See [`ts/README.md`](ts/README.md) for the TypeScript surface.

## Builders and operators

The Python package supports explicit builders and expression operators.

Explicit builder:

```python
from adk_fluent import Agent, Pipeline

pipeline = (
    Pipeline("research")
    .step(
        Agent("searcher", "gemini-2.5-flash")
        .instruct("Find relevant material.")
        .outputs("evidence")
    )
    .step(
        Agent("writer", "gemini-2.5-flash")
        .instruct("Summarize {evidence}.")
    )
    .build()
)
```

Operator form:

```python
pipeline = (
    Agent("searcher", "gemini-2.5-flash")
    .instruct("Find relevant material.")
    .outputs("evidence")
    >> Agent("writer", "gemini-2.5-flash")
    .instruct("Summarize {evidence}.")
).build()
```

Both forms compile to ADK agent objects. Use the form that keeps the topology readable.

## Mock path

Basic behavior can be exercised without an API key:

```python
from adk_fluent import Agent

agent = (
    Agent("demo", "gemini-2.5-flash")
    .instruct("You are concise.")
    .mock(["Hello."])
)

print(agent.ask("Hi"))
```

A mock response checks local builder/session behavior. It does not test a live model or deployed ADK runtime.

## Optional extras

```bash
pip install adk-fluent[a2a]
pip install adk-fluent[yaml]
pip install adk-fluent[rich]
pip install adk-fluent[search]
pip install adk-fluent[pii]
pip install adk-fluent[observability]
pip install adk-fluent[dev]
pip install adk-fluent[docs]
```

Install only the extras needed by the application.

## Three authoring paths

The repository contains three related layers:

| Path | Use when |
| --- | --- |
| Builders / operators | the topology belongs in Python or TypeScript code |
| Skills | the reusable topology or workflow should be declarative and portable |
| Harness / reactive APIs | the runtime needs signals, budgets, event handling, or autonomous control loops |

These layers solve different problems. They are not interchangeable syntax for every use case.

See the [decision guide](https://vamsiramakrishnan.github.io/adk-fluent/decision-guide/) for examples.

## Generated parity

The Python and TypeScript packages are generated from shared inputs under `shared/`.

Generation lets CI compare the intended surfaces and catch drift between languages. It does not mean arbitrary handwritten code in the two packages is automatically equivalent; parity is limited to the generated contracts and checks.

## IDE support

The Python package ships type information used by Pyright/Pylance and PyCharm.

```python
agent = Agent("demo")
agent.  # editor completion exposes builder methods
```

Definition-time errors include suggestions for unknown builder fields where the library can resolve a close match.

## A2UI

The core package includes the declarative A2UI namespace used to compose and compile agent UI structures.

The external A2UI toolset integration depends on its separate package availability. Check the [A2UI guide](https://vamsiramakrishnan.github.io/adk-fluent/user-guide/a2ui/) for the current support boundary.

## Coding-agent skills

Reusable coding-harness skills live under [`skills/`](skills/).

They document repository operations and common ADK authoring tasks. The Python/TypeScript packages remain the executable implementation; skills should call those surfaces rather than duplicate their semantics in prose.

## Repository layout

```text
python/      Python package
  README.md  Python-specific usage

ts/          TypeScript package
  README.md  TypeScript-specific usage

shared/      manifest, seeds, scanners and generators
docs/        documentation site source
skills/      coding-agent skills
justfile     repository tasks
```

## Development

```bash
git clone https://github.com/vamsiramakrishnan/adk-fluent.git
cd adk-fluent
just test-all
```

Useful tasks are listed with:

```bash
just --list
```

## Documentation

- [Getting started](https://vamsiramakrishnan.github.io/adk-fluent/getting-started/)
- [Decision guide](https://vamsiramakrishnan.github.io/adk-fluent/decision-guide/)
- [Editor and coding-agent setup](https://vamsiramakrishnan.github.io/adk-fluent/editor-setup/)
- [A2UI](https://vamsiramakrishnan.github.io/adk-fluent/user-guide/a2ui/)
- [`python/README.md`](python/README.md)
- [`ts/README.md`](ts/README.md)

## Boundaries

- adk-fluent builds ADK objects; ADK defines the runtime behavior of those objects.
- Fewer source lines are a convenience, not a correctness guarantee.
- Generated parity checks cover the surfaces driven by the shared manifest.
- Mock execution is local test behavior, not evidence about a live model.

## License

See [LICENSE](LICENSE).
