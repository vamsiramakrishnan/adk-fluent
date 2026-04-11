"""Python-to-TypeScript transpiler for adk-fluent agent definitions.

Converts Python fluent builder chains to equivalent TypeScript code.
Handles:
- Builder chains: Agent("x").instruct("y").tool(fn).build()
- Operators: >> → .then(), | → .parallel(), * → .times(), // → .fallback(), @ → .outputAs()
- Namespace calls: S.pick(), C.none(), P.role(), T.fn()
- Simple lambdas: lambda s: s["key"] == "done"

Does NOT handle:
- Arbitrary Python class definitions or business logic
- Pydantic model definitions
- Complex function bodies
"""

from .python_to_ts import transpile, transpile_file

__all__ = ["transpile", "transpile_file"]
