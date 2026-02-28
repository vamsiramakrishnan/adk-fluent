#!/usr/bin/env python3
"""
ADK-FLUENT SEED GENERATOR — backward-compatible CLI entry point.

The implementation lives in the ``scripts/seed_generator/`` package.
This file provides the CLI ``main()`` so that
``python scripts/seed_generator.py manifest.json`` continues to work.

NOTE: When Python sees both seed_generator.py and seed_generator/ in the same
directory, the package (seed_generator/) takes precedence for imports.  This
file is only reached via ``python scripts/seed_generator.py`` (direct execution).
"""

if __name__ == "__main__":
    from seed_generator.__main__ import main

    main()
