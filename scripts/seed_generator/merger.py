"""Manual seed merging — overlay hand-written customizations onto auto-generated seed."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # Fallback

from .emitter import emit_seed_toml

_MANUAL_EXTRA_BEHAVIORS = frozenset(
    {
        "dual_callback",
        "deep_copy",
        "runtime_helper",
        "runtime_helper_async",
        "runtime_helper_async_gen",
        "runtime_helper_ctx",
    }
)


def merge_manual_seed(auto_toml: str, manual_path: str) -> str:
    """Merge a manual seed.toml overlay into auto-generated TOML output.

    1. Parse the auto-generated TOML string.
    2. Load the manual TOML file.
    3. Apply builder renames from [renames] in the manual file.
    4. Append manual extras to the corresponding builder's extras list.
    5. Return the merged TOML string.
    """
    # Parse auto-generated TOML
    auto = tomllib.loads(auto_toml)

    # Load manual TOML
    manual_file = Path(manual_path)
    if not manual_file.exists():
        print(f"WARNING: manual seed {manual_path} not found, skipping merge", file=sys.stderr)
        return auto_toml

    with open(manual_file, "rb") as f:
        manual = tomllib.load(f)

    # Step 1: Extract renames from manual [renames] section
    renames = manual.get("renames", {})

    # Step 2: Apply renames to builder names in the auto dict
    if renames and "builders" in auto:
        old_builders = auto["builders"]
        new_builders = {}
        for builder_name, builder_config in old_builders.items():
            # Check if this builder was generated from a class that should be renamed
            source_class_short = builder_config.get("source_class", "").split(".")[-1]
            new_name = renames.get(source_class_short)
            if new_name and builder_name == source_class_short:
                # Rename this builder
                new_builders[new_name] = builder_config
            else:
                new_builders[builder_name] = builder_config
        auto["builders"] = new_builders

    # Step 2b: Merge field_docs (manual wins on conflict)
    manual_field_docs = manual.get("field_docs", {})
    if manual_field_docs:
        existing_fd = auto.get("field_docs", {})
        existing_fd.update(manual_field_docs)
        auto["field_docs"] = existing_fd

    # Step 3: Merge manual config into matching builders
    manual_builders = manual.get("builders", {})
    for builder_name, manual_config in manual_builders.items():
        if builder_name not in auto.get("builders", {}):
            continue

        # Merge extras (manual overrides replace auto-generated ones with same name)
        manual_extras = manual_config.get("extras", [])
        if manual_extras:
            existing_extras = auto["builders"][builder_name].get("extras", [])
            manual_names = {e["name"] for e in manual_extras}
            # Keep auto extras that aren't overridden, then append manual ones
            merged = [e for e in existing_extras if e["name"] not in manual_names]
            merged.extend(manual_extras)
            auto["builders"][builder_name]["extras"] = merged

        # Merge optional_constructor_args
        opt_args = manual_config.get("optional_constructor_args")
        if opt_args:
            auto["builders"][builder_name]["optional_constructor_args"] = opt_args

        # Merge manual_aliases into aliases
        manual_aliases = manual_config.get("manual_aliases", {})
        if manual_aliases:
            existing_aliases = auto["builders"][builder_name].get("aliases", {})
            existing_aliases.update(manual_aliases)
            auto["builders"][builder_name]["aliases"] = existing_aliases

        # Merge deprecated_aliases
        dep_aliases = manual_config.get("deprecated_aliases", {})
        if dep_aliases:
            existing_dep = auto["builders"][builder_name].get("deprecated_aliases", {})
            existing_dep.update(dep_aliases)
            auto["builders"][builder_name]["deprecated_aliases"] = existing_dep
            # Remove deprecated names from regular aliases (they get their own methods)
            if "aliases" in auto["builders"][builder_name]:
                for dep_name in dep_aliases:
                    auto["builders"][builder_name]["aliases"].pop(dep_name, None)

    # Re-emit the merged TOML
    builders_list = []
    for name, config in auto.get("builders", {}).items():
        builder = {**config, "name": name}
        builders_list.append(builder)

    global_config = auto.get("global", {})
    # Promote top-level field_docs into global_config for re-emit
    if "field_docs" in auto:
        global_config["field_docs"] = auto["field_docs"]
    adk_version = auto.get("meta", {}).get("adk_version", "unknown")

    return emit_seed_toml(builders_list, global_config, adk_version=adk_version)
