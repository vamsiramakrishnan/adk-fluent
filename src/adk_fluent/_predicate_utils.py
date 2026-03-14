"""Shared predicate evaluation for P.when, S.when, C.when.

Single canonical implementation used by all composition namespaces.
M.when has its own evaluation path (execution mode checks, TraceContext
access) so it does not use this module.
"""

from __future__ import annotations

import logging
from typing import Any

__all__ = ["evaluate_predicate"]

_log = logging.getLogger(__name__)


def evaluate_predicate(
    predicate: Any,
    state: dict[str, Any],
    *,
    strict: bool = False,
) -> bool:
    """Evaluate a predicate against session state.

    Args:
        predicate: The predicate to evaluate. Accepts:
            - ``None`` → ``False``
            - ``str`` → state key check: ``bool(state.get(key))``
            - ``callable`` → ``bool(predicate(state))``  (catches exceptions)
            - anything else → ``bool(predicate)``
        state: The current session state dictionary.
        strict: If ``True``, raise :class:`~adk_fluent.PredicateError` on
            exceptions instead of silently returning ``False``. Enable via
            ``.debug()`` on builders.

    Returns:
        Boolean result of the predicate evaluation.

    Raises:
        PredicateError: If *strict* is ``True`` and the predicate raises.

    PredicateSchema classes work via the callable path since their
    metaclass defines ``__call__(cls, state) -> bool``.
    """
    if predicate is None:
        return False
    if isinstance(predicate, str):
        return bool(state.get(predicate))
    if callable(predicate):
        try:
            return bool(predicate(state))
        except Exception as exc:
            if strict:
                from adk_fluent._exceptions import PredicateError

                raise PredicateError(
                    predicate_repr=getattr(predicate, "__name__", repr(predicate)),
                    available_keys=sorted(state.keys()),
                    original=exc,
                ) from exc
            _log.warning(
                "Predicate %s raised %s; treating as False",
                getattr(predicate, "__name__", "?"),
                exc,
            )
            return False
    return bool(predicate)
