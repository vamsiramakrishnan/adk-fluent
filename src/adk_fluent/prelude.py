"""Minimal imports for most adk-fluent projects.

Usage::

    from adk_fluent.prelude import *

Exports:

- **Tier 1 (core builders):** Agent, Pipeline, FanOut, Loop
- **Tier 2 (composition namespaces):** C, P, S, Route
- **Tier 3 (expression primitives):** until, tap, map_over, gate, race, expect
- **Tier 4 (patterns):** review_loop, cascade, chain, fan_out_merge,
  map_reduce, conditional, supervised

For tools, configs, and services, import directly from ``adk_fluent``.
"""

from adk_fluent import Agent, C, FanOut, Loop, P, Pipeline, Route, S
from adk_fluent._base import expect, gate, map_over, race, tap, until
from adk_fluent._transforms import STransform
from adk_fluent.patterns import (
    cascade,
    chain,
    conditional,
    fan_out_merge,
    map_reduce,
    review_loop,
    supervised,
)

__all__ = [
    # Tier 1: Core builders
    "Agent",
    "Pipeline",
    "FanOut",
    "Loop",
    # Tier 2: Composition namespaces
    "C",
    "P",
    "S",
    "Route",
    # Tier 3: Expression primitives
    "until",
    "tap",
    "map_over",
    "gate",
    "race",
    "expect",
    "STransform",
    # Tier 4: Patterns
    "review_loop",
    "cascade",
    "chain",
    "fan_out_merge",
    "map_reduce",
    "conditional",
    "supervised",
]
