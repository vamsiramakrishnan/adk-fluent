"""Run the TypeScript loader on every ``specs/*.spec.ts`` and return a dict.

The loader shells out to ``npx tsx shared/scripts/flux/_loader.ts`` with
``cwd=ts/`` and ``NODE_PATH=ts/node_modules`` so Zod + zod-to-json-schema
resolve via the TS workspace's ``package.json``. The spec file itself
lives under ``catalog/flux/specs/``; we pass it as an absolute path so
``pathToFileURL`` in the Node loader converts correctly.

Return shape::

    {
        "FluxButton": { ...component dict... },
        "FluxCard":   { ... },
        ...
    }

Keys are the ``name`` field of each spec (DSL invariant: must start with
``Flux``). Iteration order is the sorted alphabetic order of the spec
files on disk — this keeps ``catalog.json`` + emitted factories
deterministic without relying on the filesystem's natural order.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def _loader_script(root: Path) -> Path:
    return root / "shared" / "scripts" / "flux" / "_loader.ts"


def _ts_workspace(root: Path) -> Path:
    return root / "ts"


def _spec_files(root: Path) -> list[Path]:
    specs_dir = root / "catalog" / "flux" / "specs"
    if not specs_dir.is_dir():
        return []
    return sorted(p for p in specs_dir.glob("*.spec.ts") if p.is_file())


def _run_loader_on(root: Path, spec_path: Path) -> dict[str, Any]:
    ts_dir = _ts_workspace(root)
    if not (ts_dir / "node_modules").is_dir():
        raise RuntimeError(f"flux loader: ts/ workspace missing node_modules — run `cd {ts_dir} && npm install` first")
    if shutil.which("npx") is None:
        raise RuntimeError("flux loader: `npx` not found on PATH (install Node.js 20+)")
    env = os.environ.copy()
    env["NODE_PATH"] = str((ts_dir / "node_modules").resolve())
    cmd = [
        "npx",
        "--yes",
        "tsx",
        str(_loader_script(root).resolve()),
        str(spec_path.resolve()),
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(ts_dir),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        raise RuntimeError(f"flux loader: _loader.ts failed for {spec_path.name} (exit {proc.returncode})")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        sys.stderr.write(proc.stderr)
        raise RuntimeError(f"flux loader: _loader.ts produced non-JSON output for {spec_path.name}: {exc}") from exc


def load_all(root: Path) -> dict[str, dict[str, Any]]:
    """Load every spec under ``catalog/flux/specs/``, keyed by component name."""
    specs: dict[str, dict[str, Any]] = {}
    for spec_path in _spec_files(root):
        data = _run_loader_on(root, spec_path)
        name = data.get("name")
        if not isinstance(name, str):
            raise RuntimeError(f"flux loader: {spec_path.name} emitted no .name field")
        if name in specs:
            raise RuntimeError(f"flux loader: duplicate component name {name!r} across spec files")
        specs[name] = data
    return specs


def load_one(root: Path, spec_path: Path) -> dict[str, Any]:
    """Load a single spec file. Primarily a test hook."""
    return _run_loader_on(root, spec_path)
