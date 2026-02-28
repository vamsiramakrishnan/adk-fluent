"""ADK-FLUENT SEED GENERATOR — modular seed.toml generation pipeline.

Reads a manifest.json (produced by scanner.py) and generates a seed.toml
that drives the code generation pipeline.

Package structure:
    classifier.py    — Classify ADK classes into semantic tags
    field_policy.py  — Determine how fields map to builder methods
    aliases.py       — Derive ergonomic short names for methods
    extras.py        — Generate non-field helper methods
    emitter.py       — Serialize to TOML format
    merger.py        — Overlay hand-written customizations
    orchestrator.py  — Main pipeline coordination

Usage:
    python scripts/seed_generator.py manifest.json                # stdout
    python scripts/seed_generator.py manifest.json -o seed.toml   # file output
"""

# Ensure module identity: whether loaded as 'scripts.seed_generator' or 'seed_generator'
import sys as _sys

_sys.modules.setdefault("seed_generator", _sys.modules[__name__])

from .aliases import (
    derive_alias,
    derive_aliases,
    generate_aliases,
    generate_callback_aliases,
)
from .classifier import classify_class, is_builder_worthy
from .emitter import emit_seed_toml
from .extras import generate_extras, infer_extras, merge_extras
from .field_policy import (
    get_field_policy,
    infer_field_policy,
    is_parent_reference,
)
from .merger import merge_manual_seed
from .orchestrator import (
    detect_constructor_args,
    determine_output_module,
    generate_seed_from_manifest,
)

__all__ = [
    "classify_class",
    "derive_alias",
    "derive_aliases",
    "detect_constructor_args",
    "determine_output_module",
    "emit_seed_toml",
    "generate_aliases",
    "generate_callback_aliases",
    "generate_extras",
    "generate_seed_from_manifest",
    "get_field_policy",
    "infer_extras",
    "infer_field_policy",
    "is_builder_worthy",
    "is_parent_reference",
    "merge_extras",
    "merge_manual_seed",
]
