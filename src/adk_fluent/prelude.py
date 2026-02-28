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
from adk_fluent._base import until
from adk_fluent._enums import ExecutionMode, SessionStrategy
from adk_fluent._primitive_builders import dispatch, expect, gate, join, map_over, race, tap
from adk_fluent._primitives import get_execution_mode
from adk_fluent._transforms import STransform
from adk_fluent.middleware import DispatchLogMiddleware
from adk_fluent.patterns import (
    cascade,
    chain,
    conditional,
    fan_out_merge,
    map_reduce,
    review_loop,
    supervised,
)
from adk_fluent.source import Inbox, Source
from adk_fluent.stream import StreamRunner

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
    "dispatch",
    "join",
    "STransform",
    # Tier 4: Patterns
    "review_loop",
    "cascade",
    "chain",
    "fan_out_merge",
    "map_reduce",
    "conditional",
    "supervised",
    # Tier 5: Stream execution
    "Source",
    "Inbox",
    "StreamRunner",
    # Tier 6: Observability
    "DispatchLogMiddleware",
    "get_execution_mode",
    # Tier 7: Enums
    "SessionStrategy",
    "ExecutionMode",
]
