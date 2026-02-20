"""Verify that seed.manual.toml only contains true exceptions — things
that genuinely cannot be inferred from type information."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from pathlib import Path


def test_manual_seed_only_contains_non_inferrable_extras():
    """Every extra in seed.manual.toml should have a behavior that requires
    human judgment — not things derivable from types."""
    manual_path = Path("seeds/seed.manual.toml")
    with open(manual_path, "rb") as f:
        manual = tomllib.load(f)

    INFERRABLE_BEHAVIORS = {"list_append"}

    for builder_name, config in manual.get("builders", {}).items():
        for extra in config.get("extras", []):
            behavior = extra.get("behavior", "custom")
            if behavior in INFERRABLE_BEHAVIORS:
                assert False, (
                    f"seed.manual.toml[{builder_name}].extras has inferrable "
                    f"extra '{extra['name']}' with behavior '{behavior}'. "
                    f"This should be auto-inferred, not manually specified."
                )
