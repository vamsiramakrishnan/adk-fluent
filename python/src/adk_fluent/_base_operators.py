"""Operator-composition mixin for :class:`~adk_fluent._base.BuilderBase`.

Implements the expression language — ``>>`` (sequential), ``|`` (parallel),
``*`` (loop), ``@`` (structured output), ``//`` (fallback) — plus the
operator-support helpers (``_fork_for_operator``, ``_apply_context_transform``,
``_merge_middlewares``). Split out of ``_base.py`` so the core builder class
stays focused on the fluent chain.

Note on the ``isinstance(..., OperatorsMixin)`` checks: ``OperatorsMixin`` is
mixed into ``BuilderBase`` and nothing else, so testing against it is exactly
equivalent to testing against ``BuilderBase`` — but it avoids an import cycle
(``_base`` imports this module to compose the class). The two module-level
helpers this block needs (``_propagate_middlewares``, ``_UntilSpec``) are
imported lazily for the same reason.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

if TYPE_CHECKING:
    from adk_fluent._base import BuilderBase  # noqa: F401


class OperatorsMixin:
    """Expression-operator surface (``>>`` ``|`` ``*`` ``@`` ``//``) for builders."""

    @staticmethod
    def _merge_middlewares(left: BuilderBase, right: Any) -> list:
        """Merge middleware lists from two builder operands (deduplicating)."""
        merged = list(getattr(left, "_middlewares", []))
        other_mw = getattr(right, "_middlewares", []) if isinstance(right, OperatorsMixin) else []
        for mw in other_mw:
            if mw not in merged:
                merged.append(mw)
        return merged

    def _fork_for_operator(self) -> Self:
        """Create an operator-safe fork. Shares sub-builders (safe: operators never mutate children)."""
        new = object.__new__(type(self))
        new._config = dict(self._config)
        new._callbacks = {k: list(v) for k, v in self._callbacks.items()}
        new._lists = {k: list(v) for k, v in self._lists.items()}
        mw = getattr(self, "_middlewares", None)
        if mw is not None:
            new._middlewares = list(mw)
        return new

    def _apply_context_transform(self, ctransform) -> BuilderBase:
        """Bind a C (context) transform to an Agent in a ``>>`` chain.

        A context transform has no standalone state effect; it shapes what an
        agent sees. In a mixed pipeline it therefore attaches to an adjacent
        Agent's ``.context()`` instead of becoming a pipeline step:

        - ``Agent >> C``      → that agent, configured with the context.
        - ``Pipeline >> C``   → the pipeline with its **last Agent step**
                                 reconfigured. Non-Agent trailing steps (S/A)
                                 are skipped to find the agent the context
                                 applies to.

        Raises ``TypeError`` when no Agent is available to receive the context
        (e.g. ``FanOut >> C`` or a pipeline ending in only S/A steps), pointing
        the user at the explicit ``.context()`` form.
        """
        from adk_fluent.workflow import Pipeline

        # Direct case: self is an Agent (exposes .context()).
        if hasattr(self, "context"):
            return self.context(ctransform)  # type: ignore[attr-defined]

        # Pipeline case: rebind the last Agent step's context.
        if isinstance(self, Pipeline):
            clone = self._fork_for_operator()
            steps = clone._lists.get("sub_agents", [])
            for i in range(len(steps) - 1, -1, -1):
                step = steps[i]
                if hasattr(step, "context"):
                    steps[i] = step.context(ctransform)  # type: ignore[attr-defined]
                    return clone

        raise TypeError(
            f"Cannot bind a context transform ({type(ctransform).__name__}) via >> here: "
            f"the left operand ({type(self).__name__}) has no Agent to receive it. "
            "A C transform configures an agent's context — place it adjacent to an "
            "Agent (e.g. C.window(n=5) >> Agent(...)), or use Agent(...).context(C...)."
        )

    def __rshift__(self, other) -> BuilderBase:
        """Create or extend a Pipeline: a >> b >> c.

        Accepts:
        - BuilderBase (agents, pipelines, etc.)
        - callable (pure function, wrapped as zero-cost step)
        - dict (shorthand for deterministic Route)
        - Route (deterministic branching)
        """
        self._freeze()
        from adk_fluent._context import CTransform
        from adk_fluent._primitive_builders import _fn_step
        from adk_fluent._routing import Route
        from adk_fluent.workflow import Pipeline

        # Cross-namespace: a C (context) transform binds to an Agent's context
        # rather than becoming a state step. ``Agent >> C`` configures that
        # agent; ``Pipeline >> C`` configures the pipeline's last Agent step.
        # (S and A transforms already flow through the callable / _artifact_op
        # paths below, producing FnStep / ArtifactAgent nodes.)
        if isinstance(other, CTransform):
            return self._apply_context_transform(other)

        # Callable operand: wrap as zero-cost FnStep
        if callable(other) and not isinstance(other, OperatorsMixin | Route | type):
            other = _fn_step(other)

        # Reject unsupported operands (e.g. raw types like int)
        if not isinstance(other, OperatorsMixin | Route | dict) and not hasattr(other, "build"):
            return NotImplemented

        # Dict operand: convert to deterministic Route
        if isinstance(other, dict):
            output_key = self._config.get("output_key")
            if not output_key:
                raise ValueError(
                    "Left side of >> dict must have .writes() set so the router knows which state key to check."
                )
            route = Route(output_key)
            for value, agent_builder in other.items():
                route.eq(value, agent_builder)
            other = route  # Fall through to Route handling

        # Route operand: store Route directly so to_ir() can produce RouteNode
        if isinstance(other, Route):
            my_name = self._config.get("name", "")
            p = Pipeline(f"{my_name}_routed")
            if isinstance(self, Pipeline):
                for item in self._lists.get("sub_agents", []):
                    p._lists["sub_agents"].append(item)
            else:
                p._lists["sub_agents"].append(self)
            p._lists["sub_agents"].append(other)  # Store Route directly
            # Propagate middleware from self to result
            self_mw = getattr(self, "_middlewares", [])
            if self_mw:
                p._middlewares = list(self_mw)
            return p

        my_name = self._config.get("name", "")
        other_name = other._config.get("name", "") if hasattr(other, "_config") else ""
        if isinstance(self, Pipeline):
            # Clone, then append — original Pipeline unchanged
            clone = self._fork_for_operator()
            clone.step(other)  # type: ignore[arg-type]  # accepts BuilderBase; auto-built at build()
            clone._config["name"] = f"{my_name}_then_{other_name}"
            result = clone
        else:
            name = f"{my_name}_then_{other_name}"
            p = Pipeline(name)
            p.step(self)  # type: ignore[arg-type]  # accepts BuilderBase; auto-built at build()
            p.step(other)  # type: ignore[arg-type]
            result = p

        # Propagate middleware from operands to result
        from adk_fluent._base import _propagate_middlewares

        _propagate_middlewares(self, other, result)
        return result

    def __rrshift__(self, other) -> BuilderBase:
        """Support callable >> agent syntax."""
        if callable(other) and not isinstance(other, OperatorsMixin | type):
            from adk_fluent._primitive_builders import _fn_step

            left = _fn_step(other)
            return left >> self
        return NotImplemented

    def __or__(self, other: BuilderBase) -> BuilderBase:
        """Create or extend a FanOut: a | b | c."""
        self._freeze()
        from adk_fluent.workflow import FanOut

        if not isinstance(other, OperatorsMixin):
            return NotImplemented

        my_name = self._config.get("name", "")
        other_name = other._config.get("name", "")
        if isinstance(self, FanOut):
            # Clone, then add branch — original FanOut unchanged
            clone = self._fork_for_operator()
            clone.branch(other)  # type: ignore[arg-type]  # accepts BuilderBase; auto-built at build()
            clone._config["name"] = f"{my_name}_and_{other_name}"
            result = clone
        else:
            name = f"{my_name}_and_{other_name}"
            f = FanOut(name)
            f.branch(self)  # type: ignore[arg-type]  # accepts BuilderBase; auto-built at build()
            f.branch(other)  # type: ignore[arg-type]
            result = f

        # Propagate middleware from operands to result
        from adk_fluent._base import _propagate_middlewares

        _propagate_middlewares(self, other, result)
        return result

    def __mul__(self, other) -> BuilderBase:
        """Create a Loop: agent * 3 or agent * until(pred)."""
        self._freeze()
        from adk_fluent._base import _UntilSpec
        from adk_fluent.workflow import Loop, Pipeline

        # Handle until() spec: agent * until(pred)
        if isinstance(other, _UntilSpec):
            loop = self.__mul__(other.max)
            loop._config["_until_predicate"] = other.predicate
            return loop

        if not isinstance(other, int):
            return NotImplemented

        if other < 1:
            raise ValueError(
                f"Loop iterations must be >= 1, got {other}. "
                "Use agent * 3 for 3 iterations or agent * until(pred) for conditional loops."
            )

        iterations = other
        my_name = self._config.get("name", "")
        name = f"{my_name}_x{iterations}"
        loop = Loop(name)
        loop._config["max_iterations"] = iterations
        if isinstance(self, Pipeline):
            # Move Pipeline's sub_agents into the Loop
            for item in self._lists.get("sub_agents", []):
                loop._lists["sub_agents"].append(item)
        else:
            loop.step(self)  # type: ignore[arg-type]  # accepts BuilderBase; auto-built at build()
        return loop

    def __rmul__(self, iterations: int) -> BuilderBase:
        """Support int * agent syntax."""
        return self.__mul__(iterations)

    def __matmul__(self, schema: type) -> BuilderBase:
        """Bind structured output schema: ``agent @ Schema``.

        Shorthand for ``.returns(Schema)``. Forces the LLM to respond
        with JSON matching this Pydantic model. The agent **cannot use
        tools** when this is set.

        Equivalent to ``.returns(Schema)`` or ``.output(Schema)``.
        """
        if not isinstance(schema, type):
            raise TypeError(
                f"agent @ X requires X to be a type (Pydantic model), got {type(schema).__name__}. "
                "Usage: agent @ MySchema"
            )
        self._freeze()
        clone = self._fork_for_operator()
        clone._config["_output_schema"] = schema
        return clone

    def __floordiv__(self, other) -> BuilderBase:
        """Create a fallback chain: agent_a // agent_b.

        Tries each agent in order. First success wins.
        """
        self._freeze()
        from adk_fluent._primitive_builders import _FallbackBuilder
        from adk_fluent._routing import _make_fallback_builder

        # Callable on right side: wrap it
        if callable(other) and not isinstance(other, OperatorsMixin | type):
            from adk_fluent._primitive_builders import _fn_step

            other = _fn_step(other)

        # Collect children from existing fallback chains
        children: list[Any] = []
        if isinstance(self, _FallbackBuilder):
            children.extend(getattr(self, "_children", []))
        else:
            children.append(self)
        if isinstance(other, _FallbackBuilder):
            children.extend(getattr(other, "_children", []))
        else:
            children.append(other)

        return _make_fallback_builder(children)
