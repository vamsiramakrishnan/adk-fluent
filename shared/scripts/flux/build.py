"""flux codegen orchestrator.

One ``run(subcommand, root=...)`` entry point drives every stage. Stages
are pure functions of the catalog tree — re-running with no spec change
produces byte-identical output. The ``all`` command runs every stage in
order; individual stages are exposed so CI can run just the validation
gates without clobbering emitted files (``load`` / ``check``).
"""

from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path
from typing import Any

from shared.scripts.flux import checker, emit_catalog, emit_docs, emit_py, emit_react, emit_ts, loader


def _load(root: Path) -> dict[str, dict[str, Any]]:
    specs = loader.load_all(root)
    if not specs:
        raise RuntimeError(
            "flux build: no *.spec.ts files found under catalog/flux/specs/. "
            "W3 is responsible for adding specs; at minimum the Button reference "
            "spec must exist for the pipeline to run."
        )
    return specs


def _check(root: Path, specs: dict[str, dict[str, Any]]) -> None:
    checker.check_all(specs, root=root)


def _emit_catalog(root: Path, specs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    out = emit_catalog.emit(specs, root=root)
    print(f"[flux] wrote {out.relative_to(root)}")
    # Re-load from disk so downstream stages consume the byte-for-byte
    # representation the catalog would be shipped with.
    with out.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_catalog(root: Path) -> dict[str, Any]:
    path = root / "catalog" / "flux" / "catalog.json"
    if not path.is_file():
        raise RuntimeError("flux build: catalog.json is missing. Run the `emit` stage (or `all`) first.")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _emit_py(root: Path, catalog: dict[str, Any]) -> None:
    out = emit_py.emit(catalog, root=root)
    print(f"[flux] wrote {out.relative_to(root)}")


def _emit_ts(root: Path, catalog: dict[str, Any]) -> None:
    out = emit_ts.emit(catalog, root=root)
    print(f"[flux] wrote {out.relative_to(root)}")


def _emit_react(root: Path, catalog: dict[str, Any]) -> None:
    for out in emit_react.emit(catalog, root=root):
        print(f"[flux] wrote {out.relative_to(root)}")


def _emit_docs(root: Path, catalog: dict[str, Any]) -> None:
    for out in emit_docs.emit(catalog, root=root):
        print(f"[flux] wrote {out.relative_to(root)}")


def _clean(root: Path) -> None:
    # Generated files we own end-to-end.
    targets = [
        root / "catalog" / "flux" / "catalog.json",
        root / "python" / "src" / "adk_fluent" / "_flux_gen.py",
    ]
    for target in targets:
        if target.is_file():
            target.unlink()
            print(f"[flux] removed {target.relative_to(root)}")

    # Renderer tree: delete auto-generated files, preserve user-marked ones.
    renderer_dir = root / "ts" / "src" / "flux" / "renderer"
    if renderer_dir.is_dir():
        for path in sorted(renderer_dir.iterdir()):
            if not path.is_file():
                continue
            if path.name == "types.ts":
                path.unlink()
                print(f"[flux] removed {path.relative_to(root)}")
                continue
            if path.suffix in {".tsx", ".ts"}:
                # Preserve user scaffolds.
                try:
                    with path.open("r", encoding="utf-8") as fh:
                        first = fh.readline().rstrip("\n")
                except OSError:
                    continue
                if first.startswith(emit_react.USER_MARKER):
                    print(f"[flux] preserved user renderer {path.relative_to(root)}")
                    continue
                path.unlink()
                print(f"[flux] removed {path.relative_to(root)}")
        # Remove dir if empty.
        with contextlib.suppress(OSError):
            renderer_dir.rmdir()

    # Flux index.ts
    idx = root / "ts" / "src" / "flux" / "index.ts"
    if idx.is_file():
        idx.unlink()
        print(f"[flux] removed {idx.relative_to(root)}")
    # Remove ts/src/flux/ if now empty.
    flux_dir = root / "ts" / "src" / "flux"
    if flux_dir.is_dir():
        with contextlib.suppress(OSError):
            flux_dir.rmdir()

    # Docs
    docs_dir = root / "docs" / "flux" / "components"
    if docs_dir.is_dir():
        for path in sorted(docs_dir.iterdir()):
            if path.is_file() and path.suffix == ".md":
                path.unlink()
                print(f"[flux] removed {path.relative_to(root)}")
        with contextlib.suppress(OSError):
            docs_dir.rmdir()
            (root / "docs" / "flux").rmdir()


def run(subcommand: str, *, root: Path) -> int:
    try:
        if subcommand == "load":
            specs = _load(root)
            print(json.dumps(specs, indent=2, sort_keys=False))
            return 0
        if subcommand == "check":
            specs = _load(root)
            _check(root, specs)
            print(f"[flux] checked {len(specs)} component(s); no errors.")
            return 0
        if subcommand == "emit":
            specs = _load(root)
            _check(root, specs)
            _emit_catalog(root, specs)
            return 0
        if subcommand == "py":
            catalog = _load_catalog(root)
            _emit_py(root, catalog)
            return 0
        if subcommand == "ts":
            catalog = _load_catalog(root)
            _emit_ts(root, catalog)
            return 0
        if subcommand == "react":
            catalog = _load_catalog(root)
            _emit_react(root, catalog)
            return 0
        if subcommand == "docs":
            catalog = _load_catalog(root)
            _emit_docs(root, catalog)
            return 0
        if subcommand == "all":
            specs = _load(root)
            _check(root, specs)
            catalog = _emit_catalog(root, specs)
            _emit_py(root, catalog)
            _emit_ts(root, catalog)
            _emit_react(root, catalog)
            _emit_docs(root, catalog)
            print(f"[flux] pipeline complete: {len(specs)} component(s).")
            return 0
        if subcommand == "clean":
            _clean(root)
            return 0
        print(f"flux build: unknown subcommand {subcommand!r}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"flux build: ERROR {exc}", file=sys.stderr)
        return 1
