"""Data flow interop — five orthogonal concerns, LLM call anatomy, build-time validation.

This module is the single source of truth for how the five orthogonal
data-flow concerns interact in adk-fluent. Every method that touches
data flow maps to exactly ONE concern:

==============  ==================  ========  ================================
Concern         Method(s)           Runtime?  What it controls
==============  ==================  ========  ================================
**CONTEXT**     ``.reads()``        YES       What state keys the agent SEES
                ``.context()``                in its prompt window.

**INPUT**       ``.accepts()``      YES       What structured data the agent
                ``.input_schema()``           ACCEPTS when used as a tool.

**OUTPUT**      ``.returns()``      YES       What SHAPE the LLM's response
                ``.output()``                 takes (plain text vs structured
                ``@ Model``                   JSON matching a Pydantic model).

**STORAGE**     ``.writes()``       YES       Where the agent's text response
                ``.save_as()``                is STORED in session state.

**CONTRACT**    ``.produces()``     NO        Annotation for the data-flow
                ``.consumes()``               contract CHECKER. No runtime
                                              effect whatsoever.
==============  ==================  ========  ================================


Default behavior when NOT set
-----------------------------

================  ===================================================================
Not set           Default
================  ===================================================================
No ``.reads()``   Agent sees FULL conversation history from all agents
No ``.accepts()`` Agent accepts any input when used as a tool (no validation)
No ``.returns()`` Agent responds in plain text and CAN use tools
No ``.writes()``  Response lives ONLY in conversation history, NOT in state
No ``.produces()``Contract checker treats writes as opaque (can't verify)
================  ===================================================================


Common confusion patterns
-------------------------

1. **``.returns()`` vs ``.writes()``** — These are INDEPENDENT.
   ``.returns(Model)`` constrains the LLM's response FORMAT.
   ``.writes(key)`` controls WHERE the response is STORED.
   You can use both, either, or neither.

2. **``.returns()`` vs ``.output_schema()``** — Nearly identical.
   ``.returns(Model)`` / ``.output(Model)`` sets ``_output_schema``
   → LLM constraint + ``.ask()`` parsing.
   ``.output_schema(Model)`` sets ``output_schema`` → LLM constraint only.
   **Prefer ``.returns()`` or ``@ Model``** for the common case.

3. **``.produces()`` vs ``.writes()``** — Different layers.
   ``.produces(Model)`` is a CONTRACT annotation with NO runtime effect.
   ``.writes(key)`` ACTUALLY stores data at runtime.

4. **``.reads()`` vs ``.consumes()``** — Different layers.
   ``.reads("key")`` ACTUALLY injects state values into the agent's context.
   ``.consumes(Model)`` is a CONTRACT annotation with NO runtime effect.

5. **``.accepts()`` vs ``.consumes()``** — Different layers.
   ``.accepts(Model)`` sets ADK's ``input_schema`` (tool-mode validation).
   ``.consumes(Model)`` is a CONTRACT annotation with NO runtime effect.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DataFlow:
    """Snapshot of a builder's five data-flow concerns.

    Returned by ``builder.data_flow()`` to show developers exactly
    what each concern is configured to.
    """

    sees: str
    """What context this agent sees (CONTEXT concern)."""

    accepts: str | None
    """What input schema this agent validates in tool mode (INPUT concern)."""

    stores: str | None
    """Where the response is stored in state (STORAGE concern)."""

    format: str
    """What shape the response takes (OUTPUT concern)."""

    contract_produces: str | None
    """What the contract checker knows about writes (CONTRACT concern)."""

    contract_consumes: str | None
    """What the contract checker knows about reads (CONTRACT concern)."""

    ui: str | None = None
    """UI surface info (UI concern) — mode and surface name if set."""

    def __str__(self) -> str:
        lines = ["Data Flow:"]
        lines.append(f"  reads:    {self.sees}")
        lines.append(f"  accepts:  {self.accepts or '(not set — accepts any input as tool)'}")
        lines.append(f"  returns:  {self.format}")
        lines.append(f"  writes:   {self.stores or '(not set — response only in conversation)'}")
        if self.contract_produces or self.contract_consumes:
            parts = []
            if self.contract_produces:
                parts.append(f"produces {self.contract_produces}")
            if self.contract_consumes:
                parts.append(f"consumes {self.contract_consumes}")
            lines.append(f"  contract: {', '.join(parts)}")
        else:
            lines.append("  contract: (not set)")
        if self.ui:
            lines.append(f"  ui:       {self.ui}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"DataFlow(sees={self.sees!r}, accepts={self.accepts!r}, "
            f"stores={self.stores!r}, format={self.format!r}, "
            f"contract_produces={self.contract_produces!r}, "
            f"contract_consumes={self.contract_consumes!r}, "
            f"ui={self.ui!r})"
        )


def _extract_data_flow(builder: Any) -> DataFlow:
    """Extract the DataFlow for a builder by inspecting its config."""
    config = getattr(builder, "_config", {})

    # CONTEXT concern
    context_spec = config.get("_context_spec")
    if context_spec is not None:
        from adk_fluent.testing.contracts import _context_description

        sees = _context_description(context_spec)
    else:
        sees = "full conversation history (default)"

    # INPUT concern
    input_schema = config.get("input_schema")
    if input_schema is not None:
        schema_name = getattr(input_schema, "__name__", str(input_schema))
        fields = list(input_schema.model_fields.keys()) if hasattr(input_schema, "model_fields") else []
        accepts_str = f"{schema_name}({', '.join(fields)})" if fields else schema_name
    else:
        accepts_str = None

    # STORAGE concern
    output_key = config.get("output_key")
    stores = f"state['{output_key}']" if output_key else None

    # OUTPUT concern
    output_schema = config.get("_output_schema") or config.get("output_schema")
    if output_schema is not None:
        schema_name = getattr(output_schema, "__name__", str(output_schema))
        format_str = f"structured JSON → {schema_name} (tools disabled)"
    else:
        format_str = "plain text (default — can use tools)"

    # CONTRACT concern
    produces = config.get("_produces")
    consumes = config.get("_consumes")
    contract_produces = None
    contract_consumes = None
    if produces is not None:
        fields = list(produces.model_fields.keys()) if hasattr(produces, "model_fields") else []
        contract_produces = f"{produces.__name__}({', '.join(fields)})"
    if consumes is not None:
        fields = list(consumes.model_fields.keys()) if hasattr(consumes, "model_fields") else []
        contract_consumes = f"{consumes.__name__}({', '.join(fields)})"

    # UI concern
    ui_spec = config.get("_ui_spec")
    ui_str = None
    if ui_spec is not None:
        from adk_fluent._ui import UISurface, _UIAutoSpec

        if isinstance(ui_spec, UISurface):
            ui_str = f"declarative surface '{ui_spec.name}'"
        elif isinstance(ui_spec, _UIAutoSpec):
            ui_str = f"llm_guided (catalog={ui_spec.catalog})"
        else:
            ui_str = "declarative"

    return DataFlow(
        sees=sees,
        accepts=accepts_str,
        stores=stores,
        format=format_str,
        contract_produces=contract_produces,
        contract_consumes=contract_consumes,
        ui=ui_str,
    )


def _build_llm_anatomy(builder: Any) -> str:
    """Build a detailed view of what gets sent to the LLM for this agent.

    Returns a formatted string showing each component in order:
    system message, history inclusion, context injection, tools, output constraint.
    """
    import re

    config = getattr(builder, "_config", {})
    name = config.get("name", "?")
    lines = [f"LLM Call Anatomy: {name}"]

    # 1. System message (instruction)
    instruction = config.get("instruction", "")
    if instruction:
        if callable(instruction):
            lines.append("  1. System:     <dynamic instruction provider>")
        else:
            preview = str(instruction)[:80].replace("\n", " ")
            if len(str(instruction)) > 80:
                preview += "..."
            lines.append(f'  1. System:     "{preview}"')

            # Show template variables
            template_vars = re.findall(r"\{(\w+)\??\}", str(instruction))
            if template_vars:
                lines.append(f"                 → {{{', '.join(template_vars)}}} templated from state at runtime")
    else:
        lines.append("  1. System:     (no instruction set)")

    # 2. Conversation history
    context_spec = config.get("_context_spec")
    include_contents = config.get("include_contents", "default")
    if context_spec is not None:
        ic = getattr(context_spec, "include_contents", "none")
        if ic == "none":
            lines.append('  2. History:    SUPPRESSED (include_contents="none", set by .reads()/.context())')
        else:
            lines.append(f'  2. History:    included (include_contents="{ic}")')
    elif include_contents != "default":
        lines.append(f'  2. History:    include_contents="{include_contents}"')
    else:
        lines.append("  2. History:    FULL conversation history included (default)")

    # 3. Context injection
    if context_spec is not None:
        from adk_fluent.testing.contracts import _context_description

        desc = _context_description(context_spec)
        lines.append(f"  3. Context:    {desc}")
        lines.append("                 → injected as <conversation_context> block in instruction")
    else:
        lines.append("  3. Context:    (no context spec — agent sees history directly)")

    # 4. Tools
    tools = list(config.get("tools", []))
    lists = getattr(builder, "_lists", {})
    tools.extend(lists.get("tools", []))
    output_schema = config.get("_output_schema") or config.get("output_schema")
    if output_schema is not None:
        lines.append("  4. Tools:      DISABLED (output_schema is set — cannot use tools)")
    elif tools:
        tool_names = []
        for t in tools:
            if hasattr(t, "name"):
                tool_names.append(t.name)
            elif hasattr(t, "__name__"):
                tool_names.append(t.__name__)
            else:
                tool_names.append(type(t).__name__)
        lines.append(f"  4. Tools:      {', '.join(tool_names)}")
    else:
        lines.append("  4. Tools:      (none registered)")

    # 5. Output constraint
    if output_schema is not None:
        schema_name = getattr(output_schema, "__name__", str(output_schema))
        fields = list(output_schema.model_fields.keys()) if hasattr(output_schema, "model_fields") else []
        field_str = ", ".join(f"{f}: ..." for f in fields) if fields else "..."
        lines.append(f"  5. Constraint: must return {schema_name} {{{field_str}}}")
    else:
        lines.append("  5. Constraint: (none — free-form text response)")

    # 6. After response
    output_key = config.get("output_key")
    after_parts = []
    if output_key:
        after_parts.append(f'response stored → state["{output_key}"]')
    if output_schema and not output_key:
        after_parts.append("parsed to Pydantic model (via .ask())")
    if output_schema and output_key:
        after_parts.append("raw text stored; parsed model returned via .ask()")
    if not after_parts:
        after_parts.append("response in conversation history only")
    lines.append(f"  6. After:      {'; '.join(after_parts)}")

    return "\n".join(lines)


# ======================================================================
# Build-time confusion detection
# ======================================================================


def check_output_interop(config: dict[str, Any]) -> list[dict[str, str]]:
    """Check for common confusion patterns in output-related config.

    Returns a list of advisory dicts with 'level', 'message', and 'hint' keys.
    Called during _run_build_contracts() to surface issues early.
    """
    issues: list[dict[str, str]] = []
    name = config.get("name", "?")

    output_schema = config.get("_output_schema") or config.get("output_schema")
    output_key = config.get("output_key")
    produces = config.get("_produces")
    consumes = config.get("_consumes")
    context_spec = config.get("_context_spec")

    # Pattern 1: .produces() without .writes() — contract declared but data not stored
    if produces is not None and output_key is None:
        fields = list(produces.model_fields.keys()) if hasattr(produces, "model_fields") else []
        issues.append(
            {
                "level": "info",
                "agent": name,
                "message": (
                    f"Agent '{name}' declares .produces({produces.__name__}) "
                    f"but has no .writes() — contract says it writes "
                    f"{', '.join(fields)} but nothing is stored in state"
                ),
                "hint": (
                    "Add .writes('<key>') to store the response in state, "
                    "or remove .produces() if the contract is not needed."
                ),
            }
        )

    # Pattern 2: Both .output_schema() AND .returns() set (duplicate format)
    raw_schema = config.get("output_schema")
    internal_schema = config.get("_output_schema")
    if raw_schema is not None and internal_schema is not None and raw_schema != internal_schema:
        issues.append(
            {
                "level": "warning",
                "agent": name,
                "message": (
                    f"Agent '{name}' has both .output_schema({raw_schema.__name__}) "
                    f"and .returns({internal_schema.__name__}) set to different models"
                ),
                "hint": (
                    "Use only .returns(Model) or @ Model — it sets the LLM "
                    "constraint AND enables automatic parsing in .ask()."
                ),
            }
        )

    # Pattern 3: .consumes() without .reads() or .context() — contract but no context
    if consumes is not None and context_spec is None:
        issues.append(
            {
                "level": "info",
                "agent": name,
                "message": (
                    f"Agent '{name}' declares .consumes({consumes.__name__}) "
                    f"but has no .reads() or .context() — contract says it "
                    f"needs specific state keys but agent sees full history"
                ),
                "hint": (
                    "Add .reads(<keys>) to explicitly inject state values, "
                    "or this agent relies on template variables "
                    "({key}) in its instruction string."
                ),
            }
        )

    # Pattern 4: .returns() without .writes() — structured response not stored
    if output_schema is not None and output_key is None:
        schema_name = getattr(output_schema, "__name__", str(output_schema))
        issues.append(
            {
                "level": "info",
                "agent": name,
                "message": (
                    f"Agent '{name}' uses .returns({schema_name}) for "
                    f"structured JSON but has no .writes() — the structured "
                    f"response is not stored in state for downstream agents"
                ),
                "hint": (
                    "This is fine for terminal agents or .ask() usage. "
                    "For pipelines, add .writes('<key>') to store "
                    "the structured response in state."
                ),
            }
        )

    return issues


# ======================================================================
# LLM call anatomy reference
# ======================================================================

LLM_CALL_ANATOMY = """
╔══════════════════════════════════════════════════════════════════════╗
║              WHAT GETS SENT TO THE LLM (in order)                  ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                    ║
║  1. SYSTEM MESSAGE (assembled by ADK)                              ║
║     ┌──────────────────────────────────────────────────────────┐   ║
║     │ static_instruction    (if set — cached, position 0)      │   ║
║     │ global_instruction    (if set — always included)         │   ║
║     │ instruction           (templated with state variables)   │   ║
║     │                       {key} → state["key"] value         │   ║
║     └──────────────────────────────────────────────────────────┘   ║
║                                                                    ║
║  2. CONVERSATION HISTORY (controlled by include_contents)          ║
║     ┌──────────────────────────────────────────────────────────┐   ║
║     │ include_contents="default" → ALL prior turns included    │   ║
║     │ include_contents="none"    → NO history sent             │   ║
║     │                                                          │   ║
║     │ .reads() sets "none" — history is SUPPRESSED             │   ║
║     │ Default (no .reads/.context) — full history INCLUDED     │   ║
║     └──────────────────────────────────────────────────────────┘   ║
║                                                                    ║
║  3. CONTEXT INJECTION (from .reads() / .context())                 ║
║     ┌──────────────────────────────────────────────────────────┐   ║
║     │ When .reads("topic","tone") is set:                      │   ║
║     │   instruction + "\\n\\n<conversation_context>\\n"          │   ║
║     │   "[topic]: value_from_state\\n"                          │   ║
║     │   "[tone]: value_from_state\\n"                           │   ║
║     │   "</conversation_context>"                              │   ║
║     │                                                          │   ║
║     │ Delivered via async instruction_provider (replaces       │   ║
║     │ the instruction field at runtime)                        │   ║
║     └──────────────────────────────────────────────────────────┘   ║
║                                                                    ║
║  4. USER MESSAGE (the prompt / new_message)                        ║
║     ┌──────────────────────────────────────────────────────────┐   ║
║     │ For .ask(): the prompt string                            │   ║
║     │ For pipelines: ADK manages turn flow automatically       │   ║
║     └──────────────────────────────────────────────────────────┘   ║
║                                                                    ║
║  5. TOOLS (if any registered)                                      ║
║     ┌──────────────────────────────────────────────────────────┐   ║
║     │ Tool descriptions sent as function declarations          │   ║
║     │ NOT sent if output_schema is set (ADK constraint)        │   ║
║     └──────────────────────────────────────────────────────────┘   ║
║                                                                    ║
║  6. OUTPUT CONSTRAINT (from .returns() / .output() / @ Model)      ║
║     ┌──────────────────────────────────────────────────────────┐   ║
║     │ output_schema → LLM MUST respond with matching JSON      │   ║
║     │ No output_schema → LLM responds in free-form text        │   ║
║     │                                                          │   ║
║     │ When set: tools are DISABLED (cannot use tools)          │   ║
║     └──────────────────────────────────────────────────────────┘   ║
║                                                                    ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                    ║
║  WHAT DOES NOT GET SENT                                            ║
║  ─────────────────────                                             ║
║  • State keys NOT in .reads() → NOT injected into context          ║
║  • State keys NOT in {template} → NOT templated into instruction   ║
║  • .produces()/.consumes() → NEVER sent (contract-only)            ║
║  • .writes() target key → NOT sent (only used AFTER response)      ║
║  • .accepts() schema → NOT sent (validated at tool-call time)      ║
║  • include_contents="none" → conversation history NOT sent         ║
║                                                                    ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                    ║
║  AFTER THE LLM RESPONDS                                            ║
║  ─────────────────────                                             ║
║  1. Response text captured                                         ║
║  2. If output_key set → state[key] = response_text                 ║
║  3. If output_schema set + .ask() → parsed to Pydantic model       ║
║  4. after_model_callback / after_agent_callback run                 ║
║                                                                    ║
╚══════════════════════════════════════════════════════════════════════╝
"""


# ======================================================================
# Interplay reference (importable as documentation)
# ======================================================================

INTERPLAY_GUIDE = """
╔══════════════════════════════════════════════════════════════════════╗
║                  DATA FLOW INTERPLAY GUIDE                         ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                    ║
║  CONCERN        METHOD(S)              WHAT IT CONTROLS            ║
║  ───────        ─────────              ────────────────            ║
║  Context        .reads() / .context()  What the agent SEES         ║
║  Input          .accepts()             Tool-mode INPUT validation  ║
║  Output         .returns() / @ Model   Response SHAPE (text/JSON)  ║
║  Storage        .writes() / .save_as() Where response is STORED    ║
║  Contract       .produces()/.consumes() Checker ANNOTATIONS only   ║
║                                                                    ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                    ║
║  RECOMMENDED CHAIN                                                 ║
║  ─────────────────                                                 ║
║  Agent("name")                                                     ║
║      .reads("key")         # CONTEXT: I see state["key"]          ║
║      .accepts(InputModel)  # INPUT:   Tool-mode validation        ║
║      .returns(OutputModel) # OUTPUT:  Structured JSON response    ║
║      .writes("result")     # STORAGE: Save to state["result"]     ║
║                                                                    ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                    ║
║  COMMON COMBINATIONS                                               ║
║  ───────────────────                                               ║
║  .writes("out")                → plain text stored in state        ║
║  .returns(M).writes("out")    → structured JSON stored in state   ║
║  .returns(M)                  → structured JSON, NOT in state     ║
║  .reads("k").writes("out")   → reads state, writes state         ║
║  .reads("k").returns(M)      → reads state, structured output    ║
║                                                                    ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                    ║
║  DEFAULTS (when NOT set)                                           ║
║  ───────────────────────                                           ║
║  No .reads()     → sees full conversation history                  ║
║  No .accepts()   → accepts any input when used as tool             ║
║  No .returns()   → plain text response, CAN use tools              ║
║  No .writes()    → response only in conversation, NOT in state     ║
║  No .produces()  → contract checker can't verify data flow         ║
║                                                                    ║
╚══════════════════════════════════════════════════════════════════════╝
"""
