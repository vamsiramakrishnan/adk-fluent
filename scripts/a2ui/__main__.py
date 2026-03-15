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
import sys


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
        from scripts.a2ui.scanner import main as scan_main

        sys.argv = ["a2ui-scan", args.spec_dir]
        if args.output:
            sys.argv += ["-o", args.output]
        if args.summary:
            sys.argv += ["--summary"]
        scan_main()

    elif args.command == "seed":
        from scripts.a2ui.seed_generator import main as seed_main

        sys.argv = ["a2ui-seed", args.manifest, "-o", args.output]
        if args.merge:
            sys.argv += ["--merge", args.merge]
        if args.json:
            sys.argv += ["--json"]
        seed_main()

    elif args.command == "generate":
        from scripts.a2ui.generator import main as gen_main

        sys.argv = ["a2ui-generate", args.seed, "--output-dir", args.output_dir, "--test-dir", args.test_dir]
        gen_main()

    elif args.command == "all":
        from pathlib import Path

        from scripts.a2ui.generator import main as gen_main
        from scripts.a2ui.scanner import main as scan_main
        from scripts.a2ui.seed_generator import main as seed_main

        manifest_path = "a2ui_manifest.json"
        seed_path = "seeds/a2ui_seed.toml"
        manual_path = "seeds/a2ui_seed.manual.toml"

        print("=== Stage 1: Scan A2UI spec ===")
        sys.argv = ["a2ui-scan", args.spec_dir, "-o", manifest_path]
        scan_main()

        print("\n=== Stage 2: Generate seed ===")
        sys.argv = ["a2ui-seed", manifest_path, "-o", seed_path, "--json"]
        if Path(manual_path).exists():
            sys.argv += ["--merge", manual_path]
        seed_main()

        print("\n=== Stage 3: Generate code ===")
        sys.argv = ["a2ui-generate", seed_path, "--output-dir", args.output_dir, "--test-dir", args.test_dir]
        gen_main()

        print("\n=== A2UI pipeline complete ===")


if __name__ == "__main__":
    main()
