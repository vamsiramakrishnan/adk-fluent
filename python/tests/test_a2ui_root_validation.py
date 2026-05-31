"""Regression test: A2UI component validation requires EXACTLY one root.

PR #138 review (Codex P2): the validator accepted payloads with more than one
component whose id == "root" even though the contract/error require exactly
one, queuing ambiguous-root messages to the client.
"""

from types import SimpleNamespace

import pytest

pytest.importorskip("a2ui.adk.send_a2ui_to_client_toolset")

from a2ui.adk.send_a2ui_to_client_toolset import _validate_components  # noqa: E402

_ROOT_ERR = "exactly one component must have id == 'root'"


def _catalog(*kinds: str) -> SimpleNamespace:
    return SimpleNamespace(components={k: {} for k in kinds})


def test_single_root_accepted():
    errors = _validate_components([{"id": "root", "component": "Text"}], _catalog("Text"))
    assert not any("root" in e for e in errors)


def test_duplicate_root_rejected():
    comps = [
        {"id": "root", "component": "Text"},
        {"id": "root", "component": "Text"},
    ]
    errors = _validate_components(comps, _catalog("Text"))
    assert _ROOT_ERR in errors


def test_zero_root_rejected():
    errors = _validate_components([{"id": "body", "component": "Text"}], _catalog("Text"))
    assert _ROOT_ERR in errors
