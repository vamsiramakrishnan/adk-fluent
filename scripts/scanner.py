#!/usr/bin/env python3
"""
ADK-FLUENT SCANNER
==================
Introspects the installed google-adk package and produces a manifest.json
describing every Pydantic BaseModel class, its fields, types, defaults,
validators, callbacks, and inheritance hierarchy.

This is the machine-truth half of the codegen pipeline:
    seed.toml (human intent) + manifest.json (machine truth) → generated code

Usage:
    python scripts/scanner.py                          # stdout
    python scripts/scanner.py -o manifest.json         # file output
    python scripts/scanner.py --diff manifest.json     # show changes since last scan
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import pkgutil
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, get_type_hints

# ---------------------------------------------------------------------------
# CONFIGURATION: Which ADK modules to scan (legacy, kept for reference)
# ---------------------------------------------------------------------------
# SCAN_TARGETS = [
#     # (module_path, class_names_to_extract)
#     # None for class_names means "extract all BaseModel subclasses"
#     ("google.adk.agents", [
#         "BaseAgent", "LlmAgent", "SequentialAgent", "ParallelAgent",
#         "LoopAgent", "RunConfig", "InvocationContext",
#     ]),
#     ("google.adk.apps", ["App", "ResumabilityConfig"]),
#     ("google.adk.runners", ["Runner"]),
#     ("google.adk.artifacts", [
#         "BaseArtifactService", "InMemoryArtifactService",
#         "GcsArtifactService", "FileArtifactService",
#     ]),
#     ("google.adk.sessions", [
#         "InMemorySessionService",
#     ]),
#     ("google.adk.tools.base_tool", ["BaseTool"]),
#     ("google.adk.tools.function_tool", ["FunctionTool"]),
#     ("google.adk.events", ["Event"]),
# ]

# ---------------------------------------------------------------------------
# DATA STRUCTURES
# ---------------------------------------------------------------------------


@dataclass
class FieldInfo:
    """Describes a single field on a Pydantic model."""

    name: str
    type_str: str  # Human-readable type string
    type_raw: str  # Raw annotation repr for codegen
    default: str | None  # String repr of default, or None if required
    required: bool
    is_callback: bool  # True if type includes Callable
    is_list: bool  # True if type is list[...]
    description: str  # From Pydantic Field description
    inherited_from: str | None  # Parent class name, or None if own field
    validators: list[str]  # Names of validators that apply


@dataclass
class InitParam:
    """Describes a single __init__ parameter for non-Pydantic classes."""

    name: str
    type_str: str
    default: str | None  # None means required
    required: bool
    position: int  # 0-indexed, excluding self


@dataclass
class ClassInfo:
    """Describes a single ADK class."""

    name: str
    qualname: str  # e.g., "google.adk.agents.LlmAgent"
    module: str  # e.g., "google.adk.agents"
    is_pydantic: bool  # True if subclass of BaseModel
    bases: list[str]  # Direct base class names
    mro_chain: list[str]  # Full MRO class names
    fields: list[FieldInfo]  # All Pydantic fields (own + inherited)
    own_fields: list[str]  # Field names defined on THIS class only
    methods: list[str]  # Public method names (non-field)
    doc: str  # Class docstring
    inspection_mode: str = "pydantic"  # "pydantic" or "init_signature"
    init_params: list[InitParam] = field(default_factory=list)  # For non-Pydantic classes


@dataclass
class Manifest:
    """The complete scan output."""

    adk_version: str
    scan_timestamp: str
    python_version: str
    classes: list[ClassInfo]
    # Summary stats
    total_classes: int = 0
    total_fields: int = 0
    total_callbacks: int = 0


# ---------------------------------------------------------------------------
# AUTO-DISCOVERY
# ---------------------------------------------------------------------------


def discover_modules() -> list[str]:
    """Walk google.adk package tree and return sorted list of all submodule paths.

    Gracefully handles missing optional dependencies (a2a, docker, kubernetes, etc.).
    """
    import google.adk

    modules: list[str] = []
    for _importer, modname, _ispkg in pkgutil.walk_packages(google.adk.__path__, prefix="google.adk."):
        try:
            importlib.import_module(modname)
            modules.append(modname)
        except Exception:
            # Skip modules with missing optional deps
            pass
    return sorted(modules)


def discover_classes(modules: list[str]) -> list[tuple[type, str]]:
    """Import each module and find all public classes defined in it.

    Returns list of (class, module_path) tuples.
    Only includes classes where cls.__module__ == modname (avoids re-export duplicates).
    Skips private classes (name starts with '_').
    """
    result: list[tuple[type, str]] = []
    seen: set[int] = set()  # Track by id to avoid duplicates

    for modname in modules:
        try:
            mod = importlib.import_module(modname)
        except Exception:
            continue

        for attr_name in dir(mod):
            if attr_name.startswith("_"):
                continue
            obj = getattr(mod, attr_name, None)
            if obj is None or not isinstance(obj, type):
                continue
            if obj.__module__ != modname:
                continue
            if id(obj) in seen:
                continue
            seen.add(id(obj))
            result.append((obj, modname))

    return result


# ---------------------------------------------------------------------------
# INTROSPECTION ENGINE
# ---------------------------------------------------------------------------


def _type_to_str(annotation: Any) -> str:
    """Convert a type annotation to a readable string."""
    if annotation is inspect.Parameter.empty:
        return "Any"

    # Handle string annotations
    if isinstance(annotation, str):
        return annotation

    # Handle typing constructs
    origin = getattr(annotation, "__origin__", None)
    args = getattr(annotation, "__args__", None)

    if origin is not None:
        origin_name = getattr(origin, "__name__", str(origin))
        if args:
            args_str = ", ".join(_type_to_str(a) for a in args)
            return f"{origin_name}[{args_str}]"
        return origin_name

    # Handle plain classes
    if hasattr(annotation, "__name__"):
        return annotation.__name__

    # Fallback
    s = str(annotation)
    # Clean up common prefixes
    for prefix in ("typing.", "typing_extensions.", "google.genai.types."):
        s = s.replace(prefix, "")
    return s


def _is_callback_type(type_str: str) -> bool:
    """Heuristic: does this type represent a callback?"""
    return "Callable" in type_str or "callback" in type_str.lower()


def _is_list_type(type_str: str) -> bool:
    """Heuristic: is this a list type?"""
    return type_str.startswith("list[") or type_str.startswith("List[")


def _get_field_description(field_info) -> str:
    """Extract description from a Pydantic FieldInfo object."""
    if hasattr(field_info, "description") and field_info.description:
        return field_info.description
    if hasattr(field_info, "title") and field_info.title:
        return field_info.title
    return ""


def _get_default_repr(field_info) -> tuple[str | None, bool]:
    """Get default value repr and whether field is required."""
    from pydantic.fields import PydanticUndefined

    if field_info.default is PydanticUndefined:
        if field_info.default_factory is None:
            return None, True
        return f"{field_info.default_factory.__name__}()", False

    default = field_info.default
    if default is None:
        return "None", False
    if isinstance(default, str):
        return repr(default), False
    if isinstance(default, (int, float, bool)):
        return str(default), False
    return repr(default), False


def _find_field_origin(cls, field_name: str, mro: list[type]) -> str | None:
    """Find which class in the MRO originally defined this field."""
    for klass in reversed(mro):
        if hasattr(klass, "model_fields") and field_name in klass.model_fields and klass is not cls:
            return klass.__name__
    return None


def _scan_init_signature(cls) -> list[InitParam]:
    """Extract __init__ parameters using inspect.signature for non-Pydantic classes."""
    params: list[InitParam] = []
    try:
        sig = inspect.signature(cls.__init__)
    except (ValueError, TypeError):
        return params

    position = 0
    for name, param in sig.parameters.items():
        if name == "self":
            continue
        if name.startswith("_"):
            continue

        # Type annotation
        type_str = _type_to_str(param.annotation)

        # Default value
        if param.default is inspect.Parameter.empty:
            default = None
            required = True
        else:
            default = repr(param.default)
            required = False

        params.append(
            InitParam(
                name=name,
                type_str=type_str,
                default=default,
                required=required,
                position=position,
            )
        )
        position += 1

    return params


def scan_class(cls) -> ClassInfo:
    """Introspect a single class and produce ClassInfo."""
    module = cls.__module__
    qualname = f"{module}.{cls.__name__}"

    # Check if Pydantic
    from pydantic import BaseModel as PydanticBase

    is_pydantic = issubclass(cls, PydanticBase) if isinstance(cls, type) else False

    # MRO
    mro_names = [k.__name__ for k in cls.__mro__ if k is not object]
    base_names = [b.__name__ for b in cls.__bases__ if b is not object]

    # Fields (Pydantic models only)
    fields = []
    own_field_names = []

    if is_pydantic and hasattr(cls, "model_fields"):
        # Get type hints safely
        try:
            hints = get_type_hints(cls, include_extras=True)
        except Exception:
            hints = {}

        # Get validators
        validators_map = defaultdict(list)
        if hasattr(cls, "__validators__"):
            for v_name, v_info in cls.__validators__.items():
                for field_name in getattr(v_info, "fields", []):
                    validators_map[field_name].append(v_name)

        for field_name, field_info in cls.model_fields.items():
            type_annotation = hints.get(field_name, Any)
            type_str = _type_to_str(type_annotation)
            type_raw = repr(type_annotation)
            default_repr, required = _get_default_repr(field_info)
            description = _get_field_description(field_info)
            inherited_from = _find_field_origin(cls, field_name, cls.__mro__)

            fi = FieldInfo(
                name=field_name,
                type_str=type_str,
                type_raw=type_raw,
                default=default_repr,
                required=required,
                is_callback=_is_callback_type(type_str),
                is_list=_is_list_type(type_str),
                description=description,
                inherited_from=inherited_from,
                validators=validators_map.get(field_name, []),
            )
            fields.append(fi)

            if inherited_from is None:
                own_field_names.append(field_name)

    # Non-Pydantic: extract init params
    inspection_mode = "pydantic" if is_pydantic else "init_signature"
    init_params: list[InitParam] = []
    if not is_pydantic:
        init_params = _scan_init_signature(cls)

    # Public methods (non-dunder, non-private)
    methods = []
    for name, member in inspect.getmembers(cls):
        if name.startswith("_"):
            continue
        if name in {f.name for f in fields}:
            continue  # Skip fields
        if callable(member) or isinstance(member, (property, classmethod, staticmethod)):
            methods.append(name)

    return ClassInfo(
        name=cls.__name__,
        qualname=qualname,
        module=module,
        is_pydantic=is_pydantic,
        bases=base_names,
        mro_chain=mro_names,
        fields=fields,
        own_fields=own_field_names,
        methods=sorted(methods),
        doc=(cls.__doc__ or "").strip().split("\n")[0],  # First line only
        inspection_mode=inspection_mode,
        init_params=init_params,
    )


def scan_all() -> Manifest:
    """Scan all ADK modules using auto-discovery and produce a Manifest."""
    modules = discover_modules()
    class_tuples = discover_classes(modules)

    classes = []
    for cls, modpath in class_tuples:
        try:
            info = scan_class(cls)
            classes.append(info)
        except Exception as e:
            print(f"WARNING: Could not scan {cls.__name__} from {modpath}: {e}", file=sys.stderr)

    # Get ADK version
    try:
        from importlib.metadata import version

        adk_version = version("google-adk")
    except Exception:
        adk_version = "unknown"

    total_fields = sum(len(c.fields) for c in classes)
    total_callbacks = sum(sum(1 for f in c.fields if f.is_callback) for c in classes)

    return Manifest(
        adk_version=adk_version,
        scan_timestamp=datetime.now(UTC).isoformat(),
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        classes=classes,
        total_classes=len(classes),
        total_fields=total_fields,
        total_callbacks=total_callbacks,
    )


# ---------------------------------------------------------------------------
# DIFF ENGINE
# ---------------------------------------------------------------------------


def diff_manifests(old_path: str, new: Manifest) -> dict:
    """Compare a previous manifest with the current scan."""
    with open(old_path) as f:
        old_data = json.load(f)

    old_classes = {c["name"]: c for c in old_data.get("classes", [])}
    new_classes = {c.name: c for c in new.classes}

    added_classes = set(new_classes) - set(old_classes)
    removed_classes = set(old_classes) - set(new_classes)

    field_changes = {}
    for name in set(old_classes) & set(new_classes):
        old_fields = {f["name"] for f in old_classes[name].get("fields", [])}
        new_fields = {f.name for f in new_classes[name].fields}

        added = new_fields - old_fields
        removed = old_fields - new_fields

        if added or removed:
            field_changes[name] = {
                "added_fields": sorted(added),
                "removed_fields": sorted(removed),
            }

    return {
        "adk_version_old": old_data.get("adk_version", "unknown"),
        "adk_version_new": new.adk_version,
        "added_classes": sorted(added_classes),
        "removed_classes": sorted(removed_classes),
        "field_changes": field_changes,
        "breaking": bool(removed_classes or any(v.get("removed_fields") for v in field_changes.values())),
    }


# ---------------------------------------------------------------------------
# SERIALIZATION
# ---------------------------------------------------------------------------


def manifest_to_dict(m: Manifest) -> dict:
    """Convert manifest to JSON-serializable dict."""
    return {
        "adk_version": m.adk_version,
        "scan_timestamp": m.scan_timestamp,
        "python_version": m.python_version,
        "total_classes": m.total_classes,
        "total_fields": m.total_fields,
        "total_callbacks": m.total_callbacks,
        "classes": [asdict(c) for c in m.classes],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Scan ADK and produce manifest.json")
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    parser.add_argument("--diff", help="Compare against previous manifest.json")
    parser.add_argument("--summary", action="store_true", help="Print summary only")
    args = parser.parse_args()

    manifest = scan_all()

    if args.diff:
        changes = diff_manifests(args.diff, manifest)
        print(json.dumps(changes, indent=2))
        return

    if args.summary:
        print(f"ADK version:     {manifest.adk_version}")
        print(f"Classes scanned: {manifest.total_classes}")
        print(f"Total fields:    {manifest.total_fields}")
        print(f"Callback fields: {manifest.total_callbacks}")
        print("\nClasses:")
        for c in manifest.classes:
            if c.inspection_mode == "pydantic":
                own = len(c.own_fields)
                total = len(c.fields)
                cbs = sum(1 for f in c.fields if f.is_callback)
                print(f"  {c.name:30s} {total:3d} fields ({own} own, {cbs} callbacks) [Pydantic]")
            else:
                n_params = len(c.init_params)
                print(f"  {c.name:30s} {n_params:3d} init params [init_signature]")
        return

    data = manifest_to_dict(manifest)
    output = json.dumps(data, indent=2, default=str)

    if args.output:
        Path(args.output).write_text(output)
        print(f"Manifest written to {args.output}", file=sys.stderr)
        print(f"  ADK version:     {manifest.adk_version}", file=sys.stderr)
        print(f"  Classes scanned: {manifest.total_classes}", file=sys.stderr)
        print(f"  Total fields:    {manifest.total_fields}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
