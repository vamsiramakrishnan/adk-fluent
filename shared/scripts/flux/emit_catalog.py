"""Emit ``catalog/flux/catalog.json`` from the loaded spec tree.

Shape (see ARCHITECTURE.md §5 and ``schema/catalog.schema.json``)::

    {
      "catalogId":  "flux/components@1",
      "version":    "1.0.0",
      "extends":    ["a2ui/basic@0.10"],
      "tokens":     { "light": "./tokens/flux-light.json",
                      "dark":  "./tokens/flux-dark.json" },
      "components": { "FluxButton": { <component block> }, ... },
      "fallbacks":  { "FluxButton": "Button", ... }
    }

The emitted JSON is pretty-printed with 2-space indent, trailing newline,
and alphabetically ordered keys in ``components``/``fallbacks`` so two
runs produce byte-identical output.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

CATALOG_ID = "flux/components@1"
CATALOG_VERSION = "1.0.0"
CATALOG_EXTENDS = ("a2ui/basic@0.10",)
TOKENS_MAP = {
    "light": "./tokens/flux-light.json",
    "dark": "./tokens/flux-dark.json",
}


def _canonical_component(spec: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy of ``spec`` with a stable key order.

    Matches the CANONICAL_ORDER used by ``_loader.ts`` so a round-trip
    through JSON is a no-op. Any extra key (future DSL addition) lands in
    alphabetic order after the canonical block.
    """
    canonical_order = (
        "name",
        "extends",
        "category",
        "jsonSchema",
        "slots",
        "tokens",
        "variants",
        "compoundVariants",
        "defaultVariants",
        "accessibility",
        "llm",
        "renderer",
    )
    out: dict[str, Any] = {}
    for key in canonical_order:
        if key in spec:
            out[key] = spec[key]
    for key in sorted(spec):
        if key not in out:
            out[key] = spec[key]
    return out


def build_catalog(specs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    components: dict[str, Any] = {}
    fallbacks: dict[str, str] = {}
    for name in sorted(specs):
        spec = specs[name]
        components[name] = _canonical_component(spec)
        renderer = spec.get("renderer") or {}
        fallback = renderer.get("fallback") or {}
        fb_component = fallback.get("component")
        if isinstance(fb_component, str):
            fallbacks[name] = fb_component
    return {
        "catalogId": CATALOG_ID,
        "version": CATALOG_VERSION,
        "extends": list(CATALOG_EXTENDS),
        "tokens": dict(TOKENS_MAP),
        "components": components,
        "fallbacks": fallbacks,
    }


def _load_catalog_schema(root: Path) -> dict[str, Any]:
    path = root / "catalog" / "flux" / "schema" / "catalog.schema.json"
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _build_validator(root: Path) -> jsonschema.protocols.Validator:
    """Build a validator that resolves the in-tree schema $refs.

    ``catalog.schema.json`` $refs ``component.schema.json`` by absolute
    URL. We pre-load both and install a custom registry so validation runs
    offline.
    """
    schema_dir = root / "catalog" / "flux" / "schema"
    catalog_schema = json.loads((schema_dir / "catalog.schema.json").read_text("utf-8"))
    component_schema = json.loads((schema_dir / "component.schema.json").read_text("utf-8"))
    try:
        # jsonschema >= 4.18 uses the referencing library.
        from referencing import Registry, Resource
        from referencing.jsonschema import DRAFT202012

        registry: Registry[Any] = Registry().with_resources(
            [
                (catalog_schema["$id"], Resource(contents=catalog_schema, specification=DRAFT202012)),
                (component_schema["$id"], Resource(contents=component_schema, specification=DRAFT202012)),
            ]
        )
        validator_cls = jsonschema.validators.validator_for(catalog_schema)
        return validator_cls(catalog_schema, registry=registry)
    except ImportError:  # pragma: no cover — fallback for very old jsonschema
        return jsonschema.Draft202012Validator(catalog_schema)


def validate_catalog(catalog: dict[str, Any], *, root: Path) -> None:
    validator = _build_validator(root)
    errors = sorted(validator.iter_errors(catalog), key=lambda e: list(e.absolute_path))
    if errors:
        lines = ["catalog.json failed schema validation:"]
        for err in errors:
            path = "/".join(str(p) for p in err.absolute_path)
            lines.append(f"  {path or '<root>'}: {err.message}")
        raise RuntimeError("\n".join(lines))


def emit(
    specs: dict[str, dict[str, Any]],
    *,
    root: Path,
) -> Path:
    catalog = build_catalog(specs)
    validate_catalog(catalog, root=root)
    out_path = root / "catalog" / "flux" / "catalog.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # sort_keys=False so nested dicts keep the canonical order we constructed
    # above; we only sort the top-level ``components`` / ``fallbacks`` maps
    # (already alphabetised in ``build_catalog``).
    serialized = json.dumps(catalog, indent=2, sort_keys=False, ensure_ascii=False)
    out_path.write_text(serialized + "\n", encoding="utf-8")
    return out_path
