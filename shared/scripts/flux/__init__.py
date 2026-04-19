"""flux catalog codegen pipeline.

Turns ``catalog/flux/specs/*.spec.ts`` into:

  * ``catalog/flux/catalog.json``                         — catalog emit
  * ``python/src/adk_fluent/_flux_gen.py``                — Python factories
  * ``ts/src/flux/index.ts``                              — TS factories
  * ``ts/src/flux/renderer/*.tsx``                        — React scaffolds
  * ``ts/src/flux/renderer/{index,types}.ts``             — renderer wiring
  * ``docs/flux/components/<kebab>.md``                   — per-component docs

Every emitted file carries a ``DO NOT EDIT`` marker and is deterministic
(byte-identical when re-run with the same inputs). The react stage is the
single exception: files whose first line is ``// flux:scaffold-user`` are
preserved unchanged so hand-written renderers survive regeneration.

Public entry point::

    python -m shared.scripts.flux all
"""

from __future__ import annotations

# Make ``shared/scripts/`` importable as a bare top-level path so the loader
# and emit helpers can ``from shared.scripts.flux import X`` AND
# ``from flux import X`` regardless of cwd. Mirrors the setup used by
# ``shared/scripts/generator/__init__.py``.
import sys as _sys
from pathlib import Path as _Path

_scripts_dir = str(_Path(__file__).resolve().parent.parent)
if _scripts_dir not in _sys.path:
    _sys.path.insert(0, _scripts_dir)
