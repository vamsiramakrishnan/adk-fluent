#!/bin/bash
set -e

WIKI_DIR=".wiki"
WIKI_REPO="https://github.com/vamsiramakrishnan/adk-fluent.wiki.git"

echo "Publishing adk-fluent Wiki..."

# 1. Setup local .wiki directory alongside the repo
if [ ! -d "$WIKI_DIR/.git" ]; then
    echo "Cloning wiki repository into $WIKI_DIR..."
    rm -rf $WIKI_DIR
    git clone $WIKI_REPO $WIKI_DIR
fi

# 2. Sync content from main docs
cp docs/getting-started.md $WIKI_DIR/Getting-Started.md
cp docs/user-guide/prompts.md $WIKI_DIR/Prompt-Engineering.md
cp docs/user-guide/builders.md $WIKI_DIR/Builder-Mechanics.md
cp docs/user-guide/expression-language.md $WIKI_DIR/Expression-Algebra.md
cp docs/user-guide/state-transforms.md "$WIKI_DIR/State-Transforms-(S-Module).md"
cp docs/user-guide/transfer-control.md $WIKI_DIR/Routing-and-Control.md
cp docs/user-guide/testing.md $WIKI_DIR/Evaluation-Harness.md
cp docs/user-guide/visibility.md $WIKI_DIR/Event-Visibility.md
cp docs/user-guide/middleware.md $WIKI_DIR/Telemetry-Integration.md

# 3. Generate Wiki-specific pages with correct formatting
# We use unescaped backticks since we are in a 'MD_EOF' literal block.
cat << 'MD_EOF' > $WIKI_DIR/Home.md
# 🌊 Welcome to adk-fluent

`adk-fluent` is a type-safe, fluent builder API for Google's Agent Development Kit (ADK). It lets you compose complex, multi-agent LLM systems with intuitive, chainable syntax, robust cross-channel contract checking, and intelligent code generation.

The expression graph is the product. ADK is the backend. The IR evolves with ADK automatically. Every cross-cutting concern — telemetry, evaluation, context — extends ADK's existing infrastructure rather than replacing it.

## 🚀 Quick Start

```python
from adk_fluent import Agent
from adk_fluent._routing import Route

pipeline = (
    Agent("classifier")
        .model("gemini-2.5-flash")
        .instruct("Classify the user's intent.")
        .outputs("intent")
    >> Route("intent").eq("booking",
        Agent("booker")
            .model("gemini-2.5-flash")
            .instruct("Help the user book.")
    )
)

app = pipeline.to_app()
```

## 📖 Key Concepts
* [Architecture & Intermediate Representation (IR)](Architecture-and-IR)
* [Context Engineering (C Module)](Context-Engineering-C-Module)
* [State Transforms (S Module)](State-Transforms-(S-Module))
* [Routing & Transfer Control](Routing-and-Control)
* [Evaluation Harness](Evaluation-Harness)
MD_EOF

cat << 'MD_EOF' > $WIKI_DIR/_Sidebar.md
## Overview
* [Home](Home)
* [Getting Started](Getting-Started)
* [Cookbook Directory](Cookbook-Directory)

## Core Modules
* [Architecture & IR](Architecture-and-IR)
* [Expression Algebra](Expression-Algebra)
* [Builder Mechanics](Builder-Mechanics)
* [Context Engineering (C Module)](Context-Engineering-C-Module)
* [State Transforms (S Module)](State-Transforms-(S-Module))
* [Prompt Engineering](Prompt-Engineering)
* [Routing & Control](Routing-and-Control)

## Advanced
* [Evaluation Harness](Evaluation-Harness)
* [Event Visibility](Event-Visibility)
* [Telemetry Integration](Telemetry-Integration)

## Development
* [Contributor Guide](Contributor-Guide)
* [Codegen Pipeline](Codegen-Pipeline)
MD_EOF

cat << 'MD_EOF' > $WIKI_DIR/_Footer.md
***

[Main Repository](https://github.com/vamsiramakrishnan/adk-fluent) | [Report a Bug](https://github.com/vamsiramakrishnan/adk-fluent/issues/new/choose) | [Releases](https://github.com/vamsiramakrishnan/adk-fluent/releases)
MD_EOF

cat << 'MD_EOF' > $WIKI_DIR/Architecture-and-IR.md
# Architecture & Intermediate Representation (IR)

`adk-fluent` decouples the fluent builder API from Google ADK through an **Intermediate Representation (IR)**. 

When you write a fluent pipeline, you aren't directly constructing ADK agents. Instead, you are building an immutable, introspectable syntax tree.

## The Compilation Pipeline

```text
[ Fluent Chain ]  ──to_ir()──>  [ Frozen Dataclass IR Tree ]  ──to_app()──>  [ Native ADK App ]
```

## Why an IR?

1. **Introspection**: You can analyze the graph *before* execution to infer context dependencies, event visibility, and type contracts.
2. **Pluggable Backends**: You can compile the exact same fluent code to ADK, to a Mermaid diagram string, or to an A2A (Agent-to-Agent) deployment manifest.
3. **Immutability**: IR nodes are frozen dataclasses, making them perfectly safe to cache, clone, and traverse.

## Builder to Node Mapping

Every builder maps to an IR node type:

| Builder | IR Node | ADK Target |
|---------|---------|----------|
| `Agent` | `AgentNode` | `LlmAgent` |
| `Pipeline` / `>>` | `SequenceNode` | `SequentialAgent` |
| `FanOut` / `\|` | `ParallelNode` | `ParallelAgent` |
| `Loop` / `*` | `LoopNode` | `LoopAgent` |
| `>> fn` | `TransformNode` | `FnAgent` (custom) |
| `tap(fn)` | `TapNode` | `TapAgent` (custom) |
| `a // b` | `FallbackNode` | `FallbackAgent` (custom) |
| `race(a, b)` | `RaceNode` | `RaceAgent` (custom) |
| `gate(pred)` | `GateNode` | `GateAgent` (custom) |
| `Route(...)` | `RouteNode` | `_RouteAgent` (custom) |
MD_EOF

cat << 'MD_EOF' > $WIKI_DIR/Context-Engineering-C-Module.md
# Context Engineering (The C Module)

In a multi-agent DAG, each agent has a different view of the world. ADK provides three independent communication channels (conversation history, session state, instruction templating) that developers typically manage manually.

**Context Engineering** (the `C` module) allows you to declaratively map those channels, transforming the context an agent sees.

## The Problem

```python
pipeline = classifier.outputs("intent") >> booker.instruct("Intent is {intent}")
```
By default, ADK appends the classifier's text to the conversation history. But `booker` *also* injects `{intent}` into its instruction prompt. The LLM sees the data twice, causing prompt pollution.

## The Solution

The `C` module defines exactly what conversation history is passed into the agent.

```python
from adk_fluent import C

booker.context(C.user_only())
```

### Core Primitives

| Transform | Description |
|---|---|
| `C.default()` | Full conversation history (ADK default) |
| `C.none()` | No conversation history; context purely from state/instruction |
| `C.user_only()` | Only user messages (strips intermediate agent text) |
| `C.from_agents("a", "b")` | Include outputs from named agents + user |
| `C.exclude_agents("a")` | Full history minus named agents |
| `C.window(n=5)` | The last N turns |
| `C.from_state("key")` | Read context directly from state keys |
| `C.capture("key")` | Bridge user messages into session state |

### Usage

```python
pipeline = (
    C.capture("user_msg")
    >> Agent("classifier").outputs("intent")
    >> Route("intent").eq("booking",
        Agent("booker")
            .instruct("Help book: {user_msg}. Found intent: {intent}")
            .context(C.none())
    )
)
```
In this pipeline, `booker` takes `C.none()` because it is injected perfectly with state data.
MD_EOF

cat << 'MD_EOF' > $WIKI_DIR/Codegen-Pipeline.md
# The Codegen Pipeline

`adk-fluent` wraps ADK dynamically. Google ADK has 130+ different types of agents and builders, many with complex nested signatures. Hand-writing wrappers for each would lead to constant maintenance debt.

## How it works

The pipeline consists of three core Python scripts executed via `just`:

1. **`just scan` (`scripts/scanner.py`)**: 
   Inspects the installed `google-adk` package via reflection, extracts all Pydantic models, their fields, types, and defaults, and dumps the exact ground-truth to `manifest.json`.
2. **`just seed` (`scripts/seed_generator.py`)**:
   Reads `manifest.json` and creates a `seed.toml` file. This lets humans inject documentation aliases and overrides, blending human logic with machine truth.
3. **`just generate` (`scripts/generator.py`)**:
   Consumes `seed.toml` and `manifest.json` to write out completely type-safe `.py` runtime classes and `.pyi` stubs to `src/adk_fluent/`. It also generates unit test scaffolds automatically.

## Pipeline Architecture

```mermaid
graph TD
    A[installed google-adk] -->|scanner.py| B(manifest.json)
    B -->|seed_generator.py| C(seed.toml)
    D[seed.manual.toml] -->|merge| C
    B -->|generator.py| E[src/adk_fluent/*.py]
    C -->|generator.py| E
    B -->|generator.py| F[src/adk_fluent/*.pyi]
    C -->|generator.py| F
    B -->|generator.py| G[tests/generated/*.py]
```

## Running the Pipeline

If you update the codegen logic, re-run the pipeline to see your changes:

```bash
just generate
just typecheck
```

*Note: All generated files are `0o444` (read-only) to protect you from the "Codegen Trap" (where you accidentally edit a generated file and lose your work).*
MD_EOF

cat << 'MD_EOF' > $WIKI_DIR/Contributor-Guide.md
# Contributor Guide

Welcome to the `adk-fluent` contributor guide! 

This repository relies heavily on code generation. If you're looking to modify the fluent API or add support for new ADK agents, you need to understand our generation pipeline. 

## The Golden Rule: The Codegen Trap
**Never manually edit files in `src/adk_fluent/` or `tests/generated/`.**
These files are completely erased and rewritten every time `just generate` is run.

To protect you from losing your work, the build script makes all generated files **read-only** (`chmod 0o444`). If your editor refuses to save your changes to `agent.py`, that means the system is working.

## Adding a New Builder
If a new agent type is added to `google-adk`, here is how you expose it in the fluent API:

1. **Scan the new ADK version**:
   Ensure your local virtual environment has the latest `google-adk` version installed.
   Run: `just scan`
   *This updates `manifest.json` with the new Pydantic schema.*

2. **Add it to the Seed File**:
   Open `seeds/seed.manual.toml`. Add a configuration block for the new builder.
   ```toml
   [builders.NewAgent]
   source_class = "google.adk.agents.NewAgent"
   output_module = "new_agent"
   doc = "Fluent builder for the new ADK agent."
   
   [builders.NewAgent.aliases]
   config = "configuration_model"
   ```

3. **Generate**:
   Run `just generate`.
   The script will merge your manual seed with the manifest, emit `src/adk_fluent/new_agent.py`, create type stubs, and scaffold tests.

4. **Verify**:
   Run `just test` to verify the generated test scaffold passes.

## Adding a "Hand-Written" Feature
If you need to add custom logic that isn't a direct 1:1 mapping to a Pydantic model (like the `C` module or the `S` module), you edit the `_` prefixed files in `src/adk_fluent/`.

* `src/adk_fluent/_base.py`: The `BuilderBase` class and workflow primitives.
* `src/adk_fluent/_transforms.py`: The `S` module.
* `src/adk_fluent/_context.py`: The `C` module.
* `src/adk_fluent/_visibility.py`: Event visibility inference.

These files are **not** overwritten by the generator. They are safe to edit.

MD_EOF

cat << 'MD_EOF' > $WIKI_DIR/Cookbook-Directory.md
# Cookbook Directory

The fastest way to learn `adk-fluent` is to read the cookbook examples. We maintain over 50 executable examples showing side-by-side comparisons of the native ADK API versus the Fluent API.

These are all executed and validated in CI.

👉 **[View all 50+ Cookbooks in the Repository](https://github.com/vamsiramakrishnan/adk-fluent/tree/master/examples/cookbook)**

## Highlighted Recipes
* `01_simple_agent.py` — The absolute basics.
* `04_sequential_pipeline.py` — How to use the `>>` operator.
* `07_team_coordinator.py` — Routing with a central coordinator agent.
* `33_state_transforms.py` — Demonstrating the `S` module in depth.
* `49_context_engineering.py` — How to use the `C` module to manage what the LLM sees.
* `54_transfer_control.py` — Deep-dive into isolation and human-in-the-loop handoffs.

MD_EOF

# 4. Commit and push from local .wiki
cd $WIKI_DIR
git add .
git commit -m "docs(wiki): fix markdown rendering issues and establish local tracking" || true
git push origin master

echo "✅ Wiki successfully published from local .wiki directory!"
