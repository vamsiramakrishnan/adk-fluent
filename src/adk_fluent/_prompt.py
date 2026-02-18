"""Prompt builder — structured multi-section prompt composition.

Usage:
    from adk_fluent import Prompt

    prompt = (
        Prompt()
        .role("You are a senior code reviewer.")
        .task("Review the code for bugs and security issues.")
        .constraint("Be concise. Max 5 bullet points.")
        .format("Return markdown with ## sections.")
        .example("Input: x=eval(input()) | Output: - **Critical**: eval() on user input")
    )

    agent = Agent("reviewer").model("gemini-2.5-flash").instruct(prompt).build()

Compiles to a single instruction string. Each section is optional and reusable.
Template variables ({key}) pass through for ADK session-state injection.
"""

from __future__ import annotations

__all__ = ["Prompt"]


class Prompt:
    """Structured prompt builder that compiles to an instruction string.

    Sections are emitted in a fixed order: role, context, task, constraints,
    format, examples. All sections are optional. Calling a section method
    multiple times appends to that section.

    The result is usable anywhere ADK accepts a string instruction:
        agent.instruct(prompt)       # via str()
        agent.instruct(prompt.build())  # explicit
    """

    __slots__ = ("_sections",)

    # Ordered section keys — determines output order
    _SECTION_ORDER = ("role", "context", "task", "constraint", "format", "example")

    def __init__(self) -> None:
        self._sections: dict[str, list[str]] = {}

    # ------------------------------------------------------------------
    # Section methods
    # ------------------------------------------------------------------

    def role(self, text: str) -> Prompt:
        """Define the agent's role/persona."""
        self._sections.setdefault("role", []).append(text)
        return self

    def context(self, text: str) -> Prompt:
        """Add background context the agent should know."""
        self._sections.setdefault("context", []).append(text)
        return self

    def task(self, text: str) -> Prompt:
        """Define the primary task or objective."""
        self._sections.setdefault("task", []).append(text)
        return self

    def constraint(self, text: str) -> Prompt:
        """Add a constraint or rule the agent must follow."""
        self._sections.setdefault("constraint", []).append(text)
        return self

    def format(self, text: str) -> Prompt:
        """Specify the desired output format."""
        self._sections.setdefault("format", []).append(text)
        return self

    def example(self, text: str) -> Prompt:
        """Add a few-shot example."""
        self._sections.setdefault("example", []).append(text)
        return self

    # ------------------------------------------------------------------
    # Generic section method
    # ------------------------------------------------------------------

    def section(self, name: str, text: str) -> Prompt:
        """Add text to a named section (custom or standard)."""
        self._sections.setdefault(name, []).append(text)
        return self

    # ------------------------------------------------------------------
    # Composition
    # ------------------------------------------------------------------

    def merge(self, other: Prompt) -> Prompt:
        """Merge another Prompt's sections into this one. Returns a new Prompt."""
        result = Prompt()
        # Copy self's sections
        for key, items in self._sections.items():
            result._sections[key] = list(items)
        # Append other's sections
        for key, items in other._sections.items():
            result._sections.setdefault(key, []).extend(items)
        return result

    def __add__(self, other: Prompt) -> Prompt:
        """Combine two Prompts: prompt_a + prompt_b."""
        return self.merge(other)

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    _SECTION_LABELS = {
        "role": None,  # Role text stands alone (no header)
        "context": "Context",
        "task": "Task",
        "constraint": "Constraints",
        "format": "Output Format",
        "example": "Examples",
    }

    def build(self) -> str:
        """Compile all sections into a single instruction string."""
        parts: list[str] = []

        # Emit standard sections in order
        for key in self._SECTION_ORDER:
            items = self._sections.get(key)
            if not items:
                continue
            label = self._SECTION_LABELS.get(key, key.title())
            body = "\n".join(items)
            if label is None:
                # Role: no header
                parts.append(body)
            else:
                parts.append(f"{label}:\n{body}")

        # Emit custom sections (not in _SECTION_ORDER) alphabetically
        custom_keys = sorted(k for k in self._sections if k not in self._SECTION_ORDER)
        for key in custom_keys:
            items = self._sections[key]
            if items:
                body = "\n".join(items)
                parts.append(f"{key.title()}:\n{body}")

        return "\n\n".join(parts)

    def __str__(self) -> str:
        """String conversion — allows direct use in .instruct(prompt)."""
        return self.build()

    def __repr__(self) -> str:
        section_names = [k for k in self._SECTION_ORDER if k in self._sections]
        section_names.extend(sorted(k for k in self._sections if k not in self._SECTION_ORDER))
        return f"Prompt({', '.join(section_names)})"
