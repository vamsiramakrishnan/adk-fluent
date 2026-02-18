"""Resource dependency injection for tool functions."""
from __future__ import annotations

import functools
import inspect
from typing import Any, Callable


def inject_resources(fn: Callable, resources: dict[str, Any]) -> Callable:
    """Wrap a tool function with resource injection.

    Resource parameters are removed from __signature__ so ADK's
    FunctionTool excludes them from the LLM schema. At call time,
    the resources are injected as keyword arguments.

    Args:
        fn: The tool function to wrap.
        resources: Mapping of parameter name -> value to inject.

    Returns:
        Wrapped function with modified signature.
    """
    sig = inspect.signature(fn)
    resource_params = {
        name for name in sig.parameters
        if name in resources and name != "tool_context"
    }

    if not resource_params:
        return fn

    is_async = inspect.iscoroutinefunction(fn)

    @functools.wraps(fn)
    async def wrapped(**kwargs):
        kwargs.update({k: resources[k] for k in resource_params if k not in kwargs})
        if is_async:
            return await fn(**kwargs)
        return fn(**kwargs)

    new_params = [p for name, p in sig.parameters.items() if name not in resource_params]
    wrapped.__signature__ = sig.replace(parameters=new_params)
    return wrapped
