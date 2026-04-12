"""Alias engine — derive ergonomic short names for builder methods.

Uses morphological suffix rules to derive aliases:
    description → describe
    instruction → instruct
    configuration → configure

Also supports semantic overrides and callback alias generation.
"""

from __future__ import annotations

# DEPRECATED: use derive_alias/derive_aliases instead
_FIELD_ALIAS_TABLE = {
    "instruction": "instruct",
    "description": "describe",
    "global_instruction": "global_instruct",
    "output_key": "outputs",
    "include_contents": "history",
    "static_instruction": "static",
}

# Additional aliases that map to the same field as an existing alias.
_EXTRA_ALIASES = {
    "include_history": "include_contents",
}

# Semantic overrides from _FIELD_ALIAS_TABLE that cannot be derived morphologically.
SEMANTIC_OVERRIDES = {
    "outputs": "output_key",
    "history": "include_contents",
    "static": "static_instruction",
}

# ---------------------------------------------------------------------------
# MORPHOLOGICAL ALIAS DERIVATION (A2)
# ---------------------------------------------------------------------------

_ALIAS_SUFFIX_RULES: list[tuple[str, str]] = [
    ("ription", "ribe"),  # description -> describe
    ("ruction", "ruct"),  # instruction -> instruct
    ("uration", "ure"),  # configuration -> configure
    ("ution", "ute"),  # execution -> execute
    ("etion", "ete"),  # completion -> complete, deletion -> delete
    ("ation", "ate"),  # generation -> generate
    ("ment", ""),  # deployment -> deploy
]

_MIN_ALIAS_FIELD_LEN = 8


def derive_alias(field_name: str) -> str | None:
    """Derive a short alias from a field name using morphological suffix rules.

    Returns None if no rule matches or the name is too short (< 8 chars).
    """
    if len(field_name) < _MIN_ALIAS_FIELD_LEN:
        return None
    for suffix, replacement in _ALIAS_SUFFIX_RULES:
        if field_name.endswith(suffix):
            candidate = field_name[: -len(suffix)] + replacement
            if candidate and len(candidate) < len(field_name):
                return candidate
    return None


def derive_aliases(
    field_names: list[str],
    *,
    overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    """Batch-derive short aliases from field names.

    Returns ``{alias: field_name}``.  Applies morphological derivation first,
    then applies *overrides* (which take precedence over derived aliases).
    """
    aliases: dict[str, str] = {}
    for field_name in field_names:
        alias = derive_alias(field_name)
        if alias is not None:
            aliases[alias] = field_name
    if overrides:
        for alias, field_name in overrides.items():
            if field_name in field_names:
                aliases[alias] = field_name
    return aliases


# DEPRECATED: use derive_alias/derive_aliases instead
def generate_aliases(field_names: list[str]) -> dict[str, str]:
    """Generate ergonomic aliases for fields.

    Returns {alias: field_name} for fields that have an entry
    in the alias table or extra aliases table.
    """
    aliases: dict[str, str] = {}
    for field_name in field_names:
        if field_name in _FIELD_ALIAS_TABLE:
            aliases[_FIELD_ALIAS_TABLE[field_name]] = field_name
    # Add extra aliases (secondary short names for the same field)
    for alias, field_name in _EXTRA_ALIASES.items():
        if field_name in field_names:
            aliases[alias] = field_name
    return aliases


def generate_callback_aliases(callback_field_names: list[str]) -> dict[str, str]:
    """Generate short aliases for callback fields by stripping '_callback' suffix.

    Returns {short_name: full_callback_name},
    e.g. {"before_model": "before_model_callback"}.
    """
    aliases: dict[str, str] = {}
    for name in callback_field_names:
        if name.endswith("_callback"):
            short = name[: -len("_callback")]
            aliases[short] = name
    return aliases
