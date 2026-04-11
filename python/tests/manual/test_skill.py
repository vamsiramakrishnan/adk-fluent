"""Tests for Skill builder, parser, topology parser, and SkillRegistry."""

import textwrap
from pathlib import Path

import pytest

from adk_fluent._skill_parser import (
    parse_skill_file,
    parse_topology,
)
from adk_fluent._skill_registry import SkillRegistry
from adk_fluent.agent import Agent
from adk_fluent.skill import Skill

# ======================================================================
# Helpers — create skill files in tmp_path
# ======================================================================


def _write_skill(tmp_path: Path, name: str, content: str) -> Path:
    """Write a SKILL.md into tmp_path/<name>/SKILL.md and return the dir."""
    d = tmp_path / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(textwrap.dedent(content))
    return d


# ======================================================================
# Skill Parser Tests
# ======================================================================


class TestSkillParser:
    def test_parse_minimal_frontmatter(self, tmp_path):
        """Parse a skill file with only name and description."""
        d = _write_skill(
            tmp_path,
            "hello",
            """\
            ---
            name: hello
            description: A simple greeting skill.
            ---

            # Hello Skill
            Say hello to the user.
            """,
        )
        sd = parse_skill_file(d)
        assert sd.name == "hello"
        assert sd.description == "A simple greeting skill."
        assert sd.agents == []
        assert sd.topology is None
        assert "Hello Skill" in sd.body

    def test_parse_agents_block(self, tmp_path):
        """Parse agents: block with model, instruct, tools, writes."""
        d = _write_skill(
            tmp_path,
            "research",
            """\
            ---
            name: research
            description: Research skill
            agents:
              researcher:
                model: gemini-2.5-flash
                instruct: Research {topic}.
                tools: [web_search]
                writes: findings
              writer:
                model: gemini-2.5-pro
                instruct: Write about {findings}.
                reads: [findings]
                writes: report
            topology: researcher >> writer
            ---
            """,
        )
        sd = parse_skill_file(d)
        assert len(sd.agents) == 2
        assert sd.agents[0].name == "researcher"
        assert sd.agents[0].model == "gemini-2.5-flash"
        assert sd.agents[0].tools == ["web_search"]
        assert sd.agents[0].writes == "findings"
        assert sd.agents[1].name == "writer"
        assert sd.agents[1].reads == ["findings"]
        assert sd.topology == "researcher >> writer"

    def test_parse_no_agents_block(self, tmp_path):
        """Skills without agents: are documentation-only (no error)."""
        d = _write_skill(
            tmp_path,
            "docs-only",
            """\
            ---
            name: docs-only
            description: Just documentation.
            ---

            # Documentation Skill
            This is prose only.
            """,
        )
        sd = parse_skill_file(d)
        assert sd.name == "docs-only"
        assert sd.agents == []

    def test_parse_input_output_contract(self, tmp_path):
        """Parse input:/output: schema declarations."""
        d = _write_skill(
            tmp_path,
            "typed",
            """\
            ---
            name: typed
            description: Typed skill
            agents:
              worker:
                instruct: Do something.
            input:
              topic: str
              depth: int
            output:
              report: str
            ---
            """,
        )
        sd = parse_skill_file(d)
        assert sd.input_schema == {"topic": "str", "depth": "int"}
        assert sd.output_schema == {"report": "str"}

    def test_parse_eval_cases(self, tmp_path):
        """Parse eval: inline test cases."""
        d = _write_skill(
            tmp_path,
            "eval",
            """\
            ---
            name: eval-skill
            description: Skill with evals
            agents:
              helper:
                instruct: Help.
            eval:
              - prompt: "What is 2+2?"
                expect: "4"
              - prompt: "Hello"
                rubrics: ["Friendly"]
            ---
            """,
        )
        sd = parse_skill_file(d)
        assert len(sd.eval_cases) == 2
        assert sd.eval_cases[0]["prompt"] == "What is 2+2?"
        assert sd.eval_cases[0]["expect"] == "4"

    def test_parse_tags_as_list(self, tmp_path):
        """Tags can be a YAML list."""
        d = _write_skill(
            tmp_path,
            "tagged",
            """\
            ---
            name: tagged
            description: Tagged skill
            tags: [research, synthesis]
            ---
            """,
        )
        sd = parse_skill_file(d)
        assert sd.tags == ["research", "synthesis"]

    def test_parse_metadata(self, tmp_path):
        """Metadata dict is parsed."""
        d = _write_skill(
            tmp_path,
            "meta",
            """\
            ---
            name: meta
            description: Has metadata
            metadata:
              license: Apache-2.0
              author: test
            ---
            """,
        )
        sd = parse_skill_file(d)
        assert sd.metadata["license"] == "Apache-2.0"

    def test_parse_file_not_found(self):
        """Nonexistent path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            parse_skill_file("/nonexistent/path/SKILL.md")

    def test_parse_directory_with_skill_md(self, tmp_path):
        """Can parse by passing directory path."""
        d = _write_skill(
            tmp_path,
            "dir-test",
            """\
            ---
            name: dir-test
            description: Test.
            ---
            """,
        )
        sd = parse_skill_file(d)
        assert sd.name == "dir-test"

    def test_parse_reads_as_string(self, tmp_path):
        """reads: can be a single string (auto-wrapped to list)."""
        d = _write_skill(
            tmp_path,
            "reads-str",
            """\
            ---
            name: reads-str
            description: test
            agents:
              a:
                instruct: test
                reads: findings
            ---
            """,
        )
        sd = parse_skill_file(d)
        assert sd.agents[0].reads == ["findings"]


# ======================================================================
# Topology Expression Parser Tests
# ======================================================================


class TestTopologyParser:
    def test_pipeline(self):
        """a >> b >> c -> Pipeline with 3 steps."""
        names = ["a", "b", "c"]
        wire = parse_topology("a >> b >> c", names)
        agents = {n: Agent(n, "gemini-2.5-flash").instruct(f"I am {n}") for n in names}
        result = wire(agents)
        built = result.build()
        assert len(built.sub_agents) == 3

    def test_fanout(self):
        """a | b | c -> FanOut with 3 branches."""
        names = ["a", "b", "c"]
        wire = parse_topology("a | b | c", names)
        agents = {n: Agent(n, "gemini-2.5-flash").instruct(f"I am {n}") for n in names}
        result = wire(agents)
        built = result.build()
        assert len(built.sub_agents) == 3

    def test_loop(self):
        """a * 3 -> Loop with 3 iterations."""
        names = ["a"]
        wire = parse_topology("a * 3", names)
        agents = {n: Agent(n, "gemini-2.5-flash").instruct(f"I am {n}") for n in names}
        result = wire(agents)
        built = result.build()
        assert built.max_iterations == 3

    def test_mixed_pipeline_fanout(self):
        """a >> (b | c) >> d -> Pipeline with FanOut in middle."""
        names = ["a", "b", "c", "d"]
        wire = parse_topology("a >> (b | c) >> d", names)
        agents = {n: Agent(n, "gemini-2.5-flash").instruct(f"I am {n}") for n in names}
        result = wire(agents)
        built = result.build()
        # Should be a Pipeline with 3 steps: a, FanOut(b,c), d
        assert len(built.sub_agents) == 3

    def test_loop_in_pipeline(self):
        """(a >> b) * 3 -> Loop containing a Pipeline."""
        names = ["a", "b"]
        wire = parse_topology("(a >> b) * 3", names)
        agents = {n: Agent(n, "gemini-2.5-flash").instruct(f"I am {n}") for n in names}
        result = wire(agents)
        built = result.build()
        assert built.max_iterations == 3

    def test_invalid_name_raises(self):
        """Unknown agent name in topology raises ValueError."""
        with pytest.raises(ValueError, match="Unknown agent 'x'"):
            parse_topology("a >> x", ["a", "b"])

    def test_single_name(self):
        """Single agent name returns that agent directly."""
        wire = parse_topology("a", ["a"])
        agents = {"a": Agent("a", "gemini-2.5-flash").instruct("I am a")}
        result = wire(agents)
        built = result.build()
        assert built.name == "a"


# ======================================================================
# Skill Builder Tests
# ======================================================================


class TestSkillBuilder:
    def test_skill_init_parses_file(self, tmp_path):
        """Skill() parses SKILL.md and stores definition."""
        d = _write_skill(
            tmp_path,
            "test-init",
            """\
            ---
            name: test-init
            description: Test initialization.
            agents:
              helper:
                instruct: Help the user.
            ---
            """,
        )
        skill = Skill(d)
        assert skill._config["name"] == "test-init"

    def test_skill_build_single_agent(self, tmp_path):
        """Skill with one agent builds to LlmAgent."""
        d = _write_skill(
            tmp_path,
            "single",
            """\
            ---
            name: single
            description: Single agent skill.
            agents:
              helper:
                model: gemini-2.5-flash
                instruct: Help the user.
            ---
            """,
        )
        skill = Skill(d)
        built = skill.build()
        assert built.name == "helper"

    def test_skill_build_pipeline(self, tmp_path):
        """Skill with topology: a >> b builds to SequentialAgent."""
        d = _write_skill(
            tmp_path,
            "pipe",
            """\
            ---
            name: pipe
            description: Pipeline skill.
            agents:
              researcher:
                model: gemini-2.5-flash
                instruct: Research.
                writes: findings
              writer:
                model: gemini-2.5-flash
                instruct: Write about {findings}.
                reads: findings
            topology: researcher >> writer
            ---
            """,
        )
        skill = Skill(d)
        built = skill.build()
        assert len(built.sub_agents) == 2

    def test_skill_model_override(self, tmp_path):
        """Skill.model() overrides all agent models."""
        d = _write_skill(
            tmp_path,
            "override",
            """\
            ---
            name: override
            description: Override test.
            agents:
              a:
                model: gemini-2.5-flash
                instruct: Test.
            ---
            """,
        )
        skill = Skill(d).model("gemini-2.5-pro")
        built = skill.build()
        assert built.model == "gemini-2.5-pro"

    def test_skill_configure_specific_agent(self, tmp_path):
        """Skill.configure('name', ...) raises on invalid name."""
        d = _write_skill(
            tmp_path,
            "cfg",
            """\
            ---
            name: cfg
            description: Config test.
            agents:
              a:
                instruct: Test.
            ---
            """,
        )
        skill = Skill(d)
        with pytest.raises(ValueError, match="not found"):
            skill.configure("nonexistent", model="x")

    def test_skill_configure_valid_name(self, tmp_path):
        """Skill.configure() on a valid name succeeds."""
        d = _write_skill(
            tmp_path,
            "cfg2",
            """\
            ---
            name: cfg2
            description: Config test.
            agents:
              a:
                instruct: Test.
            ---
            """,
        )
        skill = Skill(d).configure("a", model="gemini-2.5-pro")
        built = skill.build()
        assert built.model == "gemini-2.5-pro"

    def test_skill_inject_tools(self, tmp_path):
        """Skill.inject(web_search=fn) resolves tool references."""

        def my_search(query: str) -> str:
            """Search for things."""
            return f"Results for {query}"

        d = _write_skill(
            tmp_path,
            "inject",
            """\
            ---
            name: inject
            description: Injection test.
            agents:
              researcher:
                instruct: Research.
                tools: [web_search]
            ---
            """,
        )
        skill = Skill(d).inject(web_search=my_search)
        built = skill.build()
        # The tool should be attached
        assert len(built.tools) > 0

    def test_skill_operators_rshift(self, tmp_path):
        """Skill >> Agent creates Pipeline (inherited from BuilderBase)."""
        d = _write_skill(
            tmp_path,
            "op_rshift",
            """\
            ---
            name: op_rshift
            description: Operator test.
            agents:
              a:
                instruct: Test.
            ---
            """,
        )
        pipeline = Skill(d) >> Agent("b", "gemini-2.5-flash").instruct("Test.")
        built = pipeline.build()
        assert len(built.sub_agents) == 2

    def test_skill_operators_or(self, tmp_path):
        """Skill | Agent creates FanOut."""
        d = _write_skill(
            tmp_path,
            "op_or",
            """\
            ---
            name: op_or
            description: Operator test.
            agents:
              a:
                instruct: Test.
            ---
            """,
        )
        fanout = Skill(d) | Agent("b", "gemini-2.5-flash").instruct("Test.")
        built = fanout.build()
        assert len(built.sub_agents) == 2

    def test_skill_describe_override(self, tmp_path):
        """Skill.describe() overrides description."""
        d = _write_skill(
            tmp_path,
            "desc",
            """\
            ---
            name: desc
            description: Original.
            agents:
              a:
                instruct: Test.
            ---
            """,
        )
        skill = Skill(d).describe("Overridden description")
        assert skill._config["description"] == "Overridden description"

    def test_skill_contract(self, tmp_path):
        """Skill.contract() returns input/output schema."""
        d = _write_skill(
            tmp_path,
            "contract",
            """\
            ---
            name: contract
            description: Contract test.
            agents:
              a:
                instruct: Test.
            input:
              topic: str
            output:
              report: str
            ---
            """,
        )
        skill = Skill(d)
        c = skill.contract()
        assert c["input"] == {"topic": "str"}
        assert c["output"] == {"report": "str"}

    def test_skill_topology_expr(self, tmp_path):
        """Skill.topology_expr() returns the raw expression."""
        d = _write_skill(
            tmp_path,
            "topo",
            """\
            ---
            name: topo
            description: Topology test.
            agents:
              a:
                instruct: A.
              b:
                instruct: B.
            topology: a >> b
            ---
            """,
        )
        skill = Skill(d)
        assert skill.topology_expr() == "a >> b"

    def test_skill_build_no_agents_raises(self, tmp_path):
        """Building a documentation-only skill raises ValueError."""
        d = _write_skill(
            tmp_path,
            "no-agents",
            """\
            ---
            name: no-agents
            description: Docs only.
            ---
            """,
        )
        with pytest.raises(ValueError, match="no agents"):
            Skill(d).build()

    def test_skill_default_pipeline(self, tmp_path):
        """Multiple agents without topology default to pipeline."""
        d = _write_skill(
            tmp_path,
            "default_pipe",
            """\
            ---
            name: default_pipe
            description: Default pipeline.
            agents:
              a:
                instruct: A.
              b:
                instruct: B.
              c:
                instruct: C.
            ---
            """,
        )
        skill = Skill(d)
        built = skill.build()
        # Should be a Pipeline (SequentialAgent) with 3 sub_agents
        assert len(built.sub_agents) == 3

    def test_skill_fanout_topology(self, tmp_path):
        """Skills with fanout topology."""
        d = _write_skill(
            tmp_path,
            "fanout",
            """\
            ---
            name: fanout
            description: Fanout skill.
            agents:
              web:
                instruct: Search web.
              papers:
                instruct: Search papers.
            topology: web | papers
            ---
            """,
        )
        built = Skill(d).build()
        assert len(built.sub_agents) == 2


# ======================================================================
# Skill Registry Tests
# ======================================================================


class TestSkillRegistry:
    def test_registry_discovers_skills(self, tmp_path):
        """SkillRegistry scans directory for SKILL.md files."""
        _write_skill(tmp_path, "a", "---\nname: a\ndescription: Skill A.\n---\n")
        _write_skill(tmp_path, "b", "---\nname: b\ndescription: Skill B.\n---\n")
        reg = SkillRegistry(tmp_path)
        assert len(reg) == 2

    def test_registry_find_by_tags(self, tmp_path):
        """registry.find(tags=['research']) filters by tags."""
        _write_skill(
            tmp_path,
            "research",
            """\
            ---
            name: research
            description: Research skill.
            tags: [research, web]
            agents:
              a:
                instruct: Test.
            ---
            """,
        )
        _write_skill(
            tmp_path,
            "coding",
            """\
            ---
            name: coding
            description: Coding skill.
            tags: [coding]
            agents:
              b:
                instruct: Test.
            ---
            """,
        )
        reg = SkillRegistry(tmp_path)
        found = reg.find(tags=["research"])
        assert len(found) == 1
        assert found[0]._config["name"] == "research"

    def test_registry_find_by_name(self, tmp_path):
        """registry.find(name=...) substring matches."""
        _write_skill(tmp_path, "deep-research", "---\nname: deep-research\ndescription: test.\n---\n")
        _write_skill(tmp_path, "quick-research", "---\nname: quick-research\ndescription: test.\n---\n")
        _write_skill(tmp_path, "coding", "---\nname: coding\ndescription: test.\n---\n")
        reg = SkillRegistry(tmp_path)
        found = reg.find(name="research")
        assert len(found) == 2

    def test_registry_list_all(self, tmp_path):
        """registry.list() returns all skill metadata."""
        _write_skill(tmp_path, "a", "---\nname: a\ndescription: A.\ntags: [x]\n---\n")
        reg = SkillRegistry(tmp_path)
        items = reg.list()
        assert len(items) == 1
        assert items[0]["name"] == "a"
        assert items[0]["tags"] == ["x"]
        assert items[0]["has_agents"] is False

    def test_registry_get_by_name(self, tmp_path):
        """registry.get('name') returns Skill builder."""
        _write_skill(
            tmp_path,
            "hello",
            """\
            ---
            name: hello
            description: Hello.
            agents:
              greeter:
                instruct: Say hello.
            ---
            """,
        )
        reg = SkillRegistry(tmp_path)
        skill = reg.get("hello")
        assert isinstance(skill, Skill)
        assert skill._config["name"] == "hello"

    def test_registry_get_not_found(self, tmp_path):
        """registry.get() raises KeyError for unknown skill."""
        _write_skill(tmp_path, "a", "---\nname: a\ndescription: A.\n---\n")
        reg = SkillRegistry(tmp_path)
        with pytest.raises(KeyError, match="not found"):
            reg.get("nonexistent")

    def test_registry_empty_directory(self, tmp_path):
        """Empty directory produces empty registry."""
        reg = SkillRegistry(tmp_path)
        assert len(reg) == 0

    def test_registry_contains(self, tmp_path):
        """in operator works on registry."""
        _write_skill(tmp_path, "a", "---\nname: a\ndescription: A.\n---\n")
        reg = SkillRegistry(tmp_path)
        assert "a" in reg
        assert "b" not in reg

    def test_registry_names(self, tmp_path):
        """registry.names() returns sorted list."""
        _write_skill(tmp_path, "b", "---\nname: b\ndescription: B.\n---\n")
        _write_skill(tmp_path, "a", "---\nname: a\ndescription: A.\n---\n")
        reg = SkillRegistry(tmp_path)
        assert reg.names() == ["a", "b"]
