"""Output method interop — concept reference and build-time validation.

This module is the single source of truth for how the four orthogonal
output concerns interact in adk-fluent. Every method that touches
"output" in any form maps to exactly ONE of these four concerns:

==============  ==================  ========  ================================
Concern         Method(s)           Runtime?  What it controls
==============  ==================  ========  ================================
**CONTEXT**     ``.reads()``        YES       What state keys the agent SEES
                ``.context()``                in its prompt window.

**STORAGE**     ``.writes()``       YES       Where the agent's text response
                ``.save_as()``                is STORED in session state.

**FORMAT**      ``.output()``       YES       What SHAPE the LLM's response
                ``@ Model``                   takes (plain text vs structured
                ``.output_schema()``          JSON matching a Pydantic model).

**CONTRACT**    ``.produces()``     NO        Annotation for the data-flow
                ``.consumes()``               contract CHECKER. No runtime
                                              effect whatsoever.
==============  ==================  ========  ================================


Default behavior when NOT set
-----------------------------

===============  ===================================================================
Not set          Default
===============  ===================================================================
No ``.reads()``  Agent sees FULL conversation history from all agents
No ``.writes()`` Response lives ONLY in conversation history, NOT in state
No ``.output()`` Agent responds in plain text and CAN use tools
No ``.produces`` Contract checker treats writes as opaque (can't verify)
===============  ===================================================================


Common confusion patterns
-------------------------

1. **``.output()`` vs ``.writes()``** — These are INDEPENDENT.
   ``.output(Model)`` constrains the LLM's response FORMAT.
   ``.writes(key)`` controls WHERE the response is STORED.
   You can use both, either, or neither.

2. **``.output()`` vs ``.output_schema()``** — Nearly identical.
   ``.output(Model)`` sets ``_output_schema`` → LLM constraint + ``.ask()`` parsing.
   ``.output_schema(Model)`` sets ``output_schema`` → LLM constraint only.
   **Prefer ``.output()`` or ``@ Model``** for the common case.

3. **``.produces()`` vs ``.writes()``** — Different layers.
   ``.produces(Model)`` is a CONTRACT annotation with NO runtime effect.
   ``.writes(key)`` ACTUALLY stores data at runtime.
   Use ``.produces()`` to help the contract checker, not to store data.

4. **``.reads()`` vs ``.consumes()``** — Different layers.
   ``.reads("key")`` ACTUALLY injects state values into the agent's context.
   ``.consumes(Model)`` is a CONTRACT annotation with NO runtime effect.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DataFlow:
    """Snapshot of a builder's four output concerns.

    Returned by ``builder.data_flow()`` to show developers exactly
    what each concern is configured to.
    """

    sees: str
    """What context this agent sees (CONTEXT concern)."""

    stores: str | None
    """Where the response is stored in state (STORAGE concern)."""

    format: str
    """What shape the response takes (FORMAT concern)."""

    contract_produces: str | None
    """What the contract checker knows about writes (CONTRACT concern)."""

    contract_consumes: str | None
    """What the contract checker knows about reads (CONTRACT concern)."""

    def __str__(self) -> str:
        lines = [
            "Data Flow:",
            f"  Sees (context):  {self.sees}",
            f"  Stores (state):  {self.stores or 'nothing — response only in conversation history'}",
            f"  Format (output): {self.format}",
        ]
        if self.contract_produces or self.contract_consumes:
            lines.append("  Contract:")
            if self.contract_produces:
                lines.append(f"    produces: {self.contract_produces}")
            if self.contract_consumes:
                lines.append(f"    consumes: {self.contract_consumes}")
        else:
            lines.append("  Contract:        none declared (checker cannot verify data flow)")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"DataFlow(sees={self.sees!r}, stores={self.stores!r}, "
            f"format={self.format!r}, contract_produces={self.contract_produces!r}, "
            f"contract_consumes={self.contract_consumes!r})"
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

    # STORAGE concern
    output_key = config.get("output_key")
    stores = f"state['{output_key}']" if output_key else None

    # FORMAT concern
    output_schema = config.get("_output_schema") or config.get("output_schema")
    if output_schema is not None:
        schema_name = getattr(output_schema, "__name__", str(output_schema))
        format_str = f"structured JSON → {schema_name}"
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

    return DataFlow(
        sees=sees,
        stores=stores,
        format=format_str,
        contract_produces=contract_produces,
        contract_consumes=contract_consumes,
    )


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
                    f"Add .writes('<key>') to store the response in state, "
                    f"or remove .produces() if the contract is not needed."
                ),
            }
        )

    # Pattern 2: Both .output_schema() AND .output() set (duplicate format)
    raw_schema = config.get("output_schema")
    internal_schema = config.get("_output_schema")
    if raw_schema is not None and internal_schema is not None and raw_schema != internal_schema:
        issues.append(
            {
                "level": "warning",
                "agent": name,
                "message": (
                    f"Agent '{name}' has both .output_schema({raw_schema.__name__}) "
                    f"and .output({internal_schema.__name__}) set to different models"
                ),
                "hint": (
                    "Use only .output(Model) or @ Model — it sets the LLM "
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
                    f"Add .reads(<keys>) to explicitly inject state values, "
                    f"or this agent relies on template variables "
                    f"({{key}}) in its instruction string."
                ),
            }
        )

    # Pattern 4: .output() without .writes() — structured response not stored
    if output_schema is not None and output_key is None:
        schema_name = getattr(output_schema, "__name__", str(output_schema))
        issues.append(
            {
                "level": "info",
                "agent": name,
                "message": (
                    f"Agent '{name}' uses .output({schema_name}) for "
                    f"structured JSON but has no .writes() — the structured "
                    f"response is not stored in state for downstream agents"
                ),
                "hint": (
                    f"This is fine for terminal agents or .ask() usage. "
                    f"For pipelines, add .writes('<key>') to store "
                    f"the structured response in state."
                ),
            }
        )

    return issues


# ======================================================================
# Interplay reference (importable as documentation)
# ======================================================================

INTERPLAY_GUIDE = """
╔══════════════════════════════════════════════════════════════════════╗
║                  OUTPUT METHOD INTERPLAY GUIDE                     ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                    ║
║  CONCERN        METHOD(S)              WHAT IT CONTROLS            ║
║  ───────        ─────────              ────────────────            ║
║  Context        .reads() / .context()  What the agent SEES         ║
║  Storage        .writes() / .save_as() Where response is STORED    ║
║  Format         .output() / @ Model    Response SHAPE (text/JSON)  ║
║  Contract       .produces()/.consumes() Checker ANNOTATIONS only   ║
║                                                                    ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                    ║
║  COMMON COMBINATIONS                                               ║
║  ───────────────────                                               ║
║  .writes("out")                → plain text stored in state        ║
║  .output(M).writes("out")     → structured JSON stored in state   ║
║  .output(M)                   → structured JSON, NOT in state     ║
║  .reads("k").writes("out")    → reads state, writes state         ║
║  .reads("k").output(M)        → reads state, structured output    ║
║                                                                    ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                    ║
║  DEFAULTS (when NOT set)                                           ║
║  ───────────────────────                                           ║
║  No .reads()     → sees full conversation history                  ║
║  No .writes()    → response only in conversation, NOT in state     ║
║  No .output()    → plain text response, CAN use tools              ║
║  No .produces()  → contract checker can't verify data flow         ║
║                                                                    ║
╚══════════════════════════════════════════════════════════════════════╝
"""
