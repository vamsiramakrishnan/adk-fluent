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

        # Context — also extract reads_keys from context spec
        context_spec = getattr(node, "context_spec", None)
        if context_spec is not None:
            summary.context_description = _context_description(context_spec)
            # Extract keys from context spec (e.g., C.from_state("x", "y"))
            ctx_reads = getattr(context_spec, "_reads_keys", None)
            if ctx_reads is None and hasattr(context_spec, "keys"):
                ctx_reads = frozenset(context_spec.keys)
            if ctx_reads:
                # Merge with existing reads_keys (from schemas)
                existing = set(summary.reads_keys)
                existing.update(ctx_reads)
                summary.reads_keys = sorted(existing)
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


def _build_data_flow(ir_node: Any) -> tuple[list[KeyFlow], set[str]]:
    """Build data flow edges from the IR tree.

    Returns (flows, optional_keys) where optional_keys are template vars
    using the {var?} syntax.
    """
    producers: dict[str, str] = {}  # key -> producer name
    consumers: dict[str, list[str]] = {}  # key -> [consumer names]
    optional_keys: set[str] = set()  # keys from {var?} syntax

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
            # Capture (name, optional_marker) pairs
            template_matches = re.findall(r"\{(\w+)(\??)\}", instruction)
            for var, opt_marker in template_matches:
                consumers.setdefault(var, []).append(name)
                if opt_marker == "?":
                    optional_keys.add(var)

        reads = getattr(node, "reads_keys", frozenset())
        for key in reads:
            consumers.setdefault(key, []).append(name)

        # Context spec reads (e.g., .reads("key") → C.from_state("key"))
        context_spec = getattr(node, "context_spec", None)
        if context_spec is not None:
            ctx_reads = getattr(context_spec, "_reads_keys", None)
            if ctx_reads is None and hasattr(context_spec, "keys"):
                ctx_reads = frozenset(context_spec.keys)
            if ctx_reads:
                for key in ctx_reads:
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

    return flows, optional_keys


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
        else:
            # Unknown issue format — preserve as error
            result.append(ContractIssue(level="error", agent="?", message=str(issue)))
    return result


def _check_ui_issues(ir_node: Any) -> list[ContractIssue]:
    """Check for A2UI-related warnings in the IR tree."""
    issues: list[ContractIssue] = []

    def _walk(node: Any) -> None:
        name = getattr(node, "name", "?")
        node_type = type(node).__name__

        if node_type in ("AgentNode",):
            ui_spec = getattr(node, "ui_spec", None)
            if ui_spec is None:
                # Check config dict fallback
                config = getattr(node, "_config", {})
                ui_spec = config.get("_ui_spec") if isinstance(config, dict) else None

            if ui_spec is not None:
                from adk_fluent._ui import UISurface

                if isinstance(ui_spec, UISurface) and ui_spec.root is not None:
                    # Check for input fields without bindings
                    _check_bindings(ui_spec.root, name, issues)

        for child in getattr(node, "children", ()):
            _walk(child)

    def _check_bindings(component: Any, agent_name: str, issues: list) -> None:
        kind = getattr(component, "_kind", "")
        bindings = getattr(component, "_bindings", ())
        if kind in ("TextField", "DateTimeInput", "ChoicePicker", "Slider") and not bindings:
            label = ""
            for k, v in getattr(component, "_props", ()):
                if k == "label":
                    label = v
                    break
            issues.append(
                ContractIssue(
                    level="info",
                    agent=agent_name,
                    message=f"UI input '{label or kind}' has no data binding",
                    hint="Add bind='/path' to connect this field to the data model.",
                )
            )
        for child in getattr(component, "_children", ()):
            _check_bindings(child, agent_name, issues)

    _walk(ir_node)
    return issues


def _check_common_mistakes(
    ir_node: Any,
    agents: list[AgentSummary],
    data_flow: list[KeyFlow],
    optional_keys: set[str] | None = None,
) -> list[ContractIssue]:
    """Check for the top 13 most common mistakes users make.

    These are pragmatic checks that go beyond contract analysis to
    catch patterns that lead to silent failures or confusion.
    """
    if optional_keys is None:
        optional_keys = set()
    issues: list[ContractIssue] = []

    # 1. Agent with no model — will fail at runtime
    for summary in agents:
        if summary.node_type == "AgentNode" and not summary.model:
            issues.append(
                ContractIssue(
                    level="error",
                    agent=summary.name,
                    message="Agent has no model set",
                    hint="Add .model('gemini-2.5-flash') or pass model as second arg: Agent('name', 'gemini-2.5-flash')",
                )
            )

    # 2. Agent with no instruction — likely a mistake
    for summary in agents:
        if summary.node_type == "AgentNode" and not summary.instruction_preview:
            issues.append(
                ContractIssue(
                    level="info",
                    agent=summary.name,
                    message="Agent has no instruction set",
                    hint="Add .instruct('...') to tell the agent what to do.",
                )
            )

    # 3. Missing keys: consumed but never produced (elevated from data flow to explicit error)
    #    Skip optional template vars ({var?}) — they resolve to empty string at runtime
    for flow in data_flow:
        if not flow.producer and flow.consumers:
            if flow.key in optional_keys:
                continue  # optional vars are OK to be missing
            issues.append(
                ContractIssue(
                    level="error",
                    agent=flow.consumers[0],
                    message=f"Key '{flow.key}' is read but never produced by any upstream agent",
                    hint=f"Add .writes('{flow.key}') to the agent that should produce this value.",
                )
            )

    # 4. Orphan writes: produced but never consumed (might indicate stale config)
    for flow in data_flow:
        if flow.producer and not flow.consumers:
            # Only warn if it's an explicit output_key (not just an agent name)
            producer_summary = next((a for a in agents if a.name == flow.producer), None)
            if producer_summary and flow.key in producer_summary.writes_keys:
                issues.append(
                    ContractIssue(
                        level="info",
                        agent=flow.producer,
                        message=f"Key '{flow.key}' is written but never read by any downstream agent",
                        hint="Either add a consumer or remove .writes() if unneeded.",
                    )
                )

    # 5. Duplicate agent names in a composition
    name_counts: dict[str, int] = {}
    for summary in agents:
        name_counts[summary.name] = name_counts.get(summary.name, 0) + 1
    for name, count in name_counts.items():
        if count > 1 and name != "?":
            issues.append(
                ContractIssue(
                    level="error",
                    agent=name,
                    message=f"Agent name '{name}' appears {count} times in the pipeline",
                    hint="Agent names must be unique. Use different names for each agent.",
                )
            )

    # 6. Pipeline with single step — probably meant to use Agent directly
    node_type = type(ir_node).__name__
    children = getattr(ir_node, "children", ())
    if node_type == "SequenceNode" and len(children) == 1:
        issues.append(
            ContractIssue(
                level="info",
                agent=getattr(ir_node, "name", "?"),
                message="Pipeline has only one step — consider using the agent directly",
                hint="A single-step pipeline adds unnecessary wrapping.",
            )
        )

    # 7. FanOut with single branch
    if node_type == "ParallelNode" and len(children) == 1:
        issues.append(
            ContractIssue(
                level="info",
                agent=getattr(ir_node, "name", "?"),
                message="FanOut has only one branch — consider using the agent directly",
                hint="Parallel execution with one branch adds unnecessary overhead.",
            )
        )

    # 8. Loop with no exit condition (max_iterations only, no predicate)
    if node_type == "LoopNode":
        has_predicate = getattr(ir_node, "exit_predicate", None) is not None
        max_iter = getattr(ir_node, "max_iterations", 0)
        if not has_predicate and max_iter > 0:
            issues.append(
                ContractIssue(
                    level="info",
                    agent=getattr(ir_node, "name", "?"),
                    message=f"Loop runs exactly {max_iter} times with no exit condition",
                    hint="Consider adding .until(pred) for early termination when the goal is met.",
                )
            )

    # 9. Template var references a key that looks like a typo (close match)
    produced_keys = {f.key for f in data_flow if f.producer}
    for summary in agents:
        for var in summary.template_vars:
            if var not in produced_keys and produced_keys:
                # Find close matches
                close = [k for k in produced_keys if _is_close(var, k)]
                if close:
                    issues.append(
                        ContractIssue(
                            level="error",
                            agent=summary.name,
                            message=f"Template variable '{{{var}}}' not found — did you mean '{{{close[0]}}}'?",
                            hint=f"Available keys: {', '.join(sorted(produced_keys))}",
                        )
                    )

    # 10. Route node with no rules
    def _check_empty_routes(node: Any) -> None:
        if type(node).__name__ == "RouteNode":
            rules = getattr(node, "rules", ())
            if not rules:
                issues.append(
                    ContractIssue(
                        level="error",
                        agent=getattr(node, "name", "?"),
                        message="Route has no rules defined",
                        hint="Add at least one .eq(), .contains(), or .when() rule.",
                    )
                )
        for child in getattr(node, "children", ()):
            _check_empty_routes(child)

    _check_empty_routes(ir_node)

    # 11. .returns(Schema) + .tool() conflict — tools silently disabled
    def _check_schema_tool_conflict(node: Any) -> None:
        if type(node).__name__ == "AgentNode":
            has_schema = getattr(node, "output_schema", None) is not None
            has_tools = bool(getattr(node, "tools", ()))
            if has_schema and has_tools:
                issues.append(
                    ContractIssue(
                        level="error",
                        agent=getattr(node, "name", "?"),
                        message="Agent has both .returns(Schema) and tools — tools will be silently disabled",
                        hint="Remove .returns() to keep tools, or remove tools to use structured output. "
                        "ADK disables tools when output_schema is set.",
                    )
                )
        for child in getattr(node, "children", ()):
            _check_schema_tool_conflict(child)

    _check_schema_tool_conflict(ir_node)

    # 12. .reads() without .writes() upstream — explicit wiring gap
    #     (complements Pass 1 in contracts but gives better hint)
    all_writes = {f.key for f in data_flow if f.producer}
    for summary in agents:
        for key in summary.reads_keys:
            if key not in all_writes:
                # Don't duplicate if already caught by template var check
                already_caught = any(
                    key in i.message for i in issues if i.agent == summary.name and "template" in i.message.lower()
                )
                if not already_caught:
                    close = [k for k in all_writes if _is_close(key, k)]
                    hint = f"Add .writes('{key}') to the upstream agent."
                    if close:
                        hint = f"Did you mean .reads('{close[0]}')? " + hint
                    issues.append(
                        ContractIssue(
                            level="error",
                            agent=summary.name,
                            message=f".reads('{key}') but no upstream agent has .writes('{key}')",
                            hint=hint,
                        )
                    )

    # 13. Parallel branches writing to same state key
    def _check_parallel_writes(node: Any) -> None:
        if type(node).__name__ == "ParallelNode":
            write_keys: dict[str, list[str]] = {}  # key -> [agent names]
            for child in getattr(node, "children", ()):
                child_name = getattr(child, "name", "?")
                ok = getattr(child, "output_key", None)
                if ok:
                    write_keys.setdefault(ok, []).append(child_name)
            for key, writers in write_keys.items():
                if len(writers) > 1:
                    issues.append(
                        ContractIssue(
                            level="error",
                            agent=getattr(node, "name", "?"),
                            message=f"Parallel branches {', '.join(writers)} all write to '{key}' — last write wins, data lost",
                            hint="Use different .writes() keys for each branch, then merge with S.merge().",
                        )
                    )
        for child in getattr(node, "children", ()):
            _check_parallel_writes(child)

    _check_parallel_writes(ir_node)

    # 14. Workflow container with instruction/model/tools — these don't apply
    container_types = {"SequenceNode", "ParallelNode", "LoopNode"}

    def _check_container_misuse(node: Any) -> None:
        ntype = type(node).__name__
        if ntype in container_types:
            name = getattr(node, "name", "?")
            if getattr(node, "instruction", ""):
                issues.append(
                    ContractIssue(
                        level="error",
                        agent=name,
                        message=f".instruct() on a workflow container ({ntype}) has no effect",
                        hint="Move .instruct() to individual agents inside the pipeline/fanout/loop.",
                    )
                )
            if getattr(node, "model", ""):
                issues.append(
                    ContractIssue(
                        level="error",
                        agent=name,
                        message=f".model() on a workflow container ({ntype}) has no effect",
                        hint="Set .model() on individual agents, not on the pipeline/fanout/loop.",
                    )
                )
            if getattr(node, "tools", ()):
                issues.append(
                    ContractIssue(
                        level="error",
                        agent=name,
                        message=f".tool() on a workflow container ({ntype}) has no effect",
                        hint="Add .tool() to individual agents, not to the pipeline/fanout/loop.",
                    )
                )
        for child in getattr(node, "children", ()):
            _check_container_misuse(child)

    _check_container_misuse(ir_node)

    return issues


def _is_close(a: str, b: str) -> bool:
    """Simple edit distance check (1 edit away)."""
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(ca != cb for ca, cb in zip(a, b)) == 1
    # Check single insertion/deletion
    short, long = (a, b) if len(a) < len(b) else (b, a)
    diffs = 0
    si = li = 0
    while si < len(short) and li < len(long):
        if short[si] != long[li]:
            diffs += 1
            li += 1
        else:
            si += 1
            li += 1
    return diffs <= 1


def diagnose(ir_node: Any) -> Diagnosis:
    """Build a complete Diagnosis from an IR tree.

    This is the programmatic entry point — returns structured data
    instead of formatted text.
    """
    from adk_fluent.testing.contracts import check_contracts
    from adk_fluent.viz import ir_to_mermaid

    agents = _build_agent_summaries(ir_node)
    data_flow, optional_keys = _build_data_flow(ir_node)

    raw_issues = check_contracts(ir_node)
    issues = _convert_issues(raw_issues)

    # Add common mistake checks
    common_issues = _check_common_mistakes(ir_node, agents, data_flow, optional_keys)
    issues.extend(common_issues)

    # Add UI-specific warnings
    ui_issues = _check_ui_issues(ir_node)
    issues.extend(ui_issues)

    # Deduplicate issues (contract checker and common mistakes may overlap)
    seen: set[str] = set()
    unique_issues: list[ContractIssue] = []
    for issue in issues:
        key = f"{issue.agent}:{issue.message}"
        if key not in seen:
            seen.add(key)
            unique_issues.append(issue)

    topology = ir_to_mermaid(ir_node, show_contracts=True, show_data_flow=True)

    return Diagnosis(
        agents=agents,
        data_flow=data_flow,
        issues=unique_issues,
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
            lines.append("  Orphan keys (produced, never consumed):")
            for flow in orphan_produced:
                lines.append(f"    {flow.producer} --[{flow.key}]--> (unused)")
        if orphan_consumed:
            lines.append("  Missing keys (consumed, never produced):")
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
