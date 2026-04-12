"""Issue #12 — CLI visualization tests."""

from __future__ import annotations

import sys
import types

from adk_fluent import Agent
from adk_fluent.cli import _MERMAID_HTML_TEMPLATE, _find_builders, main


class TestFindBuilders:
    """Auto-detection should find BuilderBase instances in modules."""

    def test_finds_builder_instances(self):
        mod = types.ModuleType("test_mod")
        mod.my_agent = Agent("test").model("gemini-2.0-flash").instruct("hi")
        mod.some_str = "not a builder"
        builders = _find_builders(mod)
        assert "my_agent" in builders
        assert "some_str" not in builders

    def test_skips_private_names(self):
        mod = types.ModuleType("test_mod")
        mod._private = Agent("hidden")
        builders = _find_builders(mod)
        assert "_private" not in builders


class TestHtmlWrapper:
    """HTML wrapper should contain mermaid source."""

    def test_html_contains_mermaid(self):
        html = _MERMAID_HTML_TEMPLATE.format(title="test", mermaid_source="graph LR\nA-->B")
        assert "mermaid" in html
        assert "graph LR" in html
        assert "A-->B" in html

    def test_html_has_cdn_script(self):
        html = _MERMAID_HTML_TEMPLATE.format(title="test", mermaid_source="graph LR")
        # Match the full script src so the check is anchored to the URL scheme
        # and host (avoids the CodeQL "incomplete URL substring sanitization"
        # warning that fires on bare substring checks like `"cdn.jsdelivr.net" in url`).
        assert 'src="https://cdn.jsdelivr.net/npm/mermaid@' in html


class TestCliMain:
    """CLI main() should handle --format mermaid."""

    def test_mermaid_format_outputs_text(self, capsys, tmp_path):
        # Create a temp module with a builder
        mod_file = tmp_path / "test_viz_mod.py"
        mod_file.write_text(
            "from adk_fluent import Agent\nmy_agent = Agent('viz_test').model('gemini-2.0-flash').instruct('hi')\n"
        )
        sys.path.insert(0, str(tmp_path))
        try:
            main(["visualize", "test_viz_mod", "--var", "my_agent", "--format", "mermaid"])
            captured = capsys.readouterr()
            assert "graph" in captured.out or "flowchart" in captured.out or "stateDiagram" in captured.out
        finally:
            sys.path.pop(0)
            sys.modules.pop("test_viz_mod", None)
