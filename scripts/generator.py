#!/usr/bin/env python3
"""
ADK-FLUENT GENERATOR — backward-compatible CLI entry point.

The implementation lives in the ``scripts/generator/`` package.
This file provides the CLI ``main()`` so that
``python scripts/generator.py seed.toml manifest.json`` continues to work.

For imports, use the package directly:
    from generator import BuilderSpec, parse_seed, parse_manifest, ...

NOTE: When Python sees both generator.py and generator/ in the same directory,
the package (generator/) takes precedence for imports.  This file is only
reached via ``python scripts/generator.py`` (direct execution), at which
point ``__name__ == "__main__"``.
"""

if __name__ == "__main__":
    from generator.__main__ import main

    main()
