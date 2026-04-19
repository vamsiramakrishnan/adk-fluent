# Docs UX Audit — Progressive Disclosure

*Date: 2026-04-18*
*Scope: reader's-first-hour experience — landing page, getting started, user-guide index.*
*Status: audit; candidate fixes listed but not applied.*

## 1. Finding summary

The docs fail progressive disclosure in three places: the landing
page hero opens with six unfamiliar concepts at once, the getting
started page trebles its own "5 minutes" promise, and the user-guide
index duplicates the landing pathways table while hiding a 41-entry
flat toctree below the fold. Each is independently fixable.

## 2. Landing page (`docs/index.md`)

### 2.1 Hero sample overloads the reader (L111-119)

The first code block shown on the homepage is:

```python
pipeline = (
    Agent("classifier", "gemini-2.5-flash").writes("intent")
    | Agent("sentiment", "gemini-2.5-flash").writes("tone")
) >> Agent("responder", "gemini-2.5-flash").instruct(
    "Reply to {intent} with {tone} tone."
).context(C.from_state("intent", "tone"))
```

It uses, in nine visible lines: `|` (parallel), `>>` (sequential),
`.writes()`, `.context()`, `C.from_state()`, and `{intent}` template
interpolation. Three of those six are not introduced anywhere on the
landing page before the reader meets them in code. Result: the
first impression sample is visually dense and not imitable from
memory.

**Candidate fix**: lead with a three-line single-agent sample;
demote the pipeline flex to a "once you're comfortable" section
further down.

### 2.2 Pathways table duplicated (index.md L293-337 ↔ user-guide/index.md L36-64)

The same "Three Pathways" narrative lives on both the landing page
and the user-guide entry page. Readers who click "User Guide" are
shown content they already scrolled past.

**Candidate fix**: keep it on the landing page; replace the
user-guide version with a one-sentence reference back to it.

## 3. Getting started (`docs/getting-started.md`)

### 3.1 "5 minutes" promise, 596-line page

The page title and intro claim a 5-minute tour. Actual length:
596 lines, roughly 6 screens at default furo width.

### 3.2 IDE/typo tangent ahead of the first agent (L56-82)

Before the reader has built a single agent, the page discusses:
editor configuration, environment variables, and typo handling. All
useful, none relevant to the 5-minute path.

**Candidate fix**: move the IDE/env block to a short
"before-you-start" or a side-by-side installation admonition, not
inline prose.

### 3.3 Async warning buried (L491-510)

`ask()` vs `ask_async()` is a tripwire for anyone using FastAPI or
Jupyter. The warning sits at line 491 of 596, i.e. ~82% through the
page. Readers who stop after the first working agent never see it.

**Candidate fix**: surface as a `{warning}` admonition the first
time `.ask()` appears (~L150), not only in the execution section.

## 4. User guide index (`docs/user-guide/index.md`)

### 4.1 Quick-taste sample (L15-33) conflicts with landing

The quick-taste here is longer (8 lines) than the landing hero and
uses a different set of builders. A reader arriving from index.md
experiences style whiplash.

### 4.2 Flat 41-entry toctree (L166-213)

The toctree lists 41 chapters in a single flat block. There is no
grouping by tier (Core / Patterns / Advanced / Reference), which
means the reader has no cue for *reading order*. Chapters like
"A2A remote agents" and "Agent builder methods" sit side-by-side
alphabetically.

**Candidate fix**: split the toctree into 4 `:caption:`-tagged
blocks. Sphinx supports this natively via multiple `toctree`
directives inside a single page.

## 5. Architecture & concepts (`docs/user-guide/architecture-and-concepts.md`)

### 5.1 Opens cold with "The Three Channels" (L6)

The generated concepts page has no introductory paragraph — it
drops the reader straight into the state thesis' H2. Readers
arriving from the toctree have no signpost for what this page
covers or where it sits in the learning path.

**Candidate fix**: Prepend a 2-3 line framing paragraph produced
by `concepts_generator.py` rather than extracted. This is a one-line
change.

### 5.2 Truncation

The file ends mid-sentence in the current generated output because
the second extractor (`| Operation |` table header) breaks on the
first non-pipe line, which can be the table's own trailing blank.
See `docs/plans/2026-04-18-docs-pipeline-audit.md §4.4`.

## 6. Chapter ordering proposal (DAG)

Current: 41 chapters in alphabetical flat order. Proposed tiers,
read-before arrows implied left-to-right:

```
Tier 0  concepts
Tier 1  agent-builder -> operators -> pipelines -> fan-out -> loops
Tier 2  tools -> guards -> middleware -> callbacks
Tier 3  context-engineering -> prompt-composition -> state-transforms
Tier 4  patterns -> routing -> fallback -> map-reduce
Tier 5  memory -> sessions -> artifacts
Tier 6  harness (hooks, permissions, plan-mode, reactor, subagents)
Tier 7  a2a remote, deployment, observability
Tier R  reference (builders index, namespaces index, cookbook)
```

A reader who completes Tier 1 can build any linear or parallel
workflow. Tier 2 adds safety rails. Tier 3 adds fine control. Tier
4+ is specialist material.

## 7. Recommendation

Candidates in this memo are all safe-envelope edits — they do not
change any generator's byte output. The structural change (splitting
the toctree) is one edit to `user-guide/index.md`. The concepts-page
framing paragraph is one edit to `concepts_generator.py`. Both can
ship under the Phase 2 banner alongside the validator work.
