"""A2UI LLM-Guided Mode: Let the Agent Design the UI

Demonstrates LLM-guided UI mode — the agent has full control over the A2UI
surface via the ``a2ui-agent`` toolset and a catalog schema injected into
the prompt.

The wedge ergonomics:

- ``Agent.ui(llm_guided=True)``  — auto-wires ``T.a2ui()`` + ``G.a2ui()`` and
                                    promotes the spec to ``UI.auto()``.
- ``UI.auto()``                  — explicit form for those who want the marker.
- ``T.a2ui()``                   — raises ``A2UINotInstalled`` when the
                                    optional ``a2ui-agent`` package is missing.
"""

from __future__ import annotations

from adk_fluent import A2UINotInstalled, Agent, BuilderError, G, P, T, UI
from adk_fluent._ui import _UIAutoSpec  # internal marker, used only for isinstance check


def _a2ui_installed() -> bool:
    try:
        import a2ui.agent  # type: ignore[import-not-found]  # noqa: F401

        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# 1. The one-liner: .ui(llm_guided=True).
#    No need to manually call .tools(T.a2ui()) or .guard(G.a2ui()) — the
#    wedge auto-wires both at build time.
# ---------------------------------------------------------------------------

auto_agent = Agent("creative", "gemini-2.5-flash").instruct("Build beautiful UIs.").ui(llm_guided=True)
spec = auto_agent._config["_ui_spec"]
assert isinstance(spec, _UIAutoSpec)
assert spec._from_flag is True
assert auto_agent._config["_a2ui_auto_tool"] is True
assert auto_agent._config["_a2ui_auto_guard"] is True

# ---------------------------------------------------------------------------
# 2. The explicit form: pass UI.auto() and opt into auto-wiring.
# ---------------------------------------------------------------------------

guided = (
    Agent("designer", "gemini-2.5-flash")
    .instruct(P.role("UI designer") + P.task("Build a dashboard"))
    .ui(UI.auto(catalog="basic"), llm_guided=True)
)
assert isinstance(guided._config["_ui_spec"], _UIAutoSpec)
assert guided._config["_a2ui_auto_tool"] is True

# ---------------------------------------------------------------------------
# 3. Prompt-only mode: pass UI.auto() WITHOUT the flag — schema goes into
#    the prompt but no toolset / guard is auto-wired.
# ---------------------------------------------------------------------------

prompt_only = Agent("scribe", "gemini-2.5-flash").instruct("Describe UIs textually.").ui(UI.auto())
assert prompt_only._config["_a2ui_auto_tool"] is False
assert prompt_only._config["_a2ui_auto_guard"] is False

# ---------------------------------------------------------------------------
# 4. Custom catalog identifier.
# ---------------------------------------------------------------------------

custom = UI.auto(catalog="extended")
assert custom.catalog == "extended"
assert custom._from_flag is False  # only flag-promoted specs set this True

# ---------------------------------------------------------------------------
# 5. Manual cross-namespace symphony — still works for users who want
#    explicit control over every layer.
# ---------------------------------------------------------------------------

if _a2ui_installed():
    full_agent = (
        Agent("support", "gemini-2.5-flash")
        .instruct(P.role("Support agent") + P.task("Help customers"))
        .tools(T.google_search() | T.a2ui())
        .guard(G.pii() | G.a2ui(max_components=30))
        .ui(UI.auto(), llm_guided=True)  # auto-wire dedups against existing T.a2ui/G.a2ui
    )
    full_agent.build()
else:
    # Without the optional dep, T.a2ui() raises immediately — the wedge contract.
    try:
        T.a2ui()
    except A2UINotInstalled as exc:
        assert "pip install a2ui-agent" in str(exc)

# ---------------------------------------------------------------------------
# 6. Build behavior when the optional dep is missing.
# ---------------------------------------------------------------------------

if not _a2ui_installed():
    try:
        auto_agent.build()
    except BuilderError as exc:
        assert isinstance(exc.__cause__, A2UINotInstalled)
    else:
        raise AssertionError("expected BuilderError on missing a2ui-agent")

print("All A2UI LLM-guided assertions passed!")
