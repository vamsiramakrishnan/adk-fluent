"""IR builders — convert BuilderSpec into ClassNode/ModuleNode IR.

Each function builds one logical piece of a builder class:
  - attrs: class-level constants (_ALIASES, _ADK_TARGET_CLASS, etc.)
  - init: __init__ method
  - aliases: ergonomic name methods (.describe() → .description())
  - callbacks: additive callback methods (.after_agent(), etc.)
  - fields: generic field setter methods
  - extras: behavior-driven helper methods (.tool(), .sub_agent(), etc.)
  - build: terminal .build() method

spec_to_ir() assembles them into a complete ClassNode.
"""

from __future__ import annotations

from code_ir import (
    AppendStmt,
    AssignStmt,
    AsyncForYield,
    ClassAttr,
    ClassNode,
    DeprecationStmt,
    ForAppendStmt,
    ForkAndAssign,
    IfStmt,
    ImportStmt,
    MethodNode,
    Param,
    RawStmt,
    ReturnStmt,
    SubscriptAssign,
    split_at_commas,
)

from .imports import _is_optional_source, adk_import_name, gen_deferred_import_line
from .sig_parser import parse_signature
from .spec import BuilderSpec

# ---------------------------------------------------------------------------
# CLASS ATTRIBUTES
# ---------------------------------------------------------------------------


def ir_class_attrs(spec: BuilderSpec) -> list[ClassAttr]:
    """Build ClassAttr nodes for _ALIASES, _CALLBACK_ALIASES, _ADK_TARGET_CLASS, etc."""
    attrs: list[ClassAttr] = []

    attrs.append(ClassAttr("_ALIASES", "dict[str, str]", repr(spec.aliases) if spec.aliases else "{}"))
    attrs.append(
        ClassAttr("_CALLBACK_ALIASES", "dict[str, str]", repr(spec.callback_aliases) if spec.callback_aliases else "{}")
    )

    additive = spec.additive_fields & {f["name"] for f in spec.fields}
    additive_repr = "{" + ", ".join(repr(s) for s in sorted(additive)) + "}" if additive else "set()"
    attrs.append(ClassAttr("_ADDITIVE_FIELDS", "set[str]", additive_repr))

    if not spec.is_composite and not spec.is_standalone and spec.inspection_mode != "init_signature":
        # ADK class is deferred — _ADK_TARGET_CLASS is None at class level.
        # Typo detection falls back to _KNOWN_PARAMS when None.
        pass

    if spec.inspection_mode == "init_signature" and spec.init_params:
        param_names = sorted(
            {p["name"] for p in spec.init_params if p["name"] not in ("self", "args", "kwargs", "kwds")}
        )
        known_repr = "{" + ", ".join(repr(s) for s in param_names) + "}" if param_names else "set()"
        attrs.append(ClassAttr("_KNOWN_PARAMS", "set[str] | None", known_repr))
    elif spec.inspection_mode == "init_signature":
        attrs.append(ClassAttr("_KNOWN_PARAMS", "set[str] | None", "set()"))

    return attrs


# ---------------------------------------------------------------------------
# __init__ METHOD
# ---------------------------------------------------------------------------


def ir_init_method(spec: BuilderSpec) -> MethodNode:
    """Build MethodNode for __init__."""
    params: list[Param] = [Param("self")]
    for arg in spec.constructor_args:
        params.append(Param(arg, type="str"))
    for arg in spec.optional_constructor_args or []:
        params.append(Param(arg, type="str | None", default="None"))

    body: list = []

    if spec.constructor_args:
        config_init = ", ".join(f'"{arg}": {arg}' for arg in spec.constructor_args)
        body.append(AssignStmt("self._config: dict[str, Any]", f"{{{config_init}}}"))
    else:
        body.append(AssignStmt("self._config: dict[str, Any]", "{}"))

    body.append(AssignStmt("self._callbacks: dict[str, list[Callable]]", "defaultdict(list)"))
    body.append(AssignStmt("self._lists: dict[str, list]", "defaultdict(list)"))
    body.append(AssignStmt("self._frozen", "False"))

    for arg in spec.optional_constructor_args or []:
        body.append(
            IfStmt(
                condition=f"{arg} is not None",
                body=(SubscriptAssign("self._config", arg, arg),),
            )
        )

    return MethodNode(name="__init__", params=params, returns="None", body=body)


# ---------------------------------------------------------------------------
# ALIAS METHODS
# ---------------------------------------------------------------------------


def ir_alias_methods(spec: BuilderSpec) -> list[MethodNode]:
    """Build MethodNodes for alias methods (.describe() → description, etc.)."""
    methods: list[MethodNode] = []

    extra_names = {e["name"] for e in spec.extras} if spec.extras else set()
    for fluent_name, field_name in spec.aliases.items():
        # Skip aliases that are now deprecated (handled by ir_deprecated_alias_methods)
        if spec.deprecated_aliases and fluent_name in spec.deprecated_aliases:
            continue
        # Skip aliases that are overridden by extras (handled by ir_extra_methods)
        if fluent_name in extra_names:
            continue
        field_info = next((f for f in spec.fields if f["name"] == field_name), None)
        type_hint = field_info["type_str"] if field_info else "Any"

        doc = spec.field_docs.get(fluent_name, "")
        if not doc:
            doc = spec.field_docs.get(field_name, "")
        if not doc and field_info:
            doc = field_info.get("description", "")

        methods.append(
            MethodNode(
                name=fluent_name,
                params=[Param("self"), Param("value", type=type_hint)],
                returns="Self",
                doc=doc or f"Set the `{field_name}` field.",
                body=[
                    ForkAndAssign(),
                    SubscriptAssign("self._config", field_name, "value"),
                    ReturnStmt("self"),
                ],
            )
        )

    return methods


# ---------------------------------------------------------------------------
# DEPRECATED ALIAS METHODS
# ---------------------------------------------------------------------------


def ir_deprecated_alias_methods(spec: BuilderSpec) -> list[MethodNode]:
    """Build MethodNodes for deprecated aliases that emit DeprecationWarning."""
    methods: list[MethodNode] = []
    if not spec.deprecated_aliases:
        return methods

    for fluent_name, config in spec.deprecated_aliases.items():
        field_name = config.get("field", spec.aliases.get(fluent_name, fluent_name))
        use_instead = config.get("use", "")

        field_info = next((f for f in spec.fields if f["name"] == field_name), None)
        type_hint = field_info["type_str"] if field_info else "Any"

        doc = f"Deprecated: use ``.{use_instead}()`` instead."

        methods.append(
            MethodNode(
                name=fluent_name,
                params=[Param("self"), Param("value", type=type_hint)],
                returns="Self",
                doc=doc,
                body=[
                    ForkAndAssign(),
                    DeprecationStmt(old_name=fluent_name, new_name=use_instead),
                    SubscriptAssign("self._config", field_name, "value"),
                    ReturnStmt("self"),
                ],
            )
        )

    return methods


# ---------------------------------------------------------------------------
# CALLBACK METHODS
# ---------------------------------------------------------------------------


def ir_callback_methods(spec: BuilderSpec) -> list[MethodNode]:
    """Build MethodNodes for callback methods (.after_agent(), .after_agent_if(), etc.)."""
    methods: list[MethodNode] = []

    for short_name, full_name in spec.callback_aliases.items():
        # Variadic version
        methods.append(
            MethodNode(
                name=short_name,
                params=[Param("self"), Param("*fns", type="Callable[..., Any]")],
                returns="Self",
                doc=f"Append callback(s) to `{full_name}`. Multiple calls accumulate.",
                body=[
                    ForkAndAssign(),
                    ForAppendStmt(var="fn", iterable="fns", target="self._callbacks", key=full_name),
                    ReturnStmt("self"),
                ],
            )
        )
        # Conditional version
        methods.append(
            MethodNode(
                name=f"{short_name}_if",
                params=[Param("self"), Param("condition", type="bool"), Param("fn", type="Callable[..., Any]")],
                returns="Self",
                doc=f"Append callback to `{full_name}` only if condition is True.",
                body=[
                    ForkAndAssign(),
                    IfStmt(
                        condition="condition",
                        body=(AppendStmt("self._callbacks", full_name, "fn"),),
                    ),
                    ReturnStmt("self"),
                ],
            )
        )

    return methods


# ---------------------------------------------------------------------------
# FIELD METHODS
# ---------------------------------------------------------------------------


def ir_field_methods(spec: BuilderSpec) -> list[MethodNode]:
    """Build MethodNodes for generic field setter methods (__getattr__ forwarding)."""
    if spec.is_composite or spec.is_standalone:
        return []

    aliased_fields = set(spec.aliases.values())
    callback_fields = set(spec.callback_aliases.values())
    extra_names = {e["name"] for e in spec.extras}
    alias_method_names = set(spec.aliases.keys())
    callback_method_names = set(spec.callback_aliases.keys())
    callback_if_names = {f"{n}_if" for n in spec.callback_aliases}
    deprecated_names = set(spec.deprecated_aliases.keys()) if spec.deprecated_aliases else set()
    deprecated_fields = (
        {v.get("field", "") for v in spec.deprecated_aliases.values()} if spec.deprecated_aliases else set()
    )

    covered = (
        spec.skip_fields
        | aliased_fields
        | callback_fields
        | extra_names
        | alias_method_names
        | callback_method_names
        | callback_if_names
        | deprecated_names
        | deprecated_fields
    )

    methods: list[MethodNode] = []

    if spec.inspection_mode == "init_signature" and spec.init_params:
        for param in spec.init_params:
            pname = param["name"]
            if pname in ("self", "args", "kwargs", "kwds"):
                continue
            if pname in covered:
                continue
            if pname in spec.constructor_args:
                continue
            type_str = param.get("type_str", "Any")
            methods.append(
                MethodNode(
                    name=pname,
                    params=[Param("self"), Param("value", type=type_str)],
                    returns="Self",
                    doc=f"Set the ``{pname}`` field.",
                    body=[
                        ForkAndAssign(),
                        SubscriptAssign("self._config", pname, "value"),
                        ReturnStmt("self"),
                    ],
                )
            )
    else:
        for field in spec.fields:
            fname = field["name"]
            if fname in covered:
                continue
            if fname in spec.constructor_args:
                continue
            if field.get("is_callback") and fname in spec.additive_fields:
                methods.append(
                    MethodNode(
                        name=fname,
                        params=[Param("self"), Param("*fns", type="Callable[..., Any]")],
                        returns="Self",
                        doc=f"Append callback(s) to ``{fname}``. Multiple calls accumulate.",
                        body=[
                            ForkAndAssign(),
                            ForAppendStmt(var="fn", iterable="fns", target="self._callbacks", key=fname),
                            ReturnStmt("self"),
                        ],
                    )
                )
            else:
                type_str = field["type_str"]
                doc = spec.field_docs.get(fname, field.get("description", ""))
                methods.append(
                    MethodNode(
                        name=fname,
                        params=[Param("self"), Param("value", type=type_str)],
                        returns="Self",
                        doc=doc or f"Set the ``{fname}`` field.",
                        body=[
                            ForkAndAssign(),
                            SubscriptAssign("self._config", fname, "value"),
                            ReturnStmt("self"),
                        ],
                    )
                )

    return methods


# ---------------------------------------------------------------------------
# EXTRA METHODS (behavior-driven)
# ---------------------------------------------------------------------------


def _extract_forwarding_args(sig: str) -> str:
    """Extract parameter names from a signature and build a forwarding argument string.

    Handles keyword-only parameters (those after ``*``) by forwarding them
    as ``name=name`` so the target helper receives them correctly.

    Uses bracket-depth-aware splitting so complex type annotations like
    ``Callable[[ReadonlyContext], str | Awaitable[str]]`` are not
    incorrectly treated as multiple parameters.
    """
    if "self, " in sig:
        params_str = sig.split("(self, ", 1)[1].rsplit(")", 1)[0]
    elif "(self)" in sig:
        return ""
    else:
        params_str = ""
    parts = []
    kw_only = False
    for p in split_at_commas(params_str):
        p = p.strip()
        if not p:
            continue
        if p == "*":
            kw_only = True
            continue
        pname = p.split(":")[0].strip().split("=")[0].strip().lstrip("*")
        if not pname:
            continue
        if kw_only:
            parts.append(f"{pname}={pname}")
        else:
            parts.append(pname)
    return ", ".join(parts)


def ir_extra_methods(spec: BuilderSpec) -> list[MethodNode]:
    """Build MethodNodes for extra methods (.tool(), .sub_agent(), .delegate(), etc.)."""
    methods: list[MethodNode] = []

    for extra in spec.extras:
        name = extra["name"]
        sig = extra.get("signature", "(self) -> Self")
        doc = extra.get("doc", "")
        behavior = extra.get("behavior", "custom")
        target = extra.get("target_field", "")

        params, return_type = parse_signature(sig)
        is_async = behavior in ("runtime_helper_async", "runtime_helper_async_gen")
        is_generator = behavior == "runtime_helper_async_gen"

        # Derive the first non-self parameter name from the parsed params list
        _value_params = [p for p in params if p.name != "self" and not p.name.startswith("*")]
        _first_param = _value_params[0].name if _value_params else "value"

        body: list = []

        if behavior == "list_append":
            body.append(ForkAndAssign())
            body.append(AppendStmt("self._lists", target, _first_param))
            body.append(ReturnStmt("self"))

        elif behavior == "field_set":
            body.append(ForkAndAssign())
            body.append(SubscriptAssign("self._config", target, _first_param))
            body.append(ReturnStmt("self"))

        elif behavior == "dual_callback":
            target_fields = extra.get("target_fields", [])
            body.append(ForkAndAssign())
            for tf in target_fields:
                body.append(AppendStmt("self._callbacks", tf, _first_param))
            body.append(ReturnStmt("self"))

        elif behavior == "deep_copy":
            body.append(
                ImportStmt(
                    module="adk_fluent._helpers",
                    name="deep_clone_builder",
                    call=f"return deep_clone_builder(self, {_first_param})",
                )
            )

        elif behavior == "runtime_helper":
            helper_func = extra.get("helper_func", name)
            args_fwd = _extract_forwarding_args(sig)
            body.append(
                ImportStmt(
                    module="adk_fluent._helpers",
                    name=helper_func,
                    call=f"return {helper_func}(self, {args_fwd})",
                )
            )

        elif behavior == "runtime_helper_async":
            helper_func = extra.get("helper_func", name)
            args_fwd = _extract_forwarding_args(sig)
            body.append(
                ImportStmt(
                    module="adk_fluent._helpers",
                    name=helper_func,
                    call=f"return await {helper_func}(self, {args_fwd})",
                )
            )

        elif behavior == "runtime_helper_async_gen":
            helper_func = extra.get("helper_func", name)
            args_fwd = _extract_forwarding_args(sig)
            body.append(
                AsyncForYield(
                    module="adk_fluent._helpers",
                    func=helper_func,
                    args=f"self, {args_fwd}" if args_fwd else "self",
                )
            )

        elif behavior == "runtime_helper_ctx":
            helper_func = extra.get("helper_func", name)
            body.append(
                ImportStmt(
                    module="adk_fluent._helpers",
                    name=helper_func,
                    call=f"return {helper_func}(self)",
                )
            )

        elif behavior == "deprecation_alias":
            target_method = extra.get("target_method", name)
            body.append(DeprecationStmt(old_name=name, new_name=target_method))
            body.append(ReturnStmt(f"self.{target_method}({_first_param})"))

        else:
            # custom / unknown
            body.append(RawStmt('raise NotImplementedError("Implement in hand-written layer")'))

        methods.append(
            MethodNode(
                name=name,
                params=params,
                returns=return_type,
                doc=doc,
                body=body,
                is_async=is_async,
                is_generator=is_generator,
            )
        )

    return methods


# ---------------------------------------------------------------------------
# BUILD METHOD
# ---------------------------------------------------------------------------


def ir_build_method(spec: BuilderSpec) -> MethodNode | None:
    """Build MethodNode for .build() terminal."""
    if spec.is_composite or spec.is_standalone:
        return None

    class_short = adk_import_name(spec)

    body: list = []

    # Deferred ADK import: load the ADK class at build time, not import time
    deferred_line = gen_deferred_import_line(spec)
    if deferred_line:
        body.append(RawStmt(deferred_line))

    # Guard against missing optional dependency at build time
    if _is_optional_source(spec.source_class):
        body.append(
            IfStmt(
                condition=f"{class_short} is None",
                body=(
                    RawStmt(
                        "raise ImportError("
                        '"A2A support requires the a2a SDK. '
                        "Install with: pip install 'google-adk[a2a]'\")"
                    ),
                ),
            )
        )

    body.extend(
        [
            AssignStmt("config", "self._prepare_build_config()"),
            AssignStmt("result", f"self._safe_build({class_short}, config)"),
            ReturnStmt("self._apply_native_hooks(result)"),
        ]
    )

    return MethodNode(
        name="build",
        params=[Param("self")],
        returns=class_short,
        doc=f"{spec.doc} Resolve into a native ADK {class_short}.",
        body=body,
    )


# ---------------------------------------------------------------------------
# ASSEMBLY: spec → ClassNode
# ---------------------------------------------------------------------------


def spec_to_ir(spec: BuilderSpec) -> ClassNode:
    """Convert a BuilderSpec into a complete ClassNode IR."""
    attrs = ir_class_attrs(spec)

    methods: list[MethodNode] = []
    methods.append(ir_init_method(spec))
    methods.extend(ir_alias_methods(spec))
    methods.extend(ir_deprecated_alias_methods(spec))
    methods.extend(ir_callback_methods(spec))
    methods.extend(ir_field_methods(spec))
    methods.extend(ir_extra_methods(spec))

    build = ir_build_method(spec)
    if build:
        methods.append(build)

    return ClassNode(
        name=spec.name,
        bases=["BuilderBase"],
        doc=spec.doc,
        attrs=attrs,
        methods=methods,
    )
