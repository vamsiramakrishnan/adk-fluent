"""Operator mapping: Python operators → TypeScript method calls.

This maps Python's operator overloading syntax to TypeScript method names
since JavaScript/TypeScript does not support operator overloading.
"""

from __future__ import annotations

import ast

# Python AST operator class → (TS method name, description)
OPERATOR_MAP: dict[type, tuple[str, str]] = {
    ast.RShift: ("then", "sequential: a >> b → a.then(b)"),
    ast.BitOr: ("parallel", "parallel: a | b → a.parallel(b)"),
    ast.FloorDiv: ("fallback", "fallback: a // b → a.fallback(b)"),
    ast.MatMult: ("outputAs", "structured output: a @ Schema → a.outputAs(Schema)"),
    # Mult is special-cased: a * 3 → a.times(3), a * until(pred) → a.timesUntil(pred)
}

# Python snake_case method → TypeScript camelCase method
METHOD_NAME_MAP: dict[str, str] = {
    # Core configuration
    "instruct": "instruct",
    "describe": "describe",
    "model": "model",
    "static": "static_",
    "global_instruct": "globalInstruct",
    "generate_content_config": "generateContentConfig",
    # Data flow
    "reads": "reads",
    "writes": "writes",
    "returns": "returns",
    "accepts": "accepts",
    "produces": "produces",
    "consumes": "consumes",
    "context": "context",
    # Tools
    "tool": "tool",
    "tools": "tools",
    "delegate_to": "delegateTo",
    # Callbacks
    "before_agent": "beforeAgent",
    "after_agent": "afterAgent",
    "before_model": "beforeModel",
    "after_model": "afterModel",
    "before_tool": "beforeTool",
    "after_tool": "afterTool",
    "guard": "guard",
    "on_model_error": "onModelError",
    "on_tool_error": "onToolError",
    # Flow control
    "loop_until": "loopUntil",
    "loop_while": "loopWhile",
    "proceed_if": "proceedIf",
    "timeout": "timeout",
    "dispatch": "dispatch",
    # Transfer control
    "transfer_to": "transferTo",
    "isolate": "isolate",
    "stay": "stay",
    "no_peers": "noPeers",
    # Visibility
    "reveal": "reveal",
    "hide": "hide",
    "transparent": "transparent",
    # Configuration
    "middleware": "middleware",
    "inject": "inject",
    "use": "use",
    "native": "native",
    "debug": "debug",
    "checked": "checked",
    "strict": "strict",
    "unchecked": "unchecked",
    "prepend": "prepend",
    # Workflow
    "step": "step",
    "branch": "branch",
    "max_iterations": "maxIterations",
    # Execution
    "build": "build",
    "ask": "ask",
    "ask_async": "askAsync",
    "stream": "stream",
    "test": "test",
    "mock": "mock",
    "clone": "clone",
    # Introspection
    "explain": "explain",
    "validate": "validate",
    "to_ir": "toIr",
    "to_mermaid": "toMermaid",
    "inspect": "inspect",
    "data_flow": "dataFlow",
    # Namespace method names (S, C, P, T, G, M)
    "pick": "pick",
    "drop": "drop",
    "rename": "rename",
    "merge": "merge",
    "transform": "transform",
    "compute": "compute",
    "set": "set",
    "default": "default_",
    "guard_fn": "guard",
    "require": "require",
    "identity": "identity",
    "log": "log",
    # C namespace
    "none": "none",
    "user_only": "userOnly",
    "window": "window",
    "from_state": "fromState",
    "template": "template",
    "notes": "notes",
    "from_agents": "fromAgents",
    "exclude_agents": "excludeAgents",
    # P namespace
    "role": "role",
    "task": "task",
    "constraint": "constraint",
    "format": "format",
    "example": "example",
    "section": "section",
    # T namespace
    "fn": "fn",
    "agent": "agent",
    "google_search": "googleSearch",
    # M namespace
    "retry": "retry",
    "cost": "cost",
    "latency": "latency",
    "scope": "scope",
    "circuit_breaker": "circuitBreaker",
    "cache": "cache",
    "fallback_model": "fallbackModel",
}


def to_camel_case(name: str) -> str:
    """Convert snake_case to camelCase."""
    if name in METHOD_NAME_MAP:
        return METHOD_NAME_MAP[name]
    parts = name.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])
