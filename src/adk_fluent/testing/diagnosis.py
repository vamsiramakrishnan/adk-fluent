"""Structured build-time diagnostics for adk-fluent pipelines.

Provides programmatic access to the same information as ``.explain()`` and
``check_contracts()``, returned as typed dataclasses for use in CI gates,
notebook widgets, IDE integrations, and test assertions.

Usage::

    from adk_fluent import Agent, S

    pipeline = (
        Agent("writer").instruct("Write.").outputs("draft")
        >> S.rename(draft="input")
        >> Agent("reviewer").instruct("Review the {input}.")
    )

    # Structured diagnostics
    diag = pipeline.diagnose()
    assert diag.ok  # no errors
    assert len(diag.data_flow) > 0

    # Formatted report
    pipeline.doctor()
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class AgentSummary:
    """Build-time summary of a single agent or node in the IR."""

    name: str
    node_type: str  # "AgentNode", "TransformNode", "CaptureNode", etc.
    model: str = ""
    instruction_preview: str = ""
    template_vars: list[str] = field(default_factory=list)
    reads_keys: list[str] = field(default_factory=list)
    writes_keys: list[str] = field(default_factory=list)
    output_key: str = ""
    context_description: str = ""
    tools: list[str] = field(default_factory=list)
    produces_type: str = ""
    consumes_type: str = ""


@dataclass
class KeyFlow:
    """A single state key flowing from producer to consumer."""

    key: str
    producer: str  # agent name
    consumers: list[str] = field(default_factory=list)  # agent names


@dataclass
class ContractIssue:
    """A single contract issue, structured for programmatic access."""

    level: Literal["error", "info"]
    agent: str
    message: str
    hint: str = ""
    pass_number: int = 0  # which pass detected this (0 = legacy string)


@dataclass
class Diagnosis:
    """Complete build-time diagnostic report for an IR tree.

    Attributes:
        agents: Summary of each agent/node in the tree.
        data_flow: State key flows between producers and consumers.
        issues: Contract issues (errors and advisories).
        topology: Mermaid source text for the graph.
        ok: True if no errors (info-level issues are fine).
        error_count: Number of error-level issues.
        info_count: Number of info-level issues.
    """

    agents: list[AgentSummary] = field(default_factory=list)
    data_flow: list[KeyFlow] = field(default_factory=list)
    issues: list[ContractIssue] = field(default_factory=list)
    topology: str = ""

    @property
    def ok(self) -> bool:
        """True if no error-level issues."""
        return all(i.level != "error" for i in self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.level == "error")

    @property
    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.level == "info")

    @property
    def errors(self) -> list[ContractIssue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[ContractIssue]:
        return [i for i in self.issues if i.level == "info"]


def _build_agent_summaries(ir_node: Any) -> list[AgentSummary]:
    """Walk the IR tree and build AgentSummary for each node."""
    from adk_fluent.testing.contracts import _context_description

    summaries: list[AgentSummary] = []

    def _walk(node: Any) -> None:
        name = getattr(node, "name", "?")
        node_type = type(node).__name__

        summary = AgentSummary(name=name, node_type=node_type)

        # Model
        model = getattr(node, "model", "")
        if model:
            summary.model = str(model)

        # Instruction
        instruction = getattr(node, "instruction", "")
        if isinstance(instruction, str) and instruction:
            preview = instruction[:80].replace("\n", " ")
            if len(instruction) > 80:
                preview += "..."
            summary.instruction_preview = preview

            template_vars = re.findall(r"\{(\w+)\??\}", instruction)
            summary.template_vars = template_vars

        # Data flow
        reads = getattr(node, "reads_keys", frozenset())
        summary.reads_keys = sorted(reads)

        writes = getattr(node, "writes_keys", frozenset())
        summary.writes_keys = sorted(writes)

        output_key = getattr(node, "output_key", None)
        if output_key:
            summary.output_key = output_key

        # Transform keys
        if node_type == "TransformNode":
            affected = getattr(node, "affected_keys", None)
            if affected:
                summary.writes_keys = sorted(affected)
            t_reads = getattr(node, "reads_keys", None)
            if t_reads is not None:
                summary.reads_keys = sorted(t_reads)

        # CaptureNode
        if node_type == "CaptureNode":
            capture_key = getattr(node, "key", "")
            summary.writes_keys = [capture_key] if capture_key else []

        # Context
        context_spec = getattr(node, "context_spec", None)
        if context_spec is not None:
            summary.context_description = _context_description(context_spec)
        else:
            include = getattr(node, "include_contents", "default")
            if include != "default":
                summary.context_description = f"include_contents='{include}'"

        # Tools
        tools = getattr(node, "tools", ())
        for t in tools:
            if hasattr(t, "name"):
                summary.tools.append(t.name)
            elif hasattr(t, "__name__"):
                summary.tools.append(t.__name__)
            else:
                summary.tools.append(type(t).__name__)

        # Type schemas
        produces = getattr(node, "produces_type", None)
        if produces:
            summary.produces_type = produces.__name__
        consumes = getattr(node, "consumes_type", None)
        if consumes:
            summary.consumes_type = consumes.__name__

        summaries.append(summary)

        # Recurse into children
        for child in getattr(node, "children", ()):
            _walk(child)

        # Body (MapOverNode, TimeoutNode)
        body = getattr(node, "body", None)
        if body is not None:
            _walk(body)

        # Rules (RouteNode)
        for _pred, agent_node in getattr(node, "rules", ()):
            _walk(agent_node)
        default = getattr(node, "default", None)
        if default is not None and not isinstance(default, str):
            _walk(default)

    _walk(ir_node)
    return summaries


def _build_data_flow(ir_node: Any) -> list[KeyFlow]:
    """Build data flow edges from the IR tree."""
    producers: dict[str, str] = {}  # key -> producer name
    consumers: dict[str, list[str]] = {}  # key -> [consumer names]

    def _walk(node: Any) -> None:
        name = getattr(node, "name", "?")
        node_type = type(node).__name__

        # What this node produces
        output_key = getattr(node, "output_key", None)
        if output_key:
            producers[output_key] = name

        if node_type == "CaptureNode":
            capture_key = getattr(node, "key", None)
            if capture_key:
                producers[capture_key] = name

        if node_type == "TransformNode":
            affected = getattr(node, "affected_keys", None)
            if affected:
                for key in affected:
                    producers[key] = name

        writes = getattr(node, "writes_keys", frozenset())
        for key in writes:
            producers[key] = name

        # What this node consumes
        instruction = getattr(node, "instruction", "")
        if isinstance(instruction, str) and instruction:
            template_vars = re.findall(r"\{(\w+)\??\}", instruction)
            for var in template_vars:
                consumers.setdefault(var, []).append(name)

        reads = getattr(node, "reads_keys", frozenset())
        for key in reads:
            consumers.setdefault(key, []).append(name)

        if node_type == "TransformNode":
            t_reads = getattr(node, "reads_keys", None)
            if t_reads is not None:
                for key in t_reads:
                    consumers.setdefault(key, []).append(name)

        if node_type == "RouteNode":
            route_key = getattr(node, "key", None)
            if route_key:
                consumers.setdefault(route_key, []).append(name)

        # Recurse
        for child in getattr(node, "children", ()):
            _walk(child)

    _walk(ir_node)

    # Build KeyFlow for all keys that have both producer and consumer
    flows: list[KeyFlow] = []
    all_keys = sorted(set(producers.keys()) | set(consumers.keys()))
    for key in all_keys:
        prod = producers.get(key, "")
        cons = consumers.get(key, [])
        flows.append(KeyFlow(key=key, producer=prod, consumers=cons))

    return flows


def _convert_issues(raw_issues: list) -> list[ContractIssue]:
    """Convert raw check_contracts output to structured ContractIssue list."""
    result = []
    for issue in raw_issues:
        if isinstance(issue, str):
            result.append(ContractIssue(level="error", agent="?", message=issue))
        elif isinstance(issue, dict):
            result.append(
                ContractIssue(
                    level=issue.get("level", "error"),
                    agent=issue.get("agent", "?"),
                    message=issue.get("message", "?"),
                    hint=issue.get("hint", ""),
                )
            )
    return result


def diagnose(ir_node: Any) -> Diagnosis:
    """Build a complete Diagnosis from an IR tree.

    This is the programmatic entry point — returns structured data
    instead of formatted text.
    """
    from adk_fluent.testing.contracts import check_contracts
    from adk_fluent.viz import ir_to_mermaid

    agents = _build_agent_summaries(ir_node)
    data_flow = _build_data_flow(ir_node)

    raw_issues = check_contracts(ir_node)
    issues = _convert_issues(raw_issues)

    topology = ir_to_mermaid(ir_node, show_contracts=True, show_data_flow=True)

    return Diagnosis(
        agents=agents,
        data_flow=data_flow,
        issues=issues,
        topology=topology,
    )


def format_diagnosis(diag: Diagnosis) -> str:
    """Format a Diagnosis into a human-readable report string.

    This powers the ``.doctor()`` method.
    """
    lines: list[str] = []
    width = 60

    # Header
    status = "OK" if diag.ok else f"ISSUES FOUND ({diag.error_count} errors, {diag.info_count} advisories)"
    lines.append(f"{'=' * width}")
    lines.append(f"  Pipeline Diagnosis: {status}")
    lines.append(f"{'=' * width}")
    lines.append("")

    # Agents section
    lines.append(f"  Agents ({len(diag.agents)}):")
    lines.append(f"  {'-' * (width - 4)}")
    for agent in diag.agents:
        node_label = agent.node_type.replace("Node", "")
        lines.append(f"  [{node_label}] {agent.name}")

        if agent.model:
            lines.append(f"    model: {agent.model}")
        if agent.instruction_preview:
            lines.append(f"    instruction: {agent.instruction_preview}")
        if agent.template_vars:
            lines.append(f"    template vars: {', '.join(agent.template_vars)}")
        if agent.reads_keys:
            lines.append(f"    reads: {', '.join(agent.reads_keys)}")
        if agent.writes_keys:
            lines.append(f"    writes: {', '.join(agent.writes_keys)}")
        if agent.output_key:
            lines.append(f"    output_key: {agent.output_key}")
        if agent.context_description:
            lines.append(f"    context: {agent.context_description}")
        if agent.tools:
            lines.append(f"    tools: {', '.join(agent.tools)}")
        if agent.produces_type:
            lines.append(f"    produces: {agent.produces_type}")
        if agent.consumes_type:
            lines.append(f"    consumes: {agent.consumes_type}")

    # Data flow section
    if diag.data_flow:
        lines.append("")
        active_flows = [f for f in diag.data_flow if f.producer and f.consumers]
        if active_flows:
            lines.append(f"  Data Flow ({len(active_flows)} keys):")
            lines.append(f"  {'-' * (width - 4)}")
            for flow in active_flows:
                cons_str = ", ".join(flow.consumers)
                lines.append(f"    {flow.producer} --[{flow.key}]--> {cons_str}")

        # Orphan keys (produced but not consumed, or consumed but not produced)
        orphan_produced = [f for f in diag.data_flow if f.producer and not f.consumers]
        orphan_consumed = [f for f in diag.data_flow if not f.producer and f.consumers]
        if orphan_produced:
            lines.append(f"  Orphan keys (produced, never consumed):")
            for flow in orphan_produced:
                lines.append(f"    {flow.producer} --[{flow.key}]--> (unused)")
        if orphan_consumed:
            lines.append(f"  Missing keys (consumed, never produced):")
            for flow in orphan_consumed:
                cons_str = ", ".join(flow.consumers)
                lines.append(f"    (missing) --[{flow.key}]--> {cons_str}")

    # Issues section
    if diag.issues:
        lines.append("")
        lines.append(f"  Issues ({len(diag.issues)}):")
        lines.append(f"  {'-' * (width - 4)}")
        for issue in diag.issues:
            marker = "ERROR" if issue.level == "error" else "INFO "
            lines.append(f"    [{marker}] {issue.agent}: {issue.message}")
            if issue.hint:
                lines.append(f"             Hint: {issue.hint}")

    lines.append("")
    lines.append(f"{'=' * width}")
    return "\n".join(lines)
