"""DocIR — the typed intermediate representation for adk-fluent documentation.

All documentation renderers (``doc_generator``, ``llms_generator``,
``skill_generator``, ``concepts_generator``, ``cookbook_generator``) should
consume this representation rather than re-walking ``manifest.json`` and
``seed.toml`` independently.  Keeping the traversal in one place is what
lets us:

  * compute canonical anchor IDs exactly once (fixing the
    235-finding case-drift problem flagged in the pipeline audit),
  * enumerate namespaces by *introspecting the live ``adk_fluent`` package*
    instead of maintaining a hand-written list,
  * cross-check rendered output against the IR from ``docs_validator``.

The module is intentionally self-contained: it depends only on
``pydantic`` plus the existing ``generator`` package (for seed/manifest
parsing).  Importing this module has no side effects.

Usage::

    from doc_ir import DocIR, build_doc_ir

    ir = build_doc_ir("shared/seeds/seed.toml", "shared/manifest.json",
                      cookbook_dir="examples/cookbook")
    ir.write_json("docs/_generated/doc_ir.json")
"""

from __future__ import annotations

import importlib
import inspect
import json
import re
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# Make the sibling ``generator`` package importable regardless of CWD.
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from generator import BuilderSpec, parse_manifest, parse_seed, resolve_builder_specs  # noqa: E402


# ---------------------------------------------------------------------------
# Canonical anchor ID — used by every renderer
# ---------------------------------------------------------------------------


_ANCHOR_STRIP = re.compile(r"[^a-zA-Z0-9\-]")


def anchor_id(name: str, *, prefix: str = "") -> str:
    """Canonical, deterministic anchor ID.

    The same rule runs in all renderers so that ``[FooTool](tool.md#builder-footool)``
    resolves regardless of source casing. Rules:

      * lower-case
      * non-alnum characters → ``-``
      * collapse repeated ``-``
      * strip leading/trailing ``-``
      * optional prefix prepended with ``-``

    Examples::

        anchor_id("MCPTool", prefix="builder") → "builder-mcptool"
        anchor_id("URL Context Tool")          → "url-context-tool"
    """
    slug = _ANCHOR_STRIP.sub("-", name).lower()
    slug = re.sub(r"-+", "-", slug).strip("-")
    return f"{prefix}-{slug}" if prefix else slug


# ---------------------------------------------------------------------------
# DocIR schema (Pydantic v2)
# ---------------------------------------------------------------------------


class FieldRef(BaseModel):
    """One Pydantic field on a builder's source class."""

    model_config = ConfigDict(extra="ignore")

    name: str
    type_str: str
    default: Any | None = None
    required: bool = False
    description: str | None = None
    is_callback: bool = False
    is_list: bool = False
    inherited_from: str | None = None


class BuilderRef(BaseModel):
    """One fluent builder."""

    model_config = ConfigDict(extra="forbid")

    name: str                         # "Agent"
    module: str                       # "agent"
    source_class: str                 # "google.adk.agents.LlmAgent"
    source_class_short: str           # "LlmAgent"
    description: str
    is_composite: bool = False
    is_standalone: bool = False
    constructor_args: list[str] = Field(default_factory=list)
    aliases: dict[str, str] = Field(default_factory=dict)
    fields: list[FieldRef] = Field(default_factory=list)
    anchor: str                       # "builder-agent"
    doc_path: str                     # "generated/builders/agent.md#builder-agent"


class NamespaceMethod(BaseModel):
    """One method on a namespace module (P, C, S, ...)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    signature: str
    summary: str
    description: str | None = None


class NamespaceDoc(BaseModel):
    """One namespace (P, C, S, A, M, T, G, UI, E, H)."""

    model_config = ConfigDict(extra="forbid")

    symbol: str                       # "P"
    module: str                       # "adk_fluent._prompt"
    title: str                        # "Prompt composition"
    anchor: str
    methods: list[NamespaceMethod] = Field(default_factory=list)


class CookbookEntry(BaseModel):
    """One cookbook example."""

    model_config = ConfigDict(extra="forbid")

    index: int
    slug: str                         # "01_hello_world"
    title: str
    category: str
    source_path: str                  # "examples/cookbook/01_hello_world.py"
    render_path: str                  # "docs/generated/cookbook/01_hello_world.md"
    preserve: bool = False            # explicit marker, not heuristic


class ConceptSection(BaseModel):
    """One extracted conceptual section (three-channels, five-ops, ...)."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    title: str
    body: str                         # rendered markdown
    source_file: str                  # for provenance
    source_heading: str


class DocIR(BaseModel):
    """The complete documentation intermediate representation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    adk_version: str = ""
    fluent_version: str = ""
    scan_timestamp: str = ""
    builders: list[BuilderRef] = Field(default_factory=list)
    namespaces: list[NamespaceDoc] = Field(default_factory=list)
    cookbooks: list[CookbookEntry] = Field(default_factory=list)
    concepts: list[ConceptSection] = Field(default_factory=list)

    # -- Convenience lookups ------------------------------------------------

    def builder_by_name(self, name: str) -> BuilderRef | None:
        for b in self.builders:
            if b.name == name:
                return b
        return None

    def namespace_by_symbol(self, symbol: str) -> NamespaceDoc | None:
        for n in self.namespaces:
            if n.symbol == symbol:
                return n
        return None

    # -- Serialisation ------------------------------------------------------

    def write_json(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(self.model_dump_json(indent=2) + "\n")
        return out

    @classmethod
    def read_json(cls, path: str | Path) -> DocIR:
        return cls.model_validate_json(Path(path).read_text())


# ---------------------------------------------------------------------------
# Namespace introspection — replaces the hand-declared NAMESPACE_MODULES
# ---------------------------------------------------------------------------


_NAMESPACE_SYMBOLS = ("P", "C", "S", "A", "M", "T", "G", "UI", "E", "H")

_NAMESPACE_TITLES = {
    "P": "Prompt composition",
    "C": "Context engineering",
    "S": "State transforms",
    "A": "Artifacts",
    "M": "Middleware",
    "T": "Tool composition",
    "G": "Guards",
    "UI": "Agent-to-UI",
    "E": "Evaluation",
    "H": "Harness",
}


def _summarise_docstring(doc: str | None) -> tuple[str, str | None]:
    """Return (first-line summary, rest) from a docstring."""
    if not doc:
        return "", None
    stripped = inspect.cleandoc(doc)
    lines = stripped.splitlines()
    if not lines:
        return "", None
    first = lines[0].strip()
    rest = "\n".join(lines[1:]).strip() or None
    return first, rest


def introspect_namespaces(package: str = "adk_fluent") -> list[NamespaceDoc]:
    """Import ``adk_fluent`` and reflect each namespace module.

    Replaces the hand-declared ``NAMESPACE_MODULES`` list in
    ``doc_generator.py``.  If a new namespace is added to the package, this
    function picks it up automatically.
    """
    mod = importlib.import_module(package)
    result: list[NamespaceDoc] = []

    for symbol in _NAMESPACE_SYMBOLS:
        ns = getattr(mod, symbol, None)
        if ns is None:
            continue

        methods: list[NamespaceMethod] = []
        for attr_name in sorted(dir(ns)):
            if attr_name.startswith("_"):
                continue
            attr = getattr(ns, attr_name)
            if not callable(attr):
                continue
            try:
                sig = str(inspect.signature(attr))
            except (TypeError, ValueError):
                sig = "(...)"
            summary, rest = _summarise_docstring(inspect.getdoc(attr))
            methods.append(
                NamespaceMethod(
                    name=attr_name,
                    signature=f"{symbol}.{attr_name}{sig}",
                    summary=summary or f"{symbol}.{attr_name}",
                    description=rest,
                )
            )

        title = _NAMESPACE_TITLES.get(symbol, symbol)
        result.append(
            NamespaceDoc(
                symbol=symbol,
                module=getattr(ns, "__module__", f"adk_fluent._{symbol.lower()}"),
                title=title,
                anchor=anchor_id(symbol, prefix="namespace"),
                methods=methods,
            )
        )

    return result


# ---------------------------------------------------------------------------
# Spec → BuilderRef
# ---------------------------------------------------------------------------


def _spec_to_builder_ref(spec: BuilderSpec) -> BuilderRef:
    fields = [
        FieldRef(
            name=f.get("name", ""),
            type_str=f.get("type_str", ""),
            default=f.get("default"),
            required=bool(f.get("required", False)),
            description=f.get("description"),
            is_callback=bool(f.get("is_callback", False)),
            is_list=bool(f.get("is_list", False)),
            inherited_from=f.get("inherited_from"),
        )
        for f in spec.fields
    ]
    anchor = anchor_id(spec.name, prefix="builder")
    return BuilderRef(
        name=spec.name,
        module=spec.output_module,
        source_class=spec.source_class,
        source_class_short=spec.source_class_short,
        description=spec.doc or "",
        is_composite=spec.is_composite,
        is_standalone=spec.is_standalone,
        constructor_args=list(spec.constructor_args),
        aliases=dict(spec.aliases),
        fields=fields,
        anchor=anchor,
        doc_path=f"generated/builders/{spec.output_module}.md#{anchor}",
    )


# ---------------------------------------------------------------------------
# Cookbook discovery
# ---------------------------------------------------------------------------


_COOKBOOK_CATEGORIES: tuple[tuple[range, str], ...] = (
    (range(1, 8), "Basics"),
    (range(8, 14), "Execution"),
    (range(14, 21), "Advanced"),
    (range(21, 44), "Patterns"),
    (range(44, 49), "v4 Features"),
    (range(49, 75), "v5.1 Features"),
    (range(75, 1000), "Skills & Harness"),
)


def _categorise(index: int) -> str:
    for r, name in _COOKBOOK_CATEGORIES:
        if index in r:
            return name
    return "Other"


_COOKBOOK_INDEX_RE = re.compile(r"^(\d{2})_(.+)\.py$")


def _extract_title(path: Path) -> str:
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped.startswith('"""') and len(stripped) > 3:
            return stripped.strip('"').strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return path.stem


_PRESERVE_MARKER = "<!-- adk-fluent:hand-crafted -->"


def discover_cookbooks(cookbook_dir: Path, docs_dir: Path) -> list[CookbookEntry]:
    out: list[CookbookEntry] = []
    if not cookbook_dir.is_dir():
        return out

    for py in sorted(cookbook_dir.glob("[0-9][0-9]_*.py")):
        m = _COOKBOOK_INDEX_RE.match(py.name)
        if not m:
            continue
        idx = int(m.group(1))
        slug = py.stem
        render_path = docs_dir / "generated" / "cookbook" / f"{slug}.md"
        preserve = render_path.exists() and _PRESERVE_MARKER in render_path.read_text()
        out.append(
            CookbookEntry(
                index=idx,
                slug=slug,
                title=_extract_title(py),
                category=_categorise(idx),
                source_path=str(py.relative_to(cookbook_dir.parent.parent))
                if cookbook_dir.parent.parent in py.parents
                else str(py),
                render_path=str(render_path),
                preserve=preserve,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Top-level builder
# ---------------------------------------------------------------------------


def build_doc_ir(
    seed_path: str | Path,
    manifest_path: str | Path,
    *,
    cookbook_dir: str | Path = "examples/cookbook",
    docs_dir: str | Path = "docs",
    concepts: list[ConceptSection] | None = None,
) -> DocIR:
    """Build the canonical ``DocIR`` from source-of-truth inputs."""
    seed = parse_seed(str(seed_path))
    manifest = parse_manifest(str(manifest_path))
    specs = resolve_builder_specs(seed, manifest)

    builders = [_spec_to_builder_ref(s) for s in specs]
    namespaces = introspect_namespaces()
    cookbooks = discover_cookbooks(Path(cookbook_dir), Path(docs_dir))

    return DocIR(
        schema_version=1,
        adk_version=str(manifest.get("adk_version", "")),
        fluent_version=str(manifest.get("fluent_version", "")),
        scan_timestamp=str(manifest.get("scan_timestamp", "")),
        builders=builders,
        namespaces=namespaces,
        cookbooks=cookbooks,
        concepts=concepts or [],
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Build the DocIR JSON snapshot.")
    parser.add_argument("--seed", default="shared/seeds/seed.toml")
    parser.add_argument("--manifest", default="shared/manifest.json")
    parser.add_argument("--cookbook-dir", default="examples/cookbook")
    parser.add_argument("--docs-dir", default="docs")
    parser.add_argument("--out", default="docs/_generated/doc_ir.json")
    args = parser.parse_args()

    ir = build_doc_ir(
        args.seed,
        args.manifest,
        cookbook_dir=args.cookbook_dir,
        docs_dir=args.docs_dir,
    )
    written = ir.write_json(args.out)
    print(
        f"DocIR written to {written}: "
        f"{len(ir.builders)} builders, {len(ir.namespaces)} namespaces, "
        f"{len(ir.cookbooks)} cookbooks, {len(ir.concepts)} concepts."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
