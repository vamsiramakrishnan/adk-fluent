#!/usr/bin/env python3
"""Measure adk-fluent build overhead vs native ADK construction.

Usage:
    python scripts/benchmark.py
"""

from __future__ import annotations

import sys
import timeit
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from google.adk.agents import LlmAgent  # noqa: E402

from adk_fluent import Agent  # noqa: E402


def fluent_build():
    Agent("bench", "gemini-2.5-flash").instruct("You are helpful.").build()


def native_build():
    LlmAgent(name="bench", model="gemini-2.5-flash", instruction="You are helpful.")


def main():
    n = 10_000
    native_time = timeit.timeit(native_build, number=n)
    fluent_time = timeit.timeit(fluent_build, number=n)

    print(f"Native ADK:  {native_time:.4f}s for {n:,} builds ({native_time / n * 1e6:.1f} \u00b5s/build)")
    print(f"adk-fluent:  {fluent_time:.4f}s for {n:,} builds ({fluent_time / n * 1e6:.1f} \u00b5s/build)")
    print(f"Overhead:    {(fluent_time - native_time) / n * 1e6:.1f} \u00b5s/build")
    print(f"Ratio:       {fluent_time / native_time:.2f}x")


if __name__ == "__main__":
    main()
