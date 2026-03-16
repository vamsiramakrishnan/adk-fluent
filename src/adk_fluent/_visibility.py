"""Topology-inferred event visibility — backward-compatibility shim.

The canonical implementation now lives at ``adk_fluent.backends.adk._visibility_plugin``.
This module re-exports everything for backward compatibility.
"""

from adk_fluent.backends.adk._visibility_plugin import *  # noqa: F401,F403
from adk_fluent.backends.adk._visibility_plugin import (  # noqa: F401
    _ZERO_COST_TYPES,
    __all__,
    _walk,
)
