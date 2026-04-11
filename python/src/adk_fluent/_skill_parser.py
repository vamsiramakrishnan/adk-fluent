"""Skill file parser — reads SKILL.md files with YAML frontmatter.

Parses the agentskills.io format extended with ``agents:``, ``topology:``,
``input:``, ``output:``, and ``eval:`` blocks for adk-fluent runtime use.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "AgentDefinition",
    "SkillDefinition",
    "parse_skill_file",
    "parse_topology",
]


# ======================================================================
# Data classes
# ======================================================================


@dataclass(frozen=True, slots=True)
class AgentDefinition:
    """A single agent parsed from the ``agents:`` block."""

    name: str
    model: str | None = None
    instruct: str = ""
    tools: list[str] = field(default_factory=list)
    reads: list[str] = field(default_factory=list)
    writes: str | None = None
    context: str | None = None
    describe: str | None = None


@dataclass(frozen=True, slots=True)
class SkillDefinition:
    """Complete parsed skill definition from a SKILL.md file."""

    name: str
    description: str = ""
    version: str | None = None
    tags: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    agents: list[AgentDefinition] = field(default_factory=list)
    topology: str | None = None
    input_schema: dict[str, str] = field(default_factory=dict)
    output_schema: dict[str, str] = field(default_factory=dict)
    eval_cases: list[dict[str, Any]] = field(default_factory=list)
    body: str = ""
    path: Path | None = None


# ======================================================================
# YAML frontmatter parser
# ======================================================================

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split YAML frontmatter from markdown body.

    Returns ``(frontmatter_dict, body_text)``.
    If no frontmatter is found, returns ``({}, full_text)``.
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text

    import yaml

    raw_yaml = m.group(1)
    body = m.group(2)

    try:
        fm = yaml.safe_load(raw_yaml)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML frontmatter: {exc}") from exc

    if not isinstance(fm, dict):
        return {}, text

    return fm, body


def _parse_agent_def(name: str, raw: dict[str, Any]) -> AgentDefinition:
    """Parse a single agent entry from the ``agents:`` block."""
    reads = raw.get("reads", [])
    if isinstance(reads, str):
        reads = [reads]
    tools = raw.get("tools", [])
    if isinstance(tools, str):
        tools = [tools]

    return AgentDefinition(
        name=name,
        model=raw.get("model"),
        instruct=str(raw.get("instruct", "")),
        tools=tools,
        reads=reads,
        writes=raw.get("writes"),
        context=raw.get("context"),
        describe=raw.get("describe"),
    )


def parse_skill_file(path: str | Path) -> SkillDefinition:
    """Parse a SKILL.md file into a :class:`SkillDefinition`.

    Parameters
    ----------
    path:
        Path to a SKILL.md file, or a directory containing one.
    """
    p = Path(path)
    if p.is_dir():
        p = p / "SKILL.md"
    if not p.exists():
        raise FileNotFoundError(f"Skill file not found: {p}")

    text = p.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)

    # Standard agentskills.io fields
    name = fm.get("name", p.parent.name)
    description = fm.get("description", "")
    version = fm.get("version")
    tags = fm.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",")]
    allowed_tools_raw = fm.get("allowed-tools", "")
    if isinstance(allowed_tools_raw, str):
        allowed_tools = [t.strip() for t in allowed_tools_raw.split(",") if t.strip()]
    else:
        allowed_tools = list(allowed_tools_raw or [])
    metadata = fm.get("metadata", {}) or {}

    # Extended adk-fluent fields
    agents_raw = fm.get("agents", {}) or {}
    agents = [_parse_agent_def(aname, adef) for aname, adef in agents_raw.items()]

    topology = fm.get("topology")
    input_schema = fm.get("input", {}) or {}
    output_schema = fm.get("output", {}) or {}
    eval_cases = fm.get("eval", []) or []

    return SkillDefinition(
        name=name,
        description=description,
        version=version,
        tags=tags,
        allowed_tools=allowed_tools,
        metadata=metadata,
        agents=agents,
        topology=topology,
        input_schema=input_schema,
        output_schema=output_schema,
        eval_cases=eval_cases,
        body=body,
        path=p,
    )


# ======================================================================
# Topology expression parser
# ======================================================================

# Tokens: NAME, INT, >>, |, *, (, )
_TOKEN_RE = re.compile(
    r"""
    \s*                      # skip whitespace
    (?:
        (>>)               | # pipeline operator
        (\|)               | # fanout operator
        (\*)               | # loop operator
        (\()               | # open paren
        (\))               | # close paren
        (\d+)              | # integer
        ([a-zA-Z_]\w*)       # name
    )
    """,
    re.VERBOSE,
)


def _tokenize(expr: str) -> list[tuple[str, str]]:
    """Tokenize a topology expression string.

    Returns list of ``(type, value)`` tuples.
    Types: ``PIPE``, ``FANOUT``, ``LOOP``, ``LPAREN``, ``RPAREN``, ``INT``, ``NAME``.
    """
    tokens: list[tuple[str, str]] = []
    pos = 0
    while pos < len(expr):
        m = _TOKEN_RE.match(expr, pos)
        if not m:
            ch = expr[pos]
            if ch.isspace():
                pos += 1
                continue
            raise ValueError(f"Unexpected character {ch!r} at position {pos} in topology: {expr!r}")
        if m.group(1):
            tokens.append(("PIPE", ">>"))
        elif m.group(2):
            tokens.append(("FANOUT", "|"))
        elif m.group(3):
            tokens.append(("LOOP", "*"))
        elif m.group(4):
            tokens.append(("LPAREN", "("))
        elif m.group(5):
            tokens.append(("RPAREN", ")"))
        elif m.group(6):
            tokens.append(("INT", m.group(6)))
        elif m.group(7):
            tokens.append(("NAME", m.group(7)))
        pos = m.end()
    return tokens


def parse_topology(expr: str, agent_names: list[str]) -> Any:
    """Parse a topology expression and return a builder-wiring function.

    Parameters
    ----------
    expr:
        Topology expression, e.g. ``"a >> b >> c"``, ``"a | b"``,
        ``"(a >> b) * 3"``.
    agent_names:
        Valid agent names from the ``agents:`` block.

    Returns
    -------
    A callable ``fn(builders: dict[str, BuilderBase]) -> BuilderBase``
    that, given a dict mapping agent names to their builders, wires them
    into the composed topology.

    Grammar (precedence low→high)::

        expr      → fanout
        fanout    → pipeline ( "|" pipeline )*
        pipeline  → loop ( ">>" loop )*
        loop      → atom ( "*" INT )?
        atom      → NAME | "(" expr ")"
    """
    tokens = _tokenize(expr)

    # Validate all names
    name_set = set(agent_names)
    for ttype, tval in tokens:
        if ttype == "NAME" and tval not in name_set:
            raise ValueError(
                f"Unknown agent '{tval}' in topology expression. Available agents: {', '.join(sorted(name_set))}"
            )

    pos = 0

    def peek() -> tuple[str, str] | None:
        nonlocal pos
        return tokens[pos] if pos < len(tokens) else None

    def consume(expected_type: str | None = None) -> tuple[str, str]:
        nonlocal pos
        if pos >= len(tokens):
            raise ValueError(f"Unexpected end of topology expression: {expr!r}")
        tok = tokens[pos]
        if expected_type and tok[0] != expected_type:
            raise ValueError(f"Expected {expected_type} but got {tok[0]}({tok[1]!r}) at position {pos} in: {expr!r}")
        pos += 1
        return tok

    def parse_expr():
        return parse_fanout()

    def parse_fanout():
        """fanout → pipeline ( "|" pipeline )*"""
        left = parse_pipeline()
        branches = [left]
        tok = peek()
        while tok is not None and tok[0] == "FANOUT":
            consume("FANOUT")
            branches.append(parse_pipeline())
            tok = peek()
        if len(branches) == 1:
            return branches[0]
        # Return a factory that creates FanOut
        return ("fanout", branches)

    def parse_pipeline():
        """pipeline → loop ( ">>" loop )*"""
        left = parse_loop()
        steps = [left]
        tok = peek()
        while tok is not None and tok[0] == "PIPE":
            consume("PIPE")
            steps.append(parse_loop())
            tok = peek()
        if len(steps) == 1:
            return steps[0]
        return ("pipeline", steps)

    def parse_loop():
        """loop → atom ( "*" INT )?"""
        node = parse_atom()
        tok = peek()
        if tok is not None and tok[0] == "LOOP":
            consume("LOOP")
            _, count_str = consume("INT")
            return ("loop", node, int(count_str))
        return node

    def parse_atom():
        """atom → NAME | "(" expr ")" """
        tok = peek()
        if not tok:
            raise ValueError(f"Unexpected end of topology expression: {expr!r}")
        if tok[0] == "NAME":
            _, name = consume("NAME")
            return ("name", name)
        if tok[0] == "LPAREN":
            consume("LPAREN")
            inner = parse_expr()
            consume("RPAREN")
            return inner
        raise ValueError(f"Unexpected token {tok[0]}({tok[1]!r}) in topology: {expr!r}")

    tree = parse_expr()
    if pos < len(tokens):
        raise ValueError(f"Unexpected token {tokens[pos][1]!r} after complete expression in: {expr!r}")

    def _build_from_tree(node, builders):
        """Recursively build adk-fluent builders from the parse tree."""
        from adk_fluent.workflow import FanOut, Loop, Pipeline

        if isinstance(node, tuple):
            kind = node[0]
            if kind == "name":
                return builders[node[1]]
            if kind == "pipeline":
                result = Pipeline("_topo_seq")
                for step in node[1]:
                    result = result.step(_build_from_tree(step, builders))
                return result
            if kind == "fanout":
                result = FanOut("_topo_par")
                for branch in node[1]:
                    result = result.branch(_build_from_tree(branch, builders))
                return result
            if kind == "loop":
                inner = _build_from_tree(node[1], builders)
                result = Loop("_topo_loop")
                result = result.step(inner).max_iterations(node[2])
                return result
        raise ValueError(f"Invalid topology parse tree node: {node!r}")

    def wire(builders: dict[str, Any]) -> Any:
        return _build_from_tree(tree, builders)

    return wire
