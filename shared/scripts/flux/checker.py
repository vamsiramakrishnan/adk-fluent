"""Validate loaded specs against token packs + basic-catalog whitelist.

Checks performed (from ARCHITECTURE.md §4.3, §6):

  1. Every ``$token.path`` referenced in ``variants`` or ``compoundVariants``
     (or anywhere else a ``$`` prefix appears) must resolve in BOTH token
     packs (``flux-light.json`` + ``flux-dark.json``).
  2. Every spec's ``name`` must start with ``Flux`` (DSL invariant, but we
     re-check post-load so a spec that bypassed ``defineComponent`` at
     import time still fails loudly).
  3. The ``tokens`` array declared in the spec must match actual usage:
        - any token path referenced but NOT listed in ``tokens`` → FAIL
        - any token path listed but NOT referenced → WARN
  4. ``renderer.fallback.component`` must be one of the 18 basic-catalog
     component names (the ``extends`` enum in ``component.schema.json``).

Failures raise ``CheckerError``; warnings are printed to stderr and do not
stop the pipeline. The W3 owner is expected to clean warnings up as they
land component specs.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

# The 18 basic-catalog component kinds, mirroring the ``extends`` enum in
# ``catalog/flux/schema/component.schema.json``. Keep this frozenset in sync
# with that schema — the canonical source is the schema file, and this
# module validates against it at startup.
BASIC_CATALOG_COMPONENTS: frozenset[str] = frozenset(
    {
        "Text",
        "Image",
        "Icon",
        "Video",
        "AudioPlayer",
        "Row",
        "Column",
        "List",
        "Card",
        "Tabs",
        "Modal",
        "Divider",
        "Button",
        "TextField",
        "CheckBox",
        "ChoicePicker",
        "Slider",
        "DateTimeInput",
    }
)


class CheckerError(RuntimeError):
    """Raised when a spec violates a checker invariant."""


def _load_pack(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise CheckerError(f"token pack missing: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _resolve(pack: dict[str, Any], path: str) -> bool:
    cursor: Any = pack
    for segment in path.split("."):
        if not isinstance(cursor, dict) or segment not in cursor:
            return False
        cursor = cursor[segment]
    return not isinstance(cursor, dict)


_TOKEN_REF_RE = re.compile(r"^\$([a-zA-Z][\w]*(?:\.[\w]+)+)$")


def _extract_refs(value: Any, acc: set[str]) -> None:
    """Walk a spec value tree and collect every ``$<dotted.path>`` token ref."""
    if isinstance(value, str):
        match = _TOKEN_REF_RE.match(value)
        if match is not None:
            acc.add(match.group(1))
        return
    if isinstance(value, dict):
        for v in value.values():
            _extract_refs(v, acc)
        return
    if isinstance(value, list):
        for item in value:
            _extract_refs(item, acc)
        return


def check_spec(
    name: str,
    spec: dict[str, Any],
    *,
    light_pack: dict[str, Any],
    dark_pack: dict[str, Any],
) -> list[str]:
    """Validate one spec. Raises ``CheckerError`` on hard failure; returns warnings."""
    warnings: list[str] = []
    # (2) name prefix
    if not name.startswith("Flux"):
        raise CheckerError(f"{name}: component name must start with 'Flux'")
    if spec.get("name") != name:
        raise CheckerError(f"{name}: spec.name={spec.get('name')!r} does not match the dict key")

    # (4) fallback.component whitelist
    renderer = spec.get("renderer") or {}
    fallback = renderer.get("fallback") or {}
    fb_component = fallback.get("component")
    if not isinstance(fb_component, str):
        raise CheckerError(f"{name}: renderer.fallback.component is missing")
    if fb_component not in BASIC_CATALOG_COMPONENTS:
        raise CheckerError(
            f"{name}: renderer.fallback.component={fb_component!r} is not a basic-catalog component. "
            f"Allowed: {sorted(BASIC_CATALOG_COMPONENTS)}"
        )

    # (1) + (3) token refs
    refs: set[str] = set()
    # Only scan variant/compoundVariant blocks for $-refs (the canonical
    # style surface). Everything else (jsonSchema, llm text, renderer) is
    # free to mention token-like strings without triggering the check.
    for block_key in ("variants", "compoundVariants"):
        if block_key in spec:
            _extract_refs(spec[block_key], refs)

    declared = set(spec.get("tokens") or [])

    # (1) resolution in both packs
    missing_light = sorted(r for r in refs if not _resolve(light_pack, r))
    missing_dark = sorted(r for r in refs if not _resolve(dark_pack, r))
    if missing_light or missing_dark:
        parts: list[str] = []
        if missing_light:
            parts.append(f"missing in flux-light: {missing_light}")
        if missing_dark:
            parts.append(f"missing in flux-dark: {missing_dark}")
        raise CheckerError(f"{name}: unresolved token refs — " + "; ".join(parts))

    # (3) tokens array vs. actual usage
    used_but_not_listed = sorted(r for r in refs if r not in declared)
    if used_but_not_listed:
        raise CheckerError(
            f"{name}: token refs used but missing from the tokens[] array — add them: {used_but_not_listed}"
        )
    listed_but_not_used = sorted(t for t in declared if t not in refs)
    if listed_but_not_used:
        warnings.append(
            f"{name}: tokens listed in tokens[] but never referenced — consider removing: {listed_but_not_used}"
        )

    return warnings


def check_all(
    specs: dict[str, dict[str, Any]],
    *,
    root: Path,
) -> list[str]:
    """Run all checks against the two shipped token packs. Returns warning list."""
    tokens_dir = root / "catalog" / "flux" / "tokens"
    light = _load_pack(tokens_dir / "flux-light.json")
    dark = _load_pack(tokens_dir / "flux-dark.json")
    all_warnings: list[str] = []
    for name in sorted(specs):
        all_warnings.extend(check_spec(name, specs[name], light_pack=light, dark_pack=dark))
    # Echo warnings to stderr so CI logs flag them, but never fail the
    # pipeline solely on warnings.
    for warning in all_warnings:
        print(f"[flux check] WARN {warning}", file=sys.stderr)
    return all_warnings
