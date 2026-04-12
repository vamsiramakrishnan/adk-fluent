"""Visual test suite fixtures.

Provides fixtures for:
- Loading cookbook modules and extracting A2UI surfaces
- Golden file comparison (snapshot testing)
- Surface compilation and validation
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

import pytest

GOLDEN_DIR = Path(__file__).parent / "golden"
COOKBOOK_DIR = Path(__file__).parents[2] / "examples" / "cookbook"


def pytest_configure(config):
    config.addinivalue_line("markers", "visual: visual regression tests for A2UI surfaces")


@pytest.fixture
def golden_dir():
    """Path to golden file directory."""
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    return GOLDEN_DIR


@pytest.fixture
def update_golden(request):
    """Whether to update golden files (pass --update-golden)."""
    return request.config.getoption("--update-golden", default=False)


def pytest_addoption(parser):
    with contextlib.suppress(ValueError):
        parser.addoption("--update-golden", action="store_true", default=False, help="Update golden snapshot files")


def assert_golden(data: dict | list, name: str, golden_dir: Path, update: bool = False):
    """Compare data against a golden file, optionally updating it."""
    golden_file = golden_dir / f"{name}.json"
    serialized = json.dumps(data, indent=2, sort_keys=True)

    if update or not golden_file.exists():
        golden_file.write_text(serialized + "\n")
        return

    expected = golden_file.read_text().strip()
    actual = serialized.strip()
    if actual != expected:
        # Write actual for diffing
        actual_file = golden_dir / f"{name}.actual.json"
        actual_file.write_text(serialized + "\n")
        pytest.fail(
            f"Golden file mismatch: {name}\n"
            f"  Expected: {golden_file}\n"
            f"  Actual:   {actual_file}\n"
            f"  Run with --update-golden to accept changes."
        )
