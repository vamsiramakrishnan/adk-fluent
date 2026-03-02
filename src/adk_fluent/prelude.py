"""Minimal imports for most adk-fluent projects.

Usage::

    from adk_fluent.prelude import *

Exports:

- **Tier 1 (core builders):** Agent, Pipeline, FanOut, Loop
- **Tier 2 (composition namespaces):** C, P, S, M, Route
- **Tier 3 (expression primitives):** until, tap, map_over, gate, race, expect
- **Tier 4 (patterns):** review_loop, cascade, chain, fan_out_merge,
  map_reduce, conditional, supervised

For tools, configs, and services, import directly from ``adk_fluent``.
"""

from adk_fluent import Agent, C, FanOut, Loop, P, Pipeline, Route, S
from adk_fluent._artifact_schema import ArtifactSchema, Consumes, Produces
from adk_fluent._artifacts import A, ATransform
from adk_fluent._base import until
from adk_fluent._enums import ExecutionMode, SessionStrategy
from adk_fluent._eval import (
    ComparisonReport,
    ComparisonSuite,
    E,
    ECase,
    EComposite,
    ECriterion,
    EPersona,
    EvalReport,
    EvalSuite,
)
from adk_fluent._middleware import M
from adk_fluent._middleware_schema import MiddlewareSchema
from adk_fluent._primitive_builders import dispatch, expect, gate, join, map_over, race, tap
from adk_fluent._primitives import get_execution_mode
from adk_fluent._routing import Fallback
from adk_fluent._tool_registry import SearchToolset, ToolRegistry, search_aware_after_tool
from adk_fluent._tools import T, TComposite
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
    "Fallback",
    # Tier 2: Composition namespaces
    "A",
    "ATransform",
    "C",
    "E",
    "EComposite",
    "ECase",
    "ECriterion",
    "EvalSuite",
    "EvalReport",
    "ComparisonReport",
    "ComparisonSuite",
    "EPersona",
    "P",
    "S",
    "M",
    "T",
    "TComposite",
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
    # Tier 8: Schemas
    "MiddlewareSchema",
    "ArtifactSchema",
    "Produces",
    "Consumes",
    # Tier 9: Tool registry
    "ToolRegistry",
    "SearchToolset",
    "search_aware_after_tool",
]
