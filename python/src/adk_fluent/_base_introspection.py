"""Introspection & explainability mixin for :class:`~adk_fluent._base.BuilderBase`.

Holds the human-facing inspection surface: ``explain`` (plain / rich / json),
``inspect``, the docs-URL resolver, and their private helpers. Split out of
``_base.py`` to keep the core builder class focused on the fluent chain
machinery.

These methods read builder state (``self._config`` / ``self._callbacks`` /
``self._lists``) and lean on a few helpers that remain on ``BuilderBase``
(``_format_value``, ``_reverse_alias``, ``_reverse_callback_alias``) — resolved
at runtime through the MRO. The single module-level dependency on
``_count_components`` is imported lazily to avoid an import cycle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from adk_fluent._base import BuilderBase  # noqa: F401


class IntrospectionMixin:
    """``explain`` / ``inspect`` / docs-URL surface for builders."""

    def _explain_plain(self) -> str:
        """Plain-text explain fallback (no rich dependency).

        Shows what the agent does, what data it reads/writes, how it sees
        conversation history, what tools it has, and any contract issues.
        Designed to be immediately useful for debugging data flow problems.
        """
        cls_name = self.__class__.__name__
        name = self._config.get("name", "?")
        lines = [f"{cls_name}: {name}"]

        # Model
        model = self._config.get("model")
        if model:
            lines.append(f"  Model: {model}")

        # Instruction summary
        instruction = self._config.get("instruction", "")
        if instruction:
            if callable(instruction):
                lines.append("  Instruction: <dynamic provider>")
            elif isinstance(instruction, str):
                import re

                # Show first 80 chars + template variables
                preview = instruction[:80].replace("\n", " ")
                if len(instruction) > 80:
                    preview += "..."
                lines.append(f"  Instruction: {preview}")

                # Extract template variables
                template_vars = re.findall(r"\{(\w+)\??\}", instruction)
                if template_vars:
                    required = [v for v in template_vars if f"{{{v}?}}" not in instruction]
                    optional = [v for v in template_vars if f"{{{v}?}}" in instruction]
                    parts = []
                    if required:
                        parts.append(f"required: {', '.join(required)}")
                    if optional:
                        parts.append(f"optional: {', '.join(optional)}")
                    lines.append(f"  Template vars: {'; '.join(parts)}")

        # Data flow: unified five-concern view
        context_spec = self._config.get("_context_spec")
        input_schema = self._config.get("input_schema")
        output_schema = self._config.get("_output_schema") or self._config.get("output_schema")
        output_key = self._config.get("output_key")
        produces_schema = self._config.get("_produces")
        consumes_schema = self._config.get("_consumes")

        lines.append("  Data flow:")

        # reads (context)
        if context_spec is not None:
            from adk_fluent.testing.contracts import _context_description

            lines.append(f"    reads:    {_context_description(context_spec)}")
        else:
            lines.append("    reads:    full conversation history (default)")

        # accepts (input)
        if input_schema is not None:
            schema_name = getattr(input_schema, "__name__", str(input_schema))
            lines.append(f"    accepts:  {schema_name} (tool-mode input validation)")
        else:
            lines.append("    accepts:  (not set — accepts any input as tool)")

        # returns (output)
        if output_schema is not None:
            schema_name = getattr(output_schema, "__name__", str(output_schema))
            lines.append(f"    returns:  {schema_name} (structured JSON — tools disabled)")
        else:
            lines.append("    returns:  plain text (default — can use tools)")

        # writes (storage)
        if output_key:
            lines.append(f'    writes:   state["{output_key}"]')
        else:
            lines.append("    writes:   (not set — response only in conversation)")

        # contract
        contract_parts = []
        if produces_schema:
            fields = list(produces_schema.model_fields.keys())
            contract_parts.append(f"produces {produces_schema.__name__}({', '.join(fields)})")
        if consumes_schema:
            fields = list(consumes_schema.model_fields.keys())
            contract_parts.append(f"consumes {consumes_schema.__name__}({', '.join(fields)})")
        if contract_parts:
            lines.append(f"    contract: {', '.join(contract_parts)}")
        else:
            lines.append("    contract: (not set)")

        # Tools
        tools = list(self._config.get("tools", []))
        tools.extend(self._lists.get("tools", []))
        if tools:
            tool_names = []
            for t in tools:
                if hasattr(t, "name"):
                    tool_names.append(t.name)
                elif hasattr(t, "__name__"):
                    tool_names.append(t.__name__)
                else:
                    tool_names.append(type(t).__name__)
            lines.append(f"  Tools ({len(tools)}): {', '.join(tool_names)}")

        for field, fns in self._callbacks.items():
            if fns:
                alias = self._reverse_callback_alias(field)
                lines.append(f"  Callback '{alias}': {len(fns)} registered")

        # Sub-agents
        children_raw = list(self._config.get("sub_agents", []))
        children_raw.extend(self._lists.get("sub_agents", []))
        if children_raw:
            child_names = [
                getattr(c, "_config", {}).get("name", "?") if hasattr(c, "_config") else str(c) for c in children_raw
            ]
            lines.append(f"  Children ({len(children_raw)}): {', '.join(child_names)}")

        # Other list fields
        for field, items in self._lists.items():
            if items and field != "sub_agents":
                lines.append(f"  {field}: {len(items)} items")

        # Contract issues (if IR is available)
        try:
            ir = self.to_ir()
            from adk_fluent.testing.contracts import check_contracts

            issues = check_contracts(ir)
            if issues:
                lines.append("  Contract issues:")
                for issue in issues:
                    if isinstance(issue, str):
                        lines.append(f"    - {issue}")
                    else:
                        level = issue.get("level", "?")
                        agent = issue.get("agent", "?")
                        msg = issue.get("message", "?")
                        hint = issue.get("hint", "")
                        marker = "ERROR" if level == "error" else "INFO"
                        lines.append(f"    [{marker}] {agent}: {msg}")
                        if hint:
                            lines.append(f"           Hint: {hint}")
        except (NotImplementedError, AttributeError, ImportError):
            pass  # IR not available or conversion failed

        return "\n".join(lines)

    def _build_rich_tree(self):
        """Build a rich.tree.Tree representing this builder's state."""
        import re

        from rich.tree import Tree  # type: ignore[reportMissingImports]

        cls_name = self.__class__.__name__
        name = self._config.get("name", "?")
        tree = Tree(f"[bold]{cls_name}[/bold]: {name}")

        # Model
        model = self._config.get("model")
        if model:
            tree.add(f"[cyan]Model[/cyan]: {model}")

        # Instruction summary
        instruction = self._config.get("instruction", "")
        if instruction:
            if callable(instruction):
                tree.add("[cyan]Instruction[/cyan]: <dynamic provider>")
            elif isinstance(instruction, str):
                preview = instruction[:80].replace("\n", " ")
                if len(instruction) > 80:
                    preview += "..."
                tree.add(f"[cyan]Instruction[/cyan]: {preview}")

                template_vars = re.findall(r"\{(\w+)\??\}", instruction)
                if template_vars:
                    required = [v for v in template_vars if f"{{{v}?}}" not in instruction]
                    optional = [v for v in template_vars if f"{{{v}?}}" in instruction]
                    parts = []
                    if required:
                        parts.append(f"required: {', '.join(required)}")
                    if optional:
                        parts.append(f"optional: {', '.join(optional)}")
                    tree.add(f"[cyan]Template vars[/cyan]: {'; '.join(parts)}")

        # Data flow: unified five-concern view
        context_spec = self._config.get("_context_spec")
        input_schema = self._config.get("input_schema")
        output_schema = self._config.get("_output_schema") or self._config.get("output_schema")
        output_key = self._config.get("output_key")
        produces_schema = self._config.get("_produces")
        consumes_schema = self._config.get("_consumes")

        df_branch = tree.add("[blue]Data flow[/blue]")

        # reads (context)
        if context_spec is not None:
            from adk_fluent.testing.contracts import _context_description

            df_branch.add(f"[magenta]reads[/magenta]:    {_context_description(context_spec)}")
        else:
            df_branch.add("[dim]reads:    full conversation history (default)[/dim]")

        # accepts (input)
        if input_schema is not None:
            schema_name = getattr(input_schema, "__name__", str(input_schema))
            df_branch.add(f"[cyan]accepts[/cyan]:  {schema_name} (tool-mode input validation)")
        else:
            df_branch.add("[dim]accepts:  (not set)[/dim]")

        # returns (output)
        if output_schema is not None:
            schema_name = getattr(output_schema, "__name__", str(output_schema))
            df_branch.add(f"[cyan]returns[/cyan]:  {schema_name} (structured JSON — tools disabled)")
        else:
            df_branch.add("[dim]returns:  plain text (default — can use tools)[/dim]")

        # writes (storage)
        if output_key:
            df_branch.add(f'[green]writes[/green]:   state["{output_key}"]')
        else:
            df_branch.add("[dim]writes:   (not set — response only in conversation)[/dim]")

        # contract
        contract_parts = []
        if produces_schema:
            fields = list(produces_schema.model_fields.keys())
            contract_parts.append(f"produces {produces_schema.__name__}({', '.join(fields)})")
        if consumes_schema:
            fields = list(consumes_schema.model_fields.keys())
            contract_parts.append(f"consumes {consumes_schema.__name__}({', '.join(fields)})")
        if contract_parts:
            df_branch.add(f"[yellow]contract[/yellow]: {', '.join(contract_parts)}")
        else:
            df_branch.add("[dim]contract: (not set)[/dim]")

        # Tools
        tools = list(self._config.get("tools", []))
        tools.extend(self._lists.get("tools", []))
        if tools:
            tool_names = []
            for t in tools:
                if hasattr(t, "name"):
                    tool_names.append(t.name)
                elif hasattr(t, "__name__"):
                    tool_names.append(t.__name__)
                else:
                    tool_names.append(type(t).__name__)
            tree.add(f"[yellow]Tools ({len(tools)})[/yellow]: {', '.join(tool_names)}")

        # Other config fields (not already shown)
        _shown = {
            "name",
            "model",
            "instruction",
            "_produces",
            "_consumes",
            "output_key",
            "_context_spec",
            "include_contents",
            "_output_schema",
            "output_schema",
            "input_schema",
            "tools",
        }
        other_fields = {k: v for k, v in self._config.items() if k not in _shown and not k.startswith("_")}
        if other_fields:
            cfg_branch = tree.add("[cyan]Config[/cyan]")
            for k, v in other_fields.items():
                display_name = self._reverse_alias(k)
                cfg_branch.add(f"{display_name}: {self._format_value(v)}")

        # Callbacks
        for field, fns in self._callbacks.items():
            if fns:
                alias = self._reverse_callback_alias(field)
                cb_branch = tree.add(f"[green]Callback '{alias}'[/green]: {len(fns)} registered")
                for fn in fns:
                    cb_branch.add(self._format_value(fn))

        # Sub-agents and other list fields
        children_raw = list(self._config.get("sub_agents", []))
        children_raw.extend(self._lists.get("sub_agents", []))
        if children_raw:
            children_branch = tree.add(f"[yellow]Children ({len(children_raw)})[/yellow]")
            for child in children_raw:
                if isinstance(child, BuilderBase):
                    children_branch.add(child._build_rich_tree())
                else:
                    children_branch.add(self._format_value(child))

        for field, items in self._lists.items():
            if items and field != "sub_agents":
                list_branch = tree.add(f"[yellow]{field}[/yellow]: {len(items)} items")
                for item in items:
                    if isinstance(item, BuilderBase):
                        list_branch.add(item._build_rich_tree())
                    else:
                        list_branch.add(self._format_value(item))

        # Contract issues
        try:
            ir = self.to_ir()
            from adk_fluent.testing.contracts import check_contracts

            issues = check_contracts(ir)
            if issues:
                issues_branch = tree.add("[red]Contract issues[/red]")
                for issue in issues:
                    if isinstance(issue, str):
                        issues_branch.add(issue)
                    else:
                        level = issue.get("level", "?")
                        agent = issue.get("agent", "?")
                        msg = issue.get("message", "?")
                        hint = issue.get("hint", "")
                        marker = "[red]ERROR[/red]" if level == "error" else "[yellow]INFO[/yellow]"
                        node = issues_branch.add(f"{marker} {agent}: {msg}")
                        if hint:
                            node.add(f"[dim]Hint: {hint}[/dim]")
        except (NotImplementedError, AttributeError, ImportError):
            pass  # IR not available or conversion failed

        return tree

    # Docs base URL — override with ADKFLUENT_DOCS_URL env var or docs_url= parameter
    _DOCS_BASE_URL = "https://vamsiramakrishnan.github.io/adk-fluent"

    # Map builder class names to their API reference doc page
    _DOCS_PAGE_MAP: dict[str, str] = {
        "Agent": "api/agent",
        "BaseAgent": "api/agent",
        "Pipeline": "api/workflow",
        "Loop": "api/workflow",
        "FanOut": "api/workflow",
        "Runner": "api/runtime",
        "InMemoryRunner": "api/runtime",
        "App": "api/runtime",
    }

    def _docs_url_for(self, base_url: str | None = None) -> str:
        """Return the docs URL for this builder's API reference page."""
        import os

        base = base_url or os.environ.get("ADKFLUENT_DOCS_URL", self._DOCS_BASE_URL)
        base = base.rstrip("/")
        cls_name = self.__class__.__name__
        page = self._DOCS_PAGE_MAP.get(cls_name)
        if page is None:
            # Infer from class name suffix
            if cls_name.endswith("Config"):
                page = "api/config"
            elif cls_name.endswith("Service"):
                page = "api/service"
            elif cls_name.endswith("Tool") or cls_name.endswith("Toolset"):
                page = "api/tool"
            elif cls_name.endswith("Plugin"):
                page = "api/plugin"
            elif cls_name.endswith("Planner"):
                page = "api/planner"
            elif cls_name.endswith("Executor"):
                page = "api/executor"
            else:
                page = "api"
        return f"{base}/{page}/"

    def explain(
        self,
        *,
        format: str = "text",
        docs_url: str | None = None,
        open_browser: bool = False,
    ) -> str | dict:
        """Return a multi-line summary of this builder's state.

        Parameters
        ----------
        format:
            ``"text"`` (default) for human-readable output (rich if available,
            plain otherwise).  ``"json"`` for a machine-readable dict.
        docs_url:
            Base URL for docs links appended to output.  Defaults to the
            published GitHub Pages site.  Set ``ADKFLUENT_DOCS_URL`` env
            var to override globally.
        open_browser:
            If ``True``, open the relevant API docs page in the default
            browser after printing.

        Returns
        -------
        str | dict
            Formatted text when ``format="text"``, a dict when
            ``format="json"``.
        """
        if format == "json":
            result = self._explain_json(docs_url=docs_url)
            if open_browser:
                self._open_docs(docs_url)
            return result

        # --- text mode ---
        try:
            from rich.console import Console  # type: ignore[reportMissingImports]

            tree = self._build_rich_tree()
            console = Console(record=True, width=120)
            console.print(tree)
            text = console.export_text()
        except ImportError:
            text = self._explain_plain()

        # Append docs link
        ref_url = self._docs_url_for(docs_url)
        text += f"\n  Docs: {ref_url}"

        if open_browser:
            self._open_docs(docs_url)

        return text

    def _explain_json(self, *, docs_url: str | None = None) -> dict:
        """Return a structured dict representation of this builder's state."""
        cls_name = self.__class__.__name__
        name = self._config.get("name", "?")
        model = self._config.get("model")
        instruction = self._config.get("instruction", "")

        result: dict[str, Any] = {
            "builder": cls_name,
            "name": name,
            "docs_url": self._docs_url_for(docs_url),
        }

        if model:
            result["model"] = model
        if instruction:
            if callable(instruction):
                result["instruction"] = "<dynamic provider>"
            else:
                result["instruction"] = instruction[:200] + ("..." if len(str(instruction)) > 200 else "")

        # Data flow (five concerns)
        context_spec = self._config.get("_context_spec")
        input_schema = self._config.get("input_schema")
        output_schema = self._config.get("_output_schema") or self._config.get("output_schema")
        output_key = self._config.get("output_key")
        produces = self._config.get("_produces")
        consumes = self._config.get("_consumes")
        data_flow: dict[str, Any] = {}
        if context_spec is not None:
            from adk_fluent.testing.contracts import _context_description

            data_flow["reads"] = _context_description(context_spec)
        if input_schema is not None:
            data_flow["accepts"] = {
                "schema": input_schema.__name__,
                "fields": list(input_schema.model_fields.keys()) if hasattr(input_schema, "model_fields") else [],
            }
        if output_schema is not None:
            data_flow["returns"] = {
                "schema": output_schema.__name__,
                "fields": list(output_schema.model_fields.keys()) if hasattr(output_schema, "model_fields") else [],
            }
        if output_key:
            data_flow["writes"] = output_key
        if consumes:
            data_flow["consumes"] = {"schema": consumes.__name__, "fields": list(consumes.model_fields.keys())}
        if produces:
            data_flow["produces"] = {"schema": produces.__name__, "fields": list(produces.model_fields.keys())}
        if data_flow:
            result["data_flow"] = data_flow

        # UI
        ui_spec = self._config.get("_ui_spec")
        if ui_spec is not None:
            ui_info: dict[str, Any] = {}
            from adk_fluent._base import _count_components
            from adk_fluent._ui import UISurface, _UIAutoSpec

            if isinstance(ui_spec, UISurface):
                ui_info["surface"] = ui_spec.name
                ui_info["mode"] = "declarative"
                if ui_spec.root is not None:
                    ui_info["components"] = _count_components(ui_spec.root)
            elif isinstance(ui_spec, _UIAutoSpec):
                ui_info["mode"] = "llm_guided"
                ui_info["catalog"] = ui_spec.catalog
            else:
                ui_info["mode"] = "declarative"
            result["ui"] = ui_info

        # Tools
        tools = list(self._config.get("tools", []))
        tools.extend(self._lists.get("tools", []))
        if tools:
            result["tools"] = [
                getattr(t, "name", None) or getattr(t, "__name__", None) or type(t).__name__ for t in tools
            ]

        # Callbacks
        cbs = {}
        for field, fns in self._callbacks.items():
            if fns:
                alias = self._reverse_callback_alias(field)
                cbs[alias] = len(fns)
        if cbs:
            result["callbacks"] = cbs

        # Children
        children_raw = list(self._config.get("sub_agents", []))
        children_raw.extend(self._lists.get("sub_agents", []))
        if children_raw:
            result["children"] = [
                getattr(c, "_config", {}).get("name", "?") if hasattr(c, "_config") else str(c) for c in children_raw
            ]

        # Config (other fields)
        _skip = {
            "name",
            "model",
            "instruction",
            "_produces",
            "_consumes",
            "output_key",
            "input_schema",
            "output_schema",
            "tools",
            "sub_agents",
        }
        other = {k: repr(v) for k, v in self._config.items() if k not in _skip and not k.startswith("_")}
        if other:
            result["config"] = other

        # Contract issues
        try:
            ir = self.to_ir()
            from adk_fluent.testing.contracts import check_contracts

            issues = check_contracts(ir)
            if issues:
                result["contract_issues"] = [
                    {"level": i.get("level", "?"), "agent": i.get("agent", "?"), "message": i.get("message", "?")}
                    if isinstance(i, dict)
                    else {"message": str(i)}
                    for i in issues
                ]
        except (NotImplementedError, AttributeError, ImportError):
            pass

        return result

    def _open_docs(self, docs_url: str | None = None) -> None:
        """Open the API reference docs page in the default browser."""
        import webbrowser

        webbrowser.open(self._docs_url_for(docs_url))

    def inspect(self) -> str:
        """Return a detailed view of this builder's full config values."""
        cls_name = self.__class__.__name__
        name = self._config.get("name", "?")
        lines = [f"{cls_name}: {name}"]

        for k, v in self._config.items():
            if k == "name":
                continue
            display_name = self._reverse_alias(k)
            lines.append(f"  {display_name} = {v!r}")

        for field, fns in self._callbacks.items():
            if fns:
                alias = self._reverse_callback_alias(field)
                lines.append(f"  {alias} = {fns!r}")

        for field, items in self._lists.items():
            if items:
                lines.append(f"  {field} = {items!r}")

        return "\n".join(lines)
