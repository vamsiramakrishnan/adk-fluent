"""Minimal imports for most adk-fluent projects.

Usage::

    from adk_fluent.prelude import *

Exports Tier 1 (core builders) and Tier 2 (composition) names only.
For tools, configs, and services, import directly from ``adk_fluent``.
"""

from adk_fluent import Agent, C, FanOut, Loop, Pipeline, Prompt, Route, S

__all__ = ["Agent", "Pipeline", "FanOut", "Loop", "C", "S", "Route", "Prompt"]
