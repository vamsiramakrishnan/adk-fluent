"""Type normalization — clean up type annotations in generated code.

Resolves module-qualified types (``types.Content`` → ``Content``),
replaces unresolvable types with ``Any``, and collects type references
for import resolution.
"""

from __future__ import annotations

import re

from code_ir import ClassNode, Param

from .imports import MODULE_PREFIX_REWRITES, STDLIB_MODULE_REFS, UNRESOLVABLE_TYPES


def normalize_stub_classes(classes: list[ClassNode]) -> list[str]:
    """Normalize type references in class method signatures.

    Resolves module-qualified types, replaces unresolvable types with ``Any``,
    and tracks additional import lines needed (e.g., ``import ssl``).

    Mutates *classes* in place and returns extra import lines.
    """
    extra_imports: list[str] = []
    needs_ssl = False

    def _normalize_type(type_str: str | None) -> str | None:
        nonlocal needs_ssl
        if type_str is None:
            return None
        result = type_str
        # Resolve module-qualified types (types.Content → Content)
        for prefix, replacement in MODULE_PREFIX_REWRITES.items():
            result = result.replace(prefix, replacement)
        # Check for stdlib module refs (ssl.SSLContext → keep, add import)
        for prefix, _import_line in STDLIB_MODULE_REFS.items():
            if prefix in result:
                needs_ssl = True
        # Replace unresolvable types with Any
        for utype in UNRESOLVABLE_TYPES:
            result = re.sub(rf"\b{re.escape(utype)}\b", "Any", result)
        # Ensure bare Callable has type args (pyright requires them)
        result = re.sub(r"\bCallable\b(?!\[)", "Callable[..., Any]", result)
        # Ensure bare AsyncIterator has type args
        result = re.sub(r"\bAsyncIterator\b(?!\[)", "AsyncIterator[Any]", result)
        return result

    for cls in classes:
        for method in cls.methods:
            new_params = []
            for param in method.params:
                new_type = _normalize_type(param.type)
                if new_type != param.type:
                    new_params.append(
                        Param(name=param.name, type=new_type, default=param.default, keyword_only=param.keyword_only)
                    )
                else:
                    new_params.append(param)
            method.params = new_params
            method.returns = _normalize_type(method.returns)

    if needs_ssl:
        extra_imports.append("import ssl")

    return extra_imports


def resolve_stub_name_conflicts(classes: list[ClassNode], already_imported: set[str]) -> None:
    """Resolve name conflicts where a type import name matches a builder class.

    When a builder class ``Foo`` exists in the module AND ``Foo`` is used
    as a parameter type in another builder's methods, the bare import
    ``from ... import Foo`` conflicts with ``class Foo(BuilderBase):``.

    This function updates method signatures to use ``_ADK_Foo`` (which is
    already imported as the build-target alias) instead of bare ``Foo``.
    """
    builder_names = {cls.name for cls in classes}

    for cls in classes:
        for method in cls.methods:
            new_params = []
            for param in method.params:
                if param.type:
                    new_type = param.type
                    for bname in builder_names:
                        # Only replace if the _ADK_ aliased import exists
                        if bname in new_type and f"_ADK_{bname}" in already_imported:
                            new_type = re.sub(rf"\b(?<!_ADK_){bname}\b", f"_ADK_{bname}", new_type)
                    if new_type != param.type:
                        new_params.append(
                            Param(
                                name=param.name, type=new_type, default=param.default, keyword_only=param.keyword_only
                            )
                        )
                    else:
                        new_params.append(param)
                else:
                    new_params.append(param)
            method.params = new_params


def collect_stub_type_refs(classes: list[ClassNode]) -> set[str]:
    """Walk all method signatures in *classes* and return referenced type names."""
    refs: set[str] = set()
    _IDENT = re.compile(r"\b([A-Z]\w+)")
    # Strip Literal[...] contents so string values like Literal['BaseAgent']
    # don't create false-positive type references.
    _LITERAL_CONTENT = re.compile(r"(Literal\[)[^\]]*\]")

    def _scan(type_str: str) -> None:
        cleaned = _LITERAL_CONTENT.sub(r"\1]", type_str)
        refs.update(_IDENT.findall(cleaned))

    for cls in classes:
        for method in cls.methods:
            for param in method.params:
                if param.type:
                    _scan(param.type)
            if method.returns:
                _scan(method.returns)
    return refs
