#!/usr/bin/env python3
"""
A2UI Pipeline CLI — unified entry point.

Usage:
    python -m scripts.a2ui scan specification/v0_10/json/ -o a2ui_manifest.json
    python -m scripts.a2ui seed a2ui_manifest.json -o seeds/a2ui_seed.toml
    python -m scripts.a2ui generate seeds/a2ui_seed.toml --output-dir src/adk_fluent
    python -m scripts.a2ui all specification/v0_10/json/   # full pipeline
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="scripts.a2ui",
        description="A2UI codegen pipeline: scan → seed → generate",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --- scan ---
    p_scan = sub.add_parser("scan", help="Scan A2UI spec → a2ui_manifest.json")
    p_scan.add_argument("spec_dir", help="A2UI JSON Schema directory")
    p_scan.add_argument("-o", "--output", default="a2ui_manifest.json")
    p_scan.add_argument("--summary", action="store_true")

    # --- seed ---
    p_seed = sub.add_parser("seed", help="a2ui_manifest.json → a2ui_seed.toml")
    p_seed.add_argument("manifest", help="Path to a2ui_manifest.json")
    p_seed.add_argument("-o", "--output", required=True)
    p_seed.add_argument("--merge", help="Manual overrides TOML")
    p_seed.add_argument("--json", action="store_true")

    # --- generate ---
    p_gen = sub.add_parser("generate", help="a2ui_seed → _ui_generated.py")
    p_gen.add_argument("seed", help="Path to a2ui_seed.toml (or JSON)")
    p_gen.add_argument("--output-dir", default="src/adk_fluent")
    p_gen.add_argument("--test-dir", default="tests/generated")

    # --- all ---
    p_all = sub.add_parser("all", help="Full pipeline: scan → seed → generate")
    p_all.add_argument("spec_dir", help="A2UI JSON Schema directory")
    p_all.add_argument("--output-dir", default="src/adk_fluent")
    p_all.add_argument("--test-dir", default="tests/generated")

    args = parser.parse_args()

    if args.command == "scan":
        from scripts.a2ui.scanner import run as scan_run

        scan_run(
            spec_dir=Path(args.spec_dir),
            output=Path(args.output) if args.output else None,
            summary=args.summary,
        )

    elif args.command == "seed":
        from scripts.a2ui.seed_generator import run as seed_run

        seed_run(
            manifest=Path(args.manifest),
            output=Path(args.output),
            merge=Path(args.merge) if args.merge else None,
            prefer_json=args.json,
        )

    elif args.command == "generate":
        from scripts.a2ui.generator import run as gen_run

        gen_run(
            seed=Path(args.seed),
            output_dir=Path(args.output_dir),
            test_dir=Path(args.test_dir),
        )

    elif args.command == "all":
        from scripts.a2ui.generator import run as gen_run
        from scripts.a2ui.scanner import run as scan_run
        from scripts.a2ui.seed_generator import run as seed_run

        manifest_path = Path("a2ui_manifest.json")
        seed_path = Path("seeds/a2ui_seed.toml")
        manual_path = Path("seeds/a2ui_seed.manual.toml")

        print("=== Stage 1: Scan A2UI spec ===")
        scan_run(spec_dir=Path(args.spec_dir), output=manifest_path)

        print("\n=== Stage 2: Generate seed ===")
        seed_run(
            manifest=manifest_path,
            output=seed_path,
            merge=manual_path if manual_path.exists() else None,
            prefer_json=True,
        )

        print("\n=== Stage 3: Generate code ===")
        gen_run(
            seed=seed_path,
            output_dir=Path(args.output_dir),
            test_dir=Path(args.test_dir),
        )

        print("\n=== A2UI pipeline complete ===")


if __name__ == "__main__":
    main()
