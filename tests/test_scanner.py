"""Tests for the enhanced scanner."""
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_discover_modules_finds_core_packages():
    from scripts.scanner import discover_modules
    modules = discover_modules()
    module_names = set(modules)
    assert any(m.startswith("google.adk.agents") for m in module_names)
    assert any(m.startswith("google.adk.events") for m in module_names)
    assert any(m.startswith("google.adk.sessions") for m in module_names)
    assert len(modules) > 50


def test_discover_modules_skips_broken_imports():
    from scripts.scanner import discover_modules
    modules = discover_modules()
    assert isinstance(modules, list)


def test_discover_classes_finds_core_classes():
    from scripts.scanner import discover_modules, discover_classes
    modules = discover_modules()
    class_tuples = discover_classes(modules)
    class_names = {cls.__name__ for cls, _ in class_tuples}
    assert "LlmAgent" in class_names
    assert "BaseAgent" in class_names
    assert "Event" in class_names


def test_scan_class_pydantic():
    from google.adk.agents import LlmAgent
    from scripts.scanner import scan_class
    info = scan_class(LlmAgent)
    assert info.is_pydantic is True
    assert info.inspection_mode == "pydantic"
    assert len(info.fields) > 10
    assert any(f.name == "instruction" for f in info.fields)


def test_scan_class_non_pydantic():
    from google.adk.runners import Runner
    from scripts.scanner import scan_class
    info = scan_class(Runner)
    assert info.is_pydantic is False
    assert info.inspection_mode == "init_signature"
    assert len(info.init_params) > 0


def test_scan_all_finds_many_classes():
    from scripts.scanner import scan_all
    manifest = scan_all()
    assert manifest.total_classes > 30
    class_names = {c.name for c in manifest.classes}
    assert "LlmAgent" in class_names
    assert "BaseAgent" in class_names


def test_scan_all_includes_non_pydantic():
    from scripts.scanner import scan_all
    manifest = scan_all()
    class_names = {c.name for c in manifest.classes}
    assert "Runner" in class_names
    runner = next(c for c in manifest.classes if c.name == "Runner")
    assert runner.inspection_mode == "init_signature"


def test_manifest_serialization():
    import json
    from scripts.scanner import scan_all, manifest_to_dict
    manifest = scan_all()
    data = manifest_to_dict(manifest)
    json_str = json.dumps(data, indent=2, default=str)
    assert len(json_str) > 1000
    parsed = json.loads(json_str)
    assert parsed["total_classes"] == manifest.total_classes
