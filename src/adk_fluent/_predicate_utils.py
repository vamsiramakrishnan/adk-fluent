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


def evaluate_predicate(predicate: Any, state: dict[str, Any]) -> bool:
    """Evaluate a predicate against session state.

    Accepts:
        - ``None`` → ``False``
        - ``str`` → state key check: ``bool(state.get(key))``
        - ``callable`` → ``bool(predicate(state))``  (catches exceptions)
        - anything else → ``bool(predicate)``

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
        except Exception:
            _log.warning("Predicate raised an exception; treating as False")
            return False
    return bool(predicate)
