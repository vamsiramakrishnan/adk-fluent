# Spec: v5.1 Phase B — C Atoms (No LLM)

Implement the atomic context engineering primitives that do not require LLM calls. These primitives operate directly on the conversation history or session state via the `C` module.

## Primitives to Implement

### SELECT Primitives
- **C.select(author=, type=, tag=):** Filter events by metadata.
- **C.recent(decay=, half_life=):** Importance-weighted selection based on recency.

### COMPRESS Primitives
- **C.compact(strategy=):** Structural compaction (e.g., merging sequential tool calls).
- **C.truncate(max_tokens=, strategy=):** Hard limit on turn count or estimated tokens.
- **C.project(fields=):** Keep only specific fields from complex event objects.
- **C.dedup(strategy="exact"|"structural"):** Remove duplicate or redundant events.

### BUDGET Primitives
- **C.budget(max_tokens=, overflow=):** Hard limit on assembled context tokens.
- **C.priority(tier=):** Assign priority to content blocks for budget-aware pruning.
- **C.fit(strategy="strict"):** Aggressive pruning to fit a hard token limit.

### PROTECT Primitives
- **C.fresh(max_age=, stale_action=):** Prune stale context based on timestamp.
- **C.redact(patterns=):** Remove PII or sensitive patterns from context.

### Composition
- Implement the `+` (union) and `|` (pipe) operator rules for all new atoms.
- Ensure proper serialization/rendering of `CComposite` and `CPipe` structures in the IR.

## Architecture
- All primitives must implement the `CTransform` interface in `src/adk_fluent/_context.py`.
- Primitives must compile to an `InstructionProvider` callable.
- The contract checker must be updated to recognize and validate these new atoms.
