"""Prompt composition module — declarative, composable prompt building blocks.

The P class is the public API namespace. Each static method returns a
frozen dataclass (PTransform subclass) describing a prompt section or
transform. At build-time, ``_compile_prompt_spec`` lowers these descriptors
into instruction strings or async InstructionProvider callables.

Composition operators:
    +  union  (PComposite) — merge sections
    |  pipe   (PPipe)      — post-process compiled output

Usage:
    from adk_fluent import P

    Agent("writer")
        .instruct(
            P.role("You are a senior code reviewer.")
            + P.task("Review the code for bugs.")
            + P.constraint("Be concise. Max 5 bullet points.")
            + P.format("Return markdown with ## sections.")
            + P.example(input="x=eval(input())", output="Critical: eval() on user input")
        )

    # Reuse base prompt across agents
    base = P.role("Senior engineer.") + P.constraint("Be precise.")
    reviewer = Agent("r").instruct(base + P.task("Review code."))
    writer   = Agent("w").instruct(base + P.task("Write docs."))
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

_DEFAULT_MODEL = "gemini-2.5-flash"
_log = logging.getLogger(__name__)

__all__ = [
    "P",
    "PTransform",
    "PComposite",
    "PPipe",
    "PRole",
    "PContext",
    "PTask",
    "PConstraint",
    "PFormat",
    "PExample",
    "PSection",
    # Phase B: Conditional & Dynamic
    "PWhen",
    "PFromState",
    "PTemplate",
    # Phase C: Structural Transforms
    "PReorder",
    "POnly",
    "PWithout",
    # Phase D: LLM-Powered Transforms
    "PCompress",
    "PAdapt",
    # Phase E: Sugar
    "PScaffolded",
    "PVersioned",
    "_compile_prompt_spec",
]


# ======================================================================
# Section ordering and labels
# ======================================================================

_SECTION_ORDER = ("role", "context", "task", "constraint", "format", "example")

_SECTION_LABELS: dict[str, str | None] = {
    "role": None,  # Role text stands alone (no header)
    "context": "Context",
    "task": "Task",
    "constraint": "Constraints",
    "format": "Output Format",
    "example": "Examples",
    "ui_schema": "UI Schema",
}

_SECTION_ORDER_MAP: dict[str, int] = {k: i * 100 + 100 for i, k in enumerate(_SECTION_ORDER)}
# role=100, context=200, task=300, constraint=400, format=500, example=600
_SECTION_ORDER_MAP["ui_schema"] = 250  # Between context (200) and task (300)


# ======================================================================
# Base transform type
# ======================================================================


@dataclass(frozen=True)
class PTransform:
    """Base prompt transform descriptor.

    Every P.xxx() factory returns a frozen PTransform (or subclass).
    The ``_kind`` field discriminates types for IR/serialization.

    At build-time, ``_compile_prompt_spec`` lowers these descriptors
    into instruction strings or async InstructionProvider callables.
    """

    _kind: str = "base"

    def __add__(self, other: PTransform) -> PComposite:
        """Union: combine two transforms via +."""
        return PComposite(blocks=(*self._as_list(), *other._as_list()))

    def __or__(self, other: PTransform) -> PPipe:
        """Pipe: source | transform."""
        return PPipe(source=self, transform=other)

    def _as_list(self) -> tuple[PTransform, ...]:
        """Flatten for composite building. Overridden by PComposite."""
        return (self,)

    # ------------------------------------------------------------------
    # NamespaceSpec protocol: key metadata for contract tracing
    # ------------------------------------------------------------------

    @property
    def _reads_keys(self) -> frozenset[str] | None:
        """State keys this prompt spec reads. Subclasses override."""
        return frozenset()  # static prompts read nothing

    @property
    def _writes_keys(self) -> frozenset[str] | None:
        """Prompt transforms never write state."""
        return frozenset()

    def build(self, state: dict[str, Any] | None = None) -> str:
        """Compile to instruction string, optionally resolving state variables."""
        return _compile_prompt_spec_static(self, state or {})

    def __str__(self) -> str:
        """String conversion — allows direct use in .instruct(prompt)."""
        return self.build()

    def __repr__(self) -> str:
        return f"{type(self).__name__}(_kind={self._kind!r})"

    def fingerprint(self) -> str:
        """SHA-256 hash of this transform's content for caching/versioning."""
        return _fingerprint(self)


# ======================================================================
# Composition types
# ======================================================================


@dataclass(frozen=True)
class PComposite(PTransform):
    """Union of multiple prompt blocks (via + operator).

    Sections within a composite are sorted by their ordering key at build time.
    Multiple sections of the same kind merge their content.
    """

    blocks: tuple[PTransform, ...] = ()
    _kind: str = "composite"

    def _as_list(self) -> tuple[PTransform, ...]:
        return self.blocks

    def __repr__(self) -> str:
        kinds = [b._kind for b in self.blocks]
        return f"PComposite({', '.join(kinds)})"


@dataclass(frozen=True)
class PPipe(PTransform):
    """Pipe transform: source feeds into transform (via | operator).

    The source is compiled first, then the transform processes the output.
    """

    source: PTransform | None = None
    transform: PTransform | None = None
    _kind: str = "pipe"

    def __repr__(self) -> str:
        src = self.source._kind if self.source else "None"
        trn = self.transform._kind if self.transform else "None"
        return f"PPipe({src} | {trn})"


# ======================================================================
# Phase A: Core section types
# ======================================================================


@dataclass(frozen=True)
class PRole(PTransform):
    """Role/persona definition. Rendered without a section header."""

    content: str = ""
    _kind: str = "role"

    def __repr__(self) -> str:
        return f"PRole({self.content[:40]!r})"


@dataclass(frozen=True)
class PContext(PTransform):
    """Background context section."""

    content: str = ""
    _kind: str = "context"

    def __repr__(self) -> str:
        return f"PContext({self.content[:40]!r})"


@dataclass(frozen=True)
class PTask(PTransform):
    """Primary task/objective section."""

    content: str = ""
    _kind: str = "task"

    def __repr__(self) -> str:
        return f"PTask({self.content[:40]!r})"


@dataclass(frozen=True)
class PConstraint(PTransform):
    """Rule/constraint section. Multiple constraints merge into one section."""

    content: str = ""
    _kind: str = "constraint"

    def __repr__(self) -> str:
        return f"PConstraint({self.content[:40]!r})"


@dataclass(frozen=True)
class PFormat(PTransform):
    """Output format specification section."""

    content: str = ""
    _kind: str = "format"

    def __repr__(self) -> str:
        return f"PFormat({self.content[:40]!r})"


@dataclass(frozen=True)
class PExample(PTransform):
    """Few-shot example section. Supports freeform text or structured input/output.

    Structured examples render as:
        Input: <input_text>
        Output: <output_text>

    Freeform examples render the content directly.
    """

    content: str = ""
    input_text: str = ""
    output_text: str = ""
    _kind: str = "example"

    def _rendered_content(self) -> str:
        """Get the rendered content for this example."""
        if self.input_text or self.output_text:
            parts = []
            if self.input_text:
                parts.append(f"Input: {self.input_text}")
            if self.output_text:
                parts.append(f"Output: {self.output_text}")
            return "\n".join(parts)
        return self.content

    def __repr__(self) -> str:
        if self.input_text or self.output_text:
            return f"PExample(input={self.input_text[:20]!r}, output={self.output_text[:20]!r})"
        return f"PExample({self.content[:40]!r})"


@dataclass(frozen=True)
class PSection(PTransform):
    """Custom named section."""

    name: str = ""
    content: str = ""
    _kind: str = "section"

    def __repr__(self) -> str:
        return f"PSection({self.name!r}, {self.content[:30]!r})"


# ======================================================================
# Phase B: Conditional & Dynamic
# ======================================================================


@dataclass(frozen=True)
class PWhen(PTransform):
    """Conditional section inclusion.

    Include the wrapped block only if the predicate evaluates to truthy
    at runtime. When ``predicate`` is a string, it is treated as a
    state key check: include when ``state[key]`` is truthy.
    """

    predicate: Any = None  # Callable[[dict], bool] or str (state key)
    block: PTransform | None = None
    _kind: str = "when"

    def __repr__(self) -> str:
        pred = self.predicate if isinstance(self.predicate, str) else "callable"
        blk = self.block._kind if self.block else "None"
        return f"PWhen({pred!r}, {blk})"


@dataclass(frozen=True)
class PFromState(PTransform):
    """Read named keys from session state and format as context sections.

    Each key produces a line: ``key: value``
    """

    keys: tuple[str, ...] = ()
    _kind: str = "from_state"

    @property
    def _reads_keys(self) -> frozenset[str]:
        return frozenset(self.keys)

    def __repr__(self) -> str:
        return f"PFromState({', '.join(self.keys)})"


@dataclass(frozen=True)
class PTemplate(PTransform):
    """Template string with {key}, {key?}, and {ns:key} placeholders.

    Variables are extracted at creation time for validation.
    At build time, placeholders are resolved from the provided state dict.
    Optional variables ({key?}) resolve to empty string if missing.
    """

    template: str = ""
    _kind: str = "template"

    @property
    def _reads_keys(self) -> frozenset[str]:
        return frozenset(re.findall(r"\{(\w+)\??}", self.template))

    def __repr__(self) -> str:
        return f"PTemplate({self.template[:40]!r})"


# ======================================================================
# Phase C: Structural Transforms (applied via | pipe)
# ======================================================================


@dataclass(frozen=True)
class PReorder(PTransform):
    """Override default section ordering.

    Named sections appear in the specified order. Unmentioned sections
    appear after the specified ones in their default order.
    """

    order: tuple[str, ...] = ()
    _kind: str = "reorder"

    def __repr__(self) -> str:
        return f"PReorder({', '.join(self.order)})"


@dataclass(frozen=True)
class POnly(PTransform):
    """Keep only the named sections (projection). Remove all others."""

    names: tuple[str, ...] = ()
    _kind: str = "only"

    def __repr__(self) -> str:
        return f"POnly({', '.join(self.names)})"


@dataclass(frozen=True)
class PWithout(PTransform):
    """Remove the named sections. Keep all others."""

    names: tuple[str, ...] = ()
    _kind: str = "without"

    def __repr__(self) -> str:
        return f"PWithout({', '.join(self.names)})"


# ======================================================================
# Phase D: LLM-Powered Transforms (applied via | pipe)
# ======================================================================


@dataclass(frozen=True)
class PCompress(PTransform):
    """LLM-powered prompt compression.

    Reduces token count while preserving semantic meaning and structure.
    Caches results via SHA-256 fingerprinting.
    """

    max_tokens: int = 500
    model: str = _DEFAULT_MODEL
    _kind: str = "compress"

    def __repr__(self) -> str:
        return f"PCompress(max_tokens={self.max_tokens})"


@dataclass(frozen=True)
class PAdapt(PTransform):
    """LLM-powered audience adaptation.

    Adjusts tone, complexity, and terminology for the target audience.
    """

    audience: str = "general"
    model: str = _DEFAULT_MODEL
    _kind: str = "adapt"

    def __repr__(self) -> str:
        return f"PAdapt(audience={self.audience!r})"


# ======================================================================
# Phase E: Sugar / Convenience
# ======================================================================


@dataclass(frozen=True)
class PScaffolded(PTransform):
    """Defensive prompt scaffolding.

    Wraps a prompt block in safety guardrails: a preamble that establishes
    boundaries and a postamble that reinforces constraints.
    """

    block: PTransform | None = None
    preamble: str = "You must follow these instructions carefully. Do not deviate from the specified task."
    postamble: str = "Remember: stay on topic, be accurate, and follow all constraints above."
    _kind: str = "scaffolded"

    def __repr__(self) -> str:
        blk = self.block._kind if self.block else "None"
        return f"PScaffolded({blk})"


@dataclass(frozen=True)
class PVersioned(PTransform):
    """Versioned prompt with tag and fingerprint metadata.

    The block is the actual prompt content. The tag and computed fingerprint
    enable version tracking and comparison without a central registry.
    """

    block: PTransform | None = None
    tag: str = ""
    _kind: str = "versioned"

    def __repr__(self) -> str:
        blk = self.block._kind if self.block else "None"
        fp = _fingerprint(self.block) if self.block else "empty"
        return f"PVersioned(tag={self.tag!r}, fp={fp[:8]}, {blk})"


# ======================================================================
# P namespace — public API
# ======================================================================


class P:
    """Prompt composition namespace. Each method returns a frozen PTransform.

    Usage:
        Agent("writer").instruct(
            P.role("You are a senior code reviewer.")
            + P.task("Review the code for bugs.")
            + P.constraint("Be concise. Max 5 bullet points.")
            + P.format("Return markdown with ## sections.")
        )
    """

    # --- Phase A: Core sections ---

    @staticmethod
    def role(text: str) -> PRole:
        """Define the agent's role/persona. Rendered without a section header."""
        return PRole(content=text)

    @staticmethod
    def context(text: str) -> PContext:
        """Add background context the agent should know."""
        return PContext(content=text)

    @staticmethod
    def task(text: str) -> PTask:
        """Define the primary task or objective."""
        return PTask(content=text)

    @staticmethod
    def constraint(*rules: str) -> PTransform:
        """Add constraint(s). Multiple args create multiple constraint blocks that merge."""
        if len(rules) == 1:
            return PConstraint(content=rules[0])
        # Multiple rules: compose as PComposite of PConstraints
        blocks = tuple(PConstraint(content=r) for r in rules)
        return PComposite(blocks=blocks)

    @staticmethod
    def format(text: str) -> PFormat:
        """Specify the desired output format."""
        return PFormat(content=text)

    @staticmethod
    def example(text: str = "", *, input: str = "", output: str = "") -> PExample:
        """Add a few-shot example.

        Freeform:  P.example("Input: x=1 | Output: valid")
        Structured: P.example(input="x=eval(y)", output="Critical: injection")
        """
        return PExample(content=text, input_text=input, output_text=output)

    @staticmethod
    def section(name: str, text: str) -> PSection:
        """Add a custom named section."""
        return PSection(name=name, content=text)

    # --- Phase B: Conditional & Dynamic ---

    @staticmethod
    def when(predicate: Callable | str, block: PTransform) -> PWhen:
        """Include block only if predicate is truthy at runtime.

        String predicate is a shortcut for state key check:
            P.when("verbose", P.context("..."))  # include if state["verbose"] truthy
        """
        return PWhen(predicate=predicate, block=block)

    @staticmethod
    def from_state(*keys: str) -> PFromState:
        """Read named keys from session state and format as context."""
        return PFromState(keys=keys)

    @staticmethod
    def template(text: str) -> PTemplate:
        """Template with {key}, {key?}, and {ns:key} placeholders.

        Resolved from session state at runtime. Optional vars ({key?})
        produce empty string if missing.
        """
        return PTemplate(template=text)

    # --- Phase C: Structural Transforms ---

    @staticmethod
    def reorder(*section_names: str) -> PReorder:
        """Override default section ordering. Unmentioned sections appear after."""
        return PReorder(order=section_names)

    @staticmethod
    def only(*section_names: str) -> POnly:
        """Keep only the named sections. Remove all others."""
        return POnly(names=section_names)

    @staticmethod
    def without(*section_names: str) -> PWithout:
        """Remove the named sections. Keep all others."""
        return PWithout(names=section_names)

    # --- Phase D: LLM-Powered Transforms ---

    @staticmethod
    def compress(*, max_tokens: int = 500, model: str = _DEFAULT_MODEL) -> PCompress:
        """LLM-compress the prompt to reduce token count."""
        return PCompress(max_tokens=max_tokens, model=model)

    @staticmethod
    def adapt(*, audience: str = "general", model: str = _DEFAULT_MODEL) -> PAdapt:
        """Adapt the prompt's tone and complexity for a target audience."""
        return PAdapt(audience=audience, model=model)

    # --- Phase E: Sugar ---

    @staticmethod
    def scaffolded(
        block: PTransform,
        *,
        preamble: str = "You must follow these instructions carefully. Do not deviate from the specified task.",
        postamble: str = "Remember: stay on topic, be accurate, and follow all constraints above.",
    ) -> PScaffolded:
        """Wrap a prompt in defensive scaffolding (safety preamble + postamble)."""
        return PScaffolded(block=block, preamble=preamble, postamble=postamble)

    @staticmethod
    def versioned(block: PTransform, *, tag: str = "") -> PVersioned:
        """Attach version metadata + fingerprint to a prompt."""
        return PVersioned(block=block, tag=tag)

    @staticmethod
    def ui_schema(*, catalog: str = "basic", examples: bool = True) -> PSection:
        """Inject A2UI schema and catalog documentation as a prompt section.

        Use with ``.instruct()`` to give the LLM knowledge of the A2UI protocol::

            agent.instruct(P.role("UI Designer") + P.ui_schema() + P.task("Build a dashboard"))

        Args:
            catalog: Catalog to document (default ``"basic"``).
            examples: Include usage examples in the prompt.
        """
        from adk_fluent._ui_compile import generate_ui_prompt_section

        text = generate_ui_prompt_section(catalog=catalog)
        return PSection(name="ui_schema", content=text)


# ======================================================================
# Fingerprinting
# ======================================================================


def _fingerprint(spec: PTransform | None) -> str:
    """Compute a stable SHA-256 fingerprint of a PTransform tree.

    Used for caching LLM transform results and prompt version comparison.
    """
    if spec is None:
        return hashlib.sha256(b"none").hexdigest()[:12]

    h = hashlib.sha256()
    h.update(spec._kind.encode())

    if isinstance(spec, PComposite):
        for block in spec.blocks:
            h.update(_fingerprint(block).encode())
    elif isinstance(spec, PPipe):
        h.update(_fingerprint(spec.source).encode())
        h.update(_fingerprint(spec.transform).encode())
    elif isinstance(spec, PExample):
        h.update(spec.content.encode())
        h.update(spec.input_text.encode())
        h.update(spec.output_text.encode())
    elif isinstance(spec, PSection):
        h.update(spec.name.encode())
        h.update(spec.content.encode())
    elif isinstance(spec, PWhen):
        # Predicate may be a lambda — hash the block, not the predicate
        h.update(_fingerprint(spec.block).encode())
        if isinstance(spec.predicate, str):
            h.update(spec.predicate.encode())
    elif isinstance(spec, PFromState):
        for key in spec.keys:
            h.update(key.encode())
    elif isinstance(spec, PTemplate):
        h.update(spec.template.encode())
    elif isinstance(spec, PScaffolded):
        h.update(spec.preamble.encode())
        h.update(spec.postamble.encode())
        h.update(_fingerprint(spec.block).encode())
    elif isinstance(spec, PVersioned):
        h.update(spec.tag.encode())
        h.update(_fingerprint(spec.block).encode())
    elif isinstance(spec, PReorder | POnly | PWithout):
        names = getattr(spec, "order", None) or getattr(spec, "names", ())
        for n in names:
            h.update(n.encode())
    elif isinstance(spec, PCompress):
        h.update(str(spec.max_tokens).encode())
        h.update(spec.model.encode())
    elif isinstance(spec, PAdapt):
        h.update(spec.audience.encode())
        h.update(spec.model.encode())
    else:
        # Generic: hash content if present
        content = getattr(spec, "content", "")
        if content:
            h.update(content.encode())

    return h.hexdigest()[:12]


# ======================================================================
# Template variable extraction
# ======================================================================

# Matches {key}, {key?}, {ns:key}, {ns:key?}
_VAR_PATTERN = re.compile(r"\{(\w+(?::\w+)?)\??\}")
# Matches optional vars specifically: {key?}
_OPTIONAL_VAR_PATTERN = re.compile(r"\{(\w+(?::\w+)?)\?\}")


def _extract_template_vars(text: str) -> tuple[frozenset[str], frozenset[str]]:
    """Extract required and optional variable names from a template string.

    Returns (required_vars, optional_vars).
    """
    all_vars = set(_VAR_PATTERN.findall(text))
    optional_vars = set(_OPTIONAL_VAR_PATTERN.findall(text))
    required_vars = all_vars - optional_vars
    return frozenset(required_vars), frozenset(optional_vars)


def _resolve_template(text: str, state: dict[str, Any]) -> str:
    """Resolve {key}, {key?}, and {ns:key} placeholders from state.

    - Required vars ({key}): pass through if not in state (for ADK runtime resolution)
    - Optional vars ({key?}): resolve to empty string if missing
    """

    def _replace(match: re.Match) -> str:
        full = match.group(0)
        key = match.group(1)
        is_optional = full.endswith("?}")

        # Try direct lookup
        value = state.get(key)

        # Try namespaced lookup (ns:key -> state["ns:key"] or state[key])
        if value is None and ":" in key:
            value = state.get(key)

        if value is not None:
            return str(value)
        if is_optional:
            return ""
        # Pass through for ADK runtime resolution
        return full

    return re.sub(r"\{(\w+(?::\w+)?)\??\}", _replace, text)


# ======================================================================
# Static compilation — _compile_prompt_spec_static
# ======================================================================


def _get_section_kind(spec: PTransform) -> str:
    """Get the section kind for ordering/grouping."""
    if isinstance(spec, PSection):
        return spec.name
    return spec._kind


def _get_section_order(kind: str) -> int:
    """Get the sort order for a section kind."""
    return _SECTION_ORDER_MAP.get(kind, 700)


def _get_section_label(kind: str) -> str | None:
    """Get the display label for a section kind. None means no header."""
    if kind in _SECTION_LABELS:
        return _SECTION_LABELS[kind]
    return kind.replace("_", " ").title()


def _get_section_content(spec: PTransform) -> str:
    """Extract the text content from a section spec."""
    if isinstance(spec, PExample):
        return spec._rendered_content()
    return getattr(spec, "content", "")


def _flatten_blocks(spec: PTransform) -> list[PTransform]:
    """Recursively flatten a PTransform tree into a list of leaf sections."""
    if isinstance(spec, PComposite):
        result: list[PTransform] = []
        for block in spec.blocks:
            result.extend(_flatten_blocks(block))
        return result
    if isinstance(spec, PPipe):
        # Pipe is handled separately during compilation
        return [spec]
    return [spec]


def _compile_prompt_spec_static(spec: PTransform, state: dict[str, Any]) -> str:
    """Compile a PTransform tree into an instruction string (static path).

    This handles the fully-resolvable case. For dynamic specs (PWhen, PFromState, etc.),
    _compile_prompt_spec returns an async InstructionProvider instead.
    """
    if isinstance(spec, PPipe):
        return _compile_pipe_static(spec, state)

    blocks = _flatten_blocks(spec)

    # Separate structural transforms from content sections
    structural: list[PTransform] = []
    content_blocks: list[PTransform] = []

    for block in blocks:
        if isinstance(block, PReorder | POnly | PWithout):
            structural.append(block)
        elif isinstance(block, PPipe):
            # Compile pipe inline
            compiled_text = _compile_pipe_static(block, state)
            if compiled_text:
                content_blocks.append(PSection(name="_pipe_result", content=compiled_text))
        else:
            content_blocks.append(block)

    # Resolve conditional sections
    resolved: list[PTransform] = []
    for block in content_blocks:
        if isinstance(block, PWhen):
            if _evaluate_predicate(block.predicate, state) and block.block is not None:
                resolved.extend(_flatten_blocks(block.block))
        elif isinstance(block, PFromState):
            text = _resolve_from_state(block.keys, state)
            if text:
                resolved.append(PContext(content=text))
        elif isinstance(block, PTemplate):
            text = _resolve_template(block.template, state)
            if text:
                resolved.append(PSection(name="_template", content=text))
        elif isinstance(block, PScaffolded):
            if block.block is not None:
                inner = _compile_prompt_spec_static(block.block, state)
                scaffolded_text = f"{block.preamble}\n\n{inner}\n\n{block.postamble}"
                resolved.append(PSection(name="_scaffolded", content=scaffolded_text))
        elif isinstance(block, PVersioned):
            if block.block is not None:
                resolved.extend(_flatten_blocks(block.block))
        else:
            resolved.append(block)

    # Group sections by kind and merge content
    groups: dict[str, list[str]] = {}
    for block in resolved:
        kind = _get_section_kind(block)
        content = _get_section_content(block)
        if content:
            groups.setdefault(kind, []).append(content)

    # Apply structural transforms
    for transform in structural:
        groups = _apply_structural_transform(transform, groups)

    # Build output in order
    return _render_sections(groups)


def _compile_pipe_static(pipe: PPipe, state: dict[str, Any]) -> str:
    """Compile a PPipe: source → transform."""
    if pipe.source is None:
        return ""

    source_text = _compile_prompt_spec_static(pipe.source, state)

    if pipe.transform is None:
        return source_text

    # LLM-powered transforms need async execution — in static mode, return source
    if isinstance(pipe.transform, PCompress | PAdapt):
        _log.warning(
            "LLM-powered transform %s requires async execution; "
            "returning unprocessed text in static build(). "
            "Use with Agent.instruct() for async resolution.",
            pipe.transform._kind,
        )
        return source_text

    # Structural transforms applied to compiled text
    if isinstance(pipe.transform, PReorder | POnly | PWithout):
        # Re-parse? No — structural transforms work on section groups, not compiled text.
        # In pipe mode, we just return the source text since it's already compiled.
        return source_text

    return source_text


from adk_fluent._predicate_utils import evaluate_predicate as _evaluate_predicate  # noqa: E402


def _resolve_from_state(keys: tuple[str, ...], state: dict[str, Any]) -> str:
    """Format state values as context lines."""
    lines = []
    for key in keys:
        value = state.get(key)
        if value is not None:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def _apply_structural_transform(transform: PTransform, groups: dict[str, list[str]]) -> dict[str, list[str]]:
    """Apply a structural transform to section groups."""
    if isinstance(transform, POnly):
        return {k: v for k, v in groups.items() if k in transform.names}
    if isinstance(transform, PWithout):
        return {k: v for k, v in groups.items() if k not in transform.names}
    # PReorder doesn't filter, only changes order — handled in _render_sections
    return groups


def _render_sections(groups: dict[str, list[str]], reorder: PReorder | None = None) -> str:
    """Render grouped sections into a final instruction string."""
    if not groups:
        return ""

    # Determine section ordering
    if reorder:
        # Custom order: specified sections first, then remaining in default order
        ordered_kinds = list(reorder.order)
        remaining = sorted(
            (k for k in groups if k not in reorder.order),
            key=lambda k: _get_section_order(k),
        )
        ordered_kinds.extend(remaining)
    else:
        # Default order
        ordered_kinds = sorted(groups.keys(), key=lambda k: _get_section_order(k))

    parts: list[str] = []
    for kind in ordered_kinds:
        items = groups.get(kind)
        if not items:
            continue

        label = _get_section_label(kind)
        body = "\n".join(items)

        if label is None:
            # Role: no header
            parts.append(body)
        elif kind.startswith("_"):
            # Internal sections (template, pipe_result, scaffolded): no header
            parts.append(body)
        else:
            parts.append(f"{label}:\n{body}")

    return "\n\n".join(parts)


# ======================================================================
# Dynamic compilation — _compile_prompt_spec
# ======================================================================


def _has_dynamic_blocks(spec: PTransform) -> bool:
    """Check if a PTransform tree contains dynamic (state-dependent) blocks."""
    if isinstance(spec, PWhen | PFromState | PTemplate):
        return True
    if isinstance(spec, PComposite):
        return any(_has_dynamic_blocks(b) for b in spec.blocks)
    if isinstance(spec, PPipe):
        has_source = _has_dynamic_blocks(spec.source) if spec.source else False
        has_transform = _has_dynamic_blocks(spec.transform) if spec.transform else False
        # LLM transforms are also dynamic
        if isinstance(spec.transform, PCompress | PAdapt):
            return True
        return has_source or has_transform
    if isinstance(spec, PScaffolded) and spec.block:
        return _has_dynamic_blocks(spec.block)
    if isinstance(spec, PVersioned) and spec.block:
        return _has_dynamic_blocks(spec.block)
    return False


def _has_llm_transforms(spec: PTransform) -> bool:
    """Check if a PTransform tree contains LLM-powered transforms."""
    if isinstance(spec, PCompress | PAdapt):
        return True
    if isinstance(spec, PComposite):
        return any(_has_llm_transforms(b) for b in spec.blocks)
    if isinstance(spec, PPipe):
        s = _has_llm_transforms(spec.source) if spec.source else False
        t = _has_llm_transforms(spec.transform) if spec.transform else False
        return s or t
    return False


# Fingerprint-keyed cache for static prompt compilation.
# Avoids recompiling identical specs across multiple agents that share prompts.
_static_compile_cache: dict[str, str] = {}


def _compile_prompt_spec(
    prompt_spec: PTransform,
    existing_instruction: str | Callable | None = None,
) -> str | Callable:
    """Lower a PTransform descriptor to an ADK-compatible instruction.

    Returns either:
    - str: if the prompt is fully static (no PWhen, PFromState, PTemplate, LLM transforms)
    - async Callable: if the prompt contains dynamic or LLM-powered elements

    When an existing_instruction is provided and the prompt_spec is static,
    the prompt_spec result replaces the existing instruction. When dynamic,
    the provider chains them.
    """
    if not _has_dynamic_blocks(prompt_spec) and not _has_llm_transforms(prompt_spec):
        # Static path: check fingerprint cache before recompiling
        fp = _fingerprint(prompt_spec)
        cached = _static_compile_cache.get(fp)
        if cached is not None:
            return cached
        result = _compile_prompt_spec_static(prompt_spec, {})
        _static_compile_cache[fp] = result
        return result

    # Dynamic path: return an async InstructionProvider
    spec = prompt_spec

    async def _prompt_provider(ctx: Any) -> str:
        """Async instruction provider for dynamic P transforms."""
        # Extract state from context
        state: dict[str, Any] = {}
        if hasattr(ctx, "state"):
            raw_state = ctx.state
            if isinstance(raw_state, dict):
                state = raw_state
            elif hasattr(raw_state, "to_dict"):
                state = raw_state.to_dict()
            elif hasattr(raw_state, "items"):
                state = dict(raw_state.items())

        # Compile with state
        blocks = _flatten_blocks(spec)

        # Handle pipe with LLM transforms
        if isinstance(spec, PPipe):
            return await _compile_pipe_async(spec, state, ctx)

        result = _compile_prompt_spec_static(spec, state)

        # Process any nested pipes with LLM transforms
        for block in blocks:
            if isinstance(block, PPipe) and isinstance(block.transform, PCompress | PAdapt):
                result = await _compile_pipe_async(
                    PPipe(source=PSection(name="_compiled", content=result), transform=block.transform),
                    state,
                    ctx,
                )

        return result

    _prompt_provider.__name__ = f"prompt_provider_{spec._kind}"
    return _prompt_provider


# ======================================================================
# Async compilation helpers
# ======================================================================

_genai_client = None


def _get_genai_client():
    """Lazy-initialize the Google GenAI client."""
    global _genai_client
    if _genai_client is None:
        try:
            from google import genai

            _genai_client = genai.Client()
        except ImportError:
            _log.warning("google-genai not available; LLM transforms will be skipped")
            return None
        except Exception as e:
            _log.warning("Failed to initialize GenAI client: %s", e)
            return None
    return _genai_client


async def _compile_pipe_async(pipe: PPipe, state: dict[str, Any], ctx: Any) -> str:
    """Compile a PPipe with async LLM transforms."""
    source_text = _compile_prompt_spec_static(pipe.source, state) if pipe.source else ""

    if pipe.transform is None:
        return source_text

    if isinstance(pipe.transform, PCompress):
        return await _llm_compress(source_text, pipe.transform, state)
    if isinstance(pipe.transform, PAdapt):
        return await _llm_adapt(source_text, pipe.transform, state)

    return source_text


async def _llm_compress(text: str, spec: PCompress, state: dict[str, Any]) -> str:
    """LLM-compress prompt text. Caches results via fingerprint."""
    cache_key = f"temp:_prompt_compress_{hashlib.sha256(text.encode()).hexdigest()[:12]}"
    cached = state.get(cache_key)
    if cached:
        return str(cached)

    client = _get_genai_client()
    if client is None:
        _log.warning("GenAI client not available; skipping compression")
        return text

    try:
        prompt = (
            f"Compress the following instruction text to approximately {spec.max_tokens} tokens "
            f"while preserving all semantic meaning, structure, and key details. "
            f"Return ONLY the compressed text, nothing else.\n\n{text}"
        )
        response = client.models.generate_content(model=spec.model, contents=prompt)
        result = response.text.strip() if response.text else text
        state[cache_key] = result
        return result
    except Exception as e:
        _log.warning("LLM compression failed: %s; returning original text", e)
        return text


async def _llm_adapt(text: str, spec: PAdapt, state: dict[str, Any]) -> str:
    """LLM-adapt prompt text for target audience. Caches results via fingerprint."""
    cache_key = f"temp:_prompt_adapt_{spec.audience}_{hashlib.sha256(text.encode()).hexdigest()[:12]}"
    cached = state.get(cache_key)
    if cached:
        return str(cached)

    client = _get_genai_client()
    if client is None:
        _log.warning("GenAI client not available; skipping adaptation")
        return text

    try:
        prompt = (
            f"Rewrite the following instruction text for a {spec.audience} audience. "
            f"Adjust tone, complexity, and terminology appropriately. "
            f"Preserve all key requirements and constraints. "
            f"Return ONLY the adapted text, nothing else.\n\n{text}"
        )
        response = client.models.generate_content(model=spec.model, contents=prompt)
        result = response.text.strip() if response.text else text
        state[cache_key] = result
        return result
    except Exception as e:
        _log.warning("LLM adaptation failed: %s; returning original text", e)
        return text
