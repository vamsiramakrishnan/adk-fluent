"""Tests for scripts/doc_generator.py — API reference, cookbook, and migration guide."""

import sys
import textwrap
from pathlib import Path

# Ensure scripts/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from doc_generator import (
    gen_api_reference_for_builder,
    gen_api_reference_module,
    gen_migration_guide,
    process_cookbook_file,
    cookbook_to_markdown,
)
from generator import BuilderSpec


# ---------------------------------------------------------------------------
# Fixtures (lightweight BuilderSpec instances for testing)
# ---------------------------------------------------------------------------

def _make_spec(**overrides) -> BuilderSpec:
    """Create a minimal BuilderSpec with sensible defaults."""
    defaults = dict(
        name="Agent",
        source_class="google.adk.agents.llm_agent.LlmAgent",
        source_class_short="LlmAgent",
        output_module="agent",
        doc="LLM-based Agent.",
        constructor_args=["name"],
        aliases={"instruct": "instruction", "describe": "description"},
        reverse_aliases={"instruction": "instruct", "description": "describe"},
        callback_aliases={"before_agent": "before_agent_callback"},
        skip_fields={"parent_agent", "name"},
        additive_fields={"before_agent_callback"},
        list_extend_fields={"tools", "sub_agents"},
        fields=[
            {"name": "name", "type_str": "str", "is_callback": False, "description": ""},
            {"name": "description", "type_str": "str", "is_callback": False, "description": ""},
            {"name": "instruction", "type_str": "str", "is_callback": True, "description": ""},
            {"name": "model", "type_str": "Union[str, BaseLlm]", "is_callback": False, "description": ""},
            {"name": "before_agent_callback", "type_str": "Callable", "is_callback": True, "description": ""},
            {"name": "parent_agent", "type_str": "Optional[BaseAgent]", "is_callback": False, "description": ""},
        ],
        terminals=[{"name": "build", "returns": "LlmAgent", "doc": "Resolve into a native ADK LlmAgent."}],
        extras=[
            {"name": "tool", "signature": "(self, fn_or_tool: Callable | BaseTool) -> Self",
             "doc": "Add a single tool.", "behavior": "list_append", "target_field": "tools"},
        ],
        is_composite=False,
        is_standalone=False,
        field_docs={},
        inspection_mode="pydantic",
        init_params=None,
    )
    defaults.update(overrides)
    return BuilderSpec(**defaults)


def _make_simple_spec() -> BuilderSpec:
    """Minimal spec with no aliases/callbacks."""
    return _make_spec(
        name="Runner",
        source_class="google.adk.runners.Runner",
        source_class_short="Runner",
        output_module="runtime",
        doc="The Runner class is used to run agents.",
        constructor_args=["session_service"],
        aliases={},
        reverse_aliases={},
        callback_aliases={},
        skip_fields={"session_service"},
        additive_fields=set(),
        list_extend_fields=set(),
        fields=[
            {"name": "session_service", "type_str": "BaseSessionService", "is_callback": False, "description": ""},
            {"name": "app_name", "type_str": "str", "is_callback": False, "description": ""},
        ],
        terminals=[{"name": "build", "returns": "Runner", "doc": "Resolve into a native ADK Runner."}],
        extras=[],
    )


# ---------------------------------------------------------------------------
# Tests: gen_api_reference_for_builder
# ---------------------------------------------------------------------------

class TestGenApiReferenceForBuilder:
    def test_header_contains_builder_name(self):
        spec = _make_spec()
        md = gen_api_reference_for_builder(spec)
        assert "# Agent" in md

    def test_header_contains_source_class(self):
        spec = _make_spec()
        md = gen_api_reference_for_builder(spec)
        assert "`google.adk.agents.llm_agent.LlmAgent`" in md

    def test_constructor_section(self):
        spec = _make_spec()
        md = gen_api_reference_for_builder(spec)
        assert "## Constructor" in md
        assert "| `name` |" in md

    def test_alias_methods_section(self):
        spec = _make_spec()
        md = gen_api_reference_for_builder(spec)
        assert "### Methods" in md
        assert ".instruct(value: str) -> Self" in md
        assert ".describe(value: str) -> Self" in md
        assert "`instruction`" in md

    def test_callback_section(self):
        spec = _make_spec()
        md = gen_api_reference_for_builder(spec)
        assert "### Callbacks" in md
        assert ".before_agent(*fns: Callable) -> Self" in md
        assert ".before_agent_if(condition: bool, fn: Callable) -> Self" in md

    def test_extra_methods_section(self):
        spec = _make_spec()
        md = gen_api_reference_for_builder(spec)
        assert "## Extra Methods" in md
        assert ".tool(" in md

    def test_terminal_methods_section(self):
        spec = _make_spec()
        md = gen_api_reference_for_builder(spec)
        assert "## Terminal Methods" in md
        assert ".build() -> LlmAgent" in md

    def test_forwarded_fields_section(self):
        spec = _make_spec()
        md = gen_api_reference_for_builder(spec)
        assert "## Forwarded Fields" in md
        # model should appear (not aliased, not skipped, not constructor)
        assert "`.model(value)`" in md

    def test_composite_builder_note(self):
        spec = _make_spec(is_composite=True, source_class="__composite__")
        md = gen_api_reference_for_builder(spec)
        assert "Composite builder" in md

    def test_standalone_builder_note(self):
        spec = _make_spec(is_standalone=True, source_class="__standalone__")
        md = gen_api_reference_for_builder(spec)
        assert "Standalone builder" in md

    def test_no_constructor_section_when_no_args(self):
        spec = _make_spec(constructor_args=[])
        md = gen_api_reference_for_builder(spec)
        # Constructor section should still not crash; may or may not appear
        # but the header should be present
        assert "# Agent" in md


# ---------------------------------------------------------------------------
# Tests: gen_api_reference_module
# ---------------------------------------------------------------------------

class TestGenApiReferenceModule:
    def test_module_header(self):
        spec = _make_spec()
        md = gen_api_reference_module([spec], "agent")
        assert "# Module: `agent`" in md

    def test_multiple_builders_separated(self):
        spec1 = _make_spec(name="Agent")
        spec2 = _make_simple_spec()
        md = gen_api_reference_module([spec1, spec2], "mixed")
        assert "# Agent" in md
        assert "# Runner" in md
        assert "---" in md


# ---------------------------------------------------------------------------
# Tests: process_cookbook_file
# ---------------------------------------------------------------------------

class TestProcessCookbookFile:
    def test_splits_on_markers(self, tmp_path):
        content = textwrap.dedent('''\
        """My Example Title"""

        # --- NATIVE ---
        native_code = 1

        # --- FLUENT ---
        fluent_code = 2

        # --- ASSERT ---
        assert True
        ''')
        f = tmp_path / "example.py"
        f.write_text(content)

        parsed = process_cookbook_file(str(f))
        assert parsed["title"] == "My Example Title"
        assert "native_code = 1" in parsed["native"]
        assert "fluent_code = 2" in parsed["fluent"]
        assert "assert True" in parsed["assertion"]
        assert parsed["filename"] == "example.py"

    def test_fallback_title(self, tmp_path):
        content = "# --- NATIVE ---\nx = 1\n"
        f = tmp_path / "no_docstring.py"
        f.write_text(content)

        parsed = process_cookbook_file(str(f))
        assert parsed["title"] == "no_docstring"

    def test_empty_sections(self, tmp_path):
        content = '"""Title"""\n'
        f = tmp_path / "empty.py"
        f.write_text(content)

        parsed = process_cookbook_file(str(f))
        assert parsed["native"] == ""
        assert parsed["fluent"] == ""
        assert parsed["assertion"] == ""


# ---------------------------------------------------------------------------
# Tests: cookbook_to_markdown
# ---------------------------------------------------------------------------

class TestCookbookToMarkdown:
    def test_produces_valid_markdown(self):
        parsed = {
            "title": "Simple Agent",
            "native": "from google.adk import Agent",
            "fluent": "from adk_fluent import Agent",
            "assertion": "assert True",
            "filename": "01_simple.py",
        }
        md = cookbook_to_markdown(parsed)

        assert "# Simple Agent" in md
        # New format uses sphinx-design tab-set instead of ## headers
        assert "tab-item} Native ADK" in md
        assert "tab-item} adk-fluent" in md
        assert "## Equivalence" in md
        assert "```python" in md
        assert "01_simple.py" in md

    def test_empty_sections_omitted(self):
        parsed = {
            "title": "Partial",
            "native": "code_here",
            "fluent": "",
            "assertion": "",
            "filename": "partial.py",
        }
        md = cookbook_to_markdown(parsed)

        assert "tab-item} Native ADK" in md
        assert "tab-item} adk-fluent" not in md
        assert "## Equivalence" not in md


# ---------------------------------------------------------------------------
# Tests: gen_migration_guide
# ---------------------------------------------------------------------------

class TestGenMigrationGuide:
    @staticmethod
    def _by_module(specs):
        """Build a by_module dict from a list of specs."""
        from collections import defaultdict
        bm = defaultdict(list)
        for s in specs:
            bm[s.output_module].append(s)
        return bm

    def test_class_mapping_table(self):
        specs = [_make_spec(), _make_simple_spec()]
        md = gen_migration_guide(specs, self._by_module(specs))

        assert "# Migration Guide" in md
        assert "## Class Mapping" in md
        # New format uses cross-ref links: [Agent](../api/agent.md#builder-Agent)
        assert "Agent" in md
        assert "Runner" in md
        assert "`from adk_fluent import Agent`" in md

    def test_field_mapping_table(self):
        specs = [_make_spec()]
        md = gen_migration_guide(specs, self._by_module(specs))

        assert "## Field Mappings" in md
        assert "### Agent" in md
        assert "| `instruction` | `.instruct()` | alias |" in md
        assert "| `before_agent_callback` | `.before_agent()` | callback, additive |" in md

    def test_no_field_mapping_for_no_aliases(self):
        specs = [_make_simple_spec()]
        md = gen_migration_guide(specs, self._by_module(specs))

        # Runner has no aliases, so it should not have a field mapping section
        assert "### Runner" not in md

    def test_composite_in_class_mapping(self):
        spec = _make_spec(name="Composite", is_composite=True, source_class="__composite__")
        md = gen_migration_guide([spec], self._by_module([spec]))
        assert "_(composite)_" in md
