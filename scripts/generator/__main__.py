"""CLI entry point: python -m scripts.generator OR python scripts/generator seed.toml manifest.json."""

from __future__ import annotations

import argparse

from .orchestrator import generate_all


def main():
    parser = argparse.ArgumentParser(description="Generate adk-fluent code from seed + manifest")
    parser.add_argument("seed", help="Path to seed.toml")
    parser.add_argument("manifest", help="Path to manifest.json")
    parser.add_argument("--output-dir", default="src/adk_fluent", help="Output directory for generated code")
    parser.add_argument("--test-dir", default=None, help="Output directory for test scaffolds")
    parser.add_argument("--stubs-only", action="store_true", help="Generate only .pyi stubs")
    parser.add_argument("--tests-only", action="store_true", help="Generate only test scaffolds")
    parser.add_argument("--stats", default=None, metavar="FILE", help="Write generation stats as JSON to FILE")
    args = parser.parse_args()

    generate_all(
        seed_path=args.seed,
        manifest_path=args.manifest,
        output_dir=args.output_dir,
        test_dir=args.test_dir,
        stubs_only=args.stubs_only,
        tests_only=args.tests_only,
        stats_json=args.stats,
    )


if __name__ == "__main__":
    main()
