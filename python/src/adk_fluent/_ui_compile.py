"""
UI build-time compiler — wires A2UI surfaces into agent configuration.
=====================================================================
Called from ``_prepare_build_config`` when ``.ui()`` is used on an Agent.

Responsibilities:
1. **Prompt augmentation** — append A2UI schema/catalog instructions to the agent's
   system prompt so the LLM knows how to generate UI.
2. **Tool injection** — add A2UI send tool so the agent can emit UI messages.
3. **Callback wiring** — emit ``createSurface`` before agent, dispatch actions after.
"""

from __future__ import annotations

import json
from typing import Any

from adk_fluent._ui import (
    UISurface,
    _UIAutoSpec,
    _UISchemaSpec,
    compile_surface,
)

# ---------------------------------------------------------------------------
# Prompt generation
# ---------------------------------------------------------------------------

_A2UI_PROMPT_HEADER = """\
## A2UI (Agent-to-UI) Protocol

You can emit structured UI by returning JSON messages conforming to the A2UI protocol.
UI components are defined in a flat adjacency list (not nested). Each component has an
"id" and a "component" type. One component MUST have id "root"."""

_A2UI_CATALOG_SECTION = """
### Available Components

{components}

### Available Functions

{functions}

### Message Format

To create a surface, emit these JSON messages in order:
1. `createSurface` — initialize with surfaceId and catalogId
2. `updateComponents` — flat list of component definitions
3. `updateDataModel` — set initial data values (optional)
"""


def _generate_component_docs(surface: UISurface | None = None) -> str:
    """Generate component documentation for the LLM prompt."""
    # Basic catalog components
    components = [
        "- **Text**: content display (variants: h1-h5, caption, body)",
        "- **Image**: image display (url, alt, fit)",
        "- **Icon**: icon display (icon name)",
        "- **Video**: video player (url)",
        "- **AudioPlayer**: audio player (url, description)",
        "- **Row**: horizontal layout (children, justify, align, gap)",
        "- **Column**: vertical layout (children, justify, align, gap)",
        "- **List**: list layout (children, direction)",
        "- **Card**: card container (single child)",
        "- **Tabs**: tabbed interface (tabs: [{title, child}])",
        "- **Modal**: modal overlay (trigger, content)",
        "- **Divider**: visual separator (axis: horizontal|vertical)",
        "- **Button**: action button (child, variant, action)",
        "- **TextField**: text input (label, value, variant)",
        "- **CheckBox**: boolean toggle (label, value)",
        "- **ChoicePicker**: selection (options, value, variant)",
        "- **Slider**: range input (min, max, value, label)",
        "- **DateTimeInput**: date/time picker (value, enableDate, enableTime)",
    ]
    return "\n".join(components)


def _generate_function_docs() -> str:
    """Generate function documentation for the LLM prompt."""
    functions = [
        "- **required(value)** → boolean: check non-empty",
        "- **regex(value, pattern)** → boolean: regex match",
        "- **length(value, min?, max?)** → boolean: string length",
        "- **numeric(value, min?, max?)** → boolean: number range",
        "- **email(value)** → boolean: email format",
        "- **formatString(value)** → string: interpolation with ${/path}",
        "- **formatNumber(value, decimals?, grouping?)** → string",
        "- **formatCurrency(value, currency, decimals?, grouping?)** → string",
        "- **formatDate(value, format)** → string",
        "- **pluralize(value, one?, other, zero?, two?, few?, many?)** → string",
        "- **openUrl(url)** → void: open URL",
        "- **and(values)** / **or(values)** / **not(value)** → boolean: logic",
    ]
    return "\n".join(functions)


def generate_ui_prompt_section(
    surface: UISurface | None = None,
    catalog: str = "basic",
) -> str:
    """Generate the A2UI prompt section to inject into agent instructions."""
    sections = [_A2UI_PROMPT_HEADER]

    sections.append(
        _A2UI_CATALOG_SECTION.format(
            components=_generate_component_docs(surface),
            functions=_generate_function_docs(),
        )
    )

    if surface is not None:
        # Include pre-compiled surface as example
        messages = compile_surface(surface)
        sections.append("### Pre-defined Surface\n")
        sections.append(
            f"Surface '{surface.name}' is already defined. You can update it using updateDataModel messages.\n"
        )
        sections.append("```json")
        for msg in messages:
            sections.append(json.dumps(msg, indent=2))
        sections.append("```")

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Build-time compilation
# ---------------------------------------------------------------------------


def _has_a2ui_toolset(items: list[Any]) -> bool:
    """Detect whether ``items`` already contains an A2UI toolset.

    Recognises both raw ``SendA2uiToClientToolset`` instances and the
    sentinel produced by the previous (no-op) ``T.a2ui()`` shim.
    """
    try:
        from a2ui.agent import SendA2uiToClientToolset  # type: ignore[import-not-found]
    except ImportError:
        SendA2uiToClientToolset = None  # type: ignore[assignment]

    for item in items:
        if SendA2uiToClientToolset is not None and isinstance(item, SendA2uiToClientToolset):
            return True
        # TComposite-shaped items (kind == "a2ui") may sneak in via direct list use
        if getattr(item, "_kind", None) == "a2ui":
            return True
    return False


def _has_a2ui_guard(callbacks: list[Any]) -> bool:
    """Detect a previously registered ``G.a2ui()`` guard tuple."""
    return any(
        isinstance(entry, tuple) and len(entry) == 2 and entry[0] == "guard:a2ui"
        for entry in callbacks
    )


def _apply_ui_auto_wire(builder: Any, ui_spec: Any) -> None:
    """Apply ``Agent.ui()`` auto-wire flags to the builder.

    Runs BEFORE callback/list composition in ``_prepare_build_config`` so that
    appended tools/guards/middleware participate in the normal merge path. The
    post-merge work (prompt augmentation, before_agent_callback wiring) still
    happens in :func:`compile_ui_for_agent`.
    """
    from adk_fluent._exceptions import A2UINotInstalled, BuilderError

    auto_tool = bool(builder._config.get("_a2ui_auto_tool"))
    auto_guard = bool(builder._config.get("_a2ui_auto_guard"))
    auto_log = bool(builder._config.get("_a2ui_auto_log"))

    if auto_tool:
        existing_tools = list(builder._lists.get("tools", []))
        if not _has_a2ui_toolset(existing_tools):
            try:
                from adk_fluent._tools import T

                tool_chain = T.a2ui()
            except A2UINotInstalled as exc:
                raise BuilderError(
                    builder_name=builder._config.get("name", "<anonymous>"),
                    builder_type=type(builder).__name__,
                    field_errors=[str(exc)],
                    original=exc,
                ) from exc
            for item in tool_chain.to_tools():
                builder._lists.setdefault("tools", []).append(item)

    if auto_guard:
        existing_after = builder._callbacks.get("after_model_callback", [])
        if not _has_a2ui_guard(existing_after):
            from adk_fluent._guards import G

            G.a2ui()._compile_into(builder)

    if auto_log:
        from adk_fluent._middleware import M

        log_mw = M.a2ui_log(level="info")
        if getattr(builder, "_middlewares", None) is None:
            builder._middlewares = []
        builder._middlewares.extend(log_mw.to_stack())


def compile_ui_for_agent(ui_spec: Any, config: dict[str, Any]) -> None:
    """Compile UI spec into agent build config.

    Called from ``_prepare_build_config`` after callback/list composition.
    Responsible for the post-merge wiring:

    - Augments ``instruction`` with the A2UI prompt section.
    - Wires a ``before_agent_callback`` to emit ``createSurface`` for
      declarative surfaces.

    Auto-wired tools, guards and middleware (the ``Agent.ui(llm_guided=True,
    log=True)`` flags) are stamped on the *builder* in
    :func:`_apply_ui_auto_wire` BEFORE this function runs, so the standard
    composition path picks them up. ``P.ui_schema()`` is NOT injected here —
    :func:`generate_ui_prompt_section` already produces equivalent content.

    Args:
        ui_spec: One of ``UISurface``, ``_UIAutoSpec``, ``_UISchemaSpec``,
                 or ``UIComponent`` (wrapped in a default surface).
        config: The agent's build config dict (from ``_prepare_build_config``).
    """
    from adk_fluent._ui import UIComponent

    # Normalize spec — _add_ui_spec already wraps loose UIComponent into a
    # surface, but be defensive in case compile_ui_for_agent is invoked
    # directly with a raw component.
    surface: UISurface | None = None
    if isinstance(ui_spec, UISurface):
        surface = ui_spec
    elif isinstance(ui_spec, UIComponent):
        surface = UISurface(name="default", root=ui_spec)
    elif isinstance(ui_spec, _UIAutoSpec):
        pass  # LLM-guided: just inject schema
    elif isinstance(ui_spec, _UISchemaSpec):
        pass  # Schema-only injection

    # 1. Prompt augmentation
    prompt_section = generate_ui_prompt_section(
        surface=surface,
        catalog=getattr(ui_spec, "catalog", "basic"),
    )
    existing_instruction = config.get("instruction", "")
    if existing_instruction:
        config["instruction"] = f"{existing_instruction}\n\n{prompt_section}"
    else:
        config["instruction"] = prompt_section

    # 2. Callback wiring — emit createSurface before agent starts
    if surface is not None:
        messages = compile_surface(surface)

        async def _emit_create_surface(callback_context: Any) -> None:
            """Before-agent callback: emit createSurface + updateComponents."""
            state = callback_context.state
            state["_a2ui_surface_messages"] = messages
            state["_a2ui_surface_id"] = surface.name  # type: ignore[union-attr]

        existing_before = config.get("before_agent_callback")
        if existing_before is not None:
            orig = existing_before

            async def _chained_before(ctx: Any) -> None:
                result = orig(ctx)
                if hasattr(result, "__await__"):
                    await result
                await _emit_create_surface(ctx)

            config["before_agent_callback"] = _chained_before
        else:
            config["before_agent_callback"] = _emit_create_surface

    # Note: ui_spec and surface are NOT stored in config — config goes to
    # LlmAgent(**config) which has extra='forbid'. The original spec is
    # preserved on the builder's _config["_ui_spec"] for introspection.
