"""Import resolution — determines what imports are needed in generated code.

Handles:
  - Runtime imports for builder .py files
  - TYPE_CHECKING-guarded imports for type stubs
  - Auto-discovery of ADK/genai types from manifest
  - Import override table for types with incorrect runtime discovery
"""

from __future__ import annotations

import re
from collections import defaultdict

from .spec import BuilderSpec

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------


def adk_import_name(spec: BuilderSpec) -> str:
    """Return the name used to reference the ADK class in generated code.

    When the builder has the same name as the ADK class, we alias the import
    to _ADK_ClassName to avoid shadowing.
    """
    class_name = spec.source_class.split(".")[-1]
    if spec.name == class_name:
        return f"_ADK_{class_name}"
    return class_name


# Module prefixes that require optional dependencies at import time.
# These imports are wrapped in try/except with a None fallback.
_OPTIONAL_IMPORT_PREFIXES = (
    "google.adk.a2a.",                     # requires: pip install 'google-adk[a2a]'
    "google.adk.agents.remote_a2a_agent",  # imports a2a SDK internally
)


def _is_optional_source(source_class: str) -> bool:
    """Check if a source class requires an optional dependency."""
    return any(source_class.startswith(prefix) for prefix in _OPTIONAL_IMPORT_PREFIXES)


def gen_runtime_imports(spec: BuilderSpec) -> list[str]:
    """Return raw import lines for a single builder spec (no header/grouping).

    Does NOT include optional imports — call ``gen_optional_import`` separately.
    """
    lines = [
        "from collections import defaultdict",
        "from collections.abc import Callable",
        "from typing import Any, Self",
        "from adk_fluent._base import BuilderBase",
    ]

    if not spec.is_composite and not spec.is_standalone:
        if _is_optional_source(spec.source_class):
            return lines  # handled by gen_optional_import
        module_path = ".".join(spec.source_class.split(".")[:-1])
        class_name = spec.source_class.split(".")[-1]
        import_name = adk_import_name(spec)
        if import_name != class_name:
            lines.append(f"from {module_path} import {class_name} as {import_name}")
        else:
            lines.append(f"from {module_path} import {class_name}")

    return lines


def gen_optional_import(spec: BuilderSpec) -> tuple[str, str] | None:
    """Return an optional import tuple ``(import_line, fallback)`` if needed.

    Returns ``None`` if the spec does not require an optional import.
    """
    if spec.is_composite or spec.is_standalone:
        return None
    if not _is_optional_source(spec.source_class):
        return None

    module_path = ".".join(spec.source_class.split(".")[:-1])
    class_name = spec.source_class.split(".")[-1]
    import_name = adk_import_name(spec)
    if import_name != class_name:
        import_line = f"from {module_path} import {class_name} as {import_name}"
    else:
        import_line = f"from {module_path} import {class_name}"
    fallback = f"{import_name} = None  # type: ignore[assignment,misc]"
    return import_line, fallback


# ---------------------------------------------------------------------------
# IMPORT CORRECTNESS OVERRIDES
# ---------------------------------------------------------------------------

# Maps type names to their correct import statements, overriding runtime
# discovery.  Needed because pkgutil.walk_packages finds types in the first
# module that has the attribute, but pyright requires imports from the
# defining module (where __module__ matches or the symbol is assigned).
IMPORT_OVERRIDES: dict[str, str] = {
    # Pydantic
    "BaseModel": "from pydantic import BaseModel",
    # FastAPI OpenAPI models (re-exported by ADK but not in their __all__)
    "OAuth2": "from fastapi.openapi.models import OAuth2",
    "HTTPBearer": "from fastapi.openapi.models import HTTPBearer",
    "APIKey": "from fastapi.openapi.models import APIKey",
    "HTTPBase": "from fastapi.openapi.models import HTTPBase",
    "OpenIdConnect": "from fastapi.openapi.models import OpenIdConnect",
    "Operation": "from fastapi.openapi.models import Operation",
    # MCP protocol types
    "StdioServerParameters": "from mcp.client.stdio import StdioServerParameters",
    "ProgressFnT": "from mcp.shared.session import ProgressFnT",
    # ADK types where runtime discovery finds wrong re-exporting module
    "ToolPredicate": "from google.adk.tools.base_toolset import ToolPredicate",
    "APIHubClient": "from google.adk.tools.apihub_tool.clients.apihub_client import APIHubClient",
    "BigQueryToolConfig": "from google.adk.tools.bigquery.config import BigQueryToolConfig",
    "BigQueryCredentialsConfig": "from google.adk.tools.bigquery.bigquery_credentials import BigQueryCredentialsConfig",
    "BigtableToolSettings": "from google.adk.tools.bigtable.settings import BigtableToolSettings",
    "BigtableCredentialsConfig": "from google.adk.tools.bigtable.bigtable_credentials import BigtableCredentialsConfig",
    "SpannerToolSettings": "from google.adk.tools.spanner.settings import SpannerToolSettings",
    "SpannerCredentialsConfig": "from google.adk.tools.spanner.spanner_credentials import SpannerCredentialsConfig",
    "DataAgentCredentialsConfig": "from google.adk.tools.data_agent.credentials import DataAgentCredentialsConfig",
    "DataAgentToolConfig": "from google.adk.tools.data_agent.config import DataAgentToolConfig",
    "PubSubCredentialsConfig": "from google.adk.tools.pubsub.pubsub_credentials import PubSubCredentialsConfig",
    "PubSubToolConfig": "from google.adk.tools.pubsub.config import PubSubToolConfig",
    # AuthScheme is a Union alias defined at module level in auth_schemes
    "AuthScheme": "from google.adk.auth.auth_schemes import AuthScheme",
    # google.genai.types that appear without module prefix after normalization
    "VertexAISearchDataStoreSpec": "from google.genai.types import VertexAISearchDataStoreSpec",
    "ThinkingConfig": "from google.genai.types import ThinkingConfig",
    # A2A SDK types (a2a package, not google.adk.a2a)
    "RequestContext": "from a2a.server.agent_execution.context import RequestContext",
    "AgentRunRequest": "from google.adk.a2a.converters.request_converter import AgentRunRequest",
}

# Types that cannot be resolved at stub-generation time (optional deps,
# private internals, forward-only references).  Replaced with ``Any``.
UNRESOLVABLE_TYPES: set[str] = {
    "Task",  # asyncio.Task (appears as bare "Task" from string annotation)
    "CredentialConfig",  # toolbox_adk.CredentialConfig (optional dependency)
    "_ArtifactEntry",  # private internal type
}

# Module-qualified prefixes in type_str that should be stripped.
# In ADK, "types.X" always means "google.genai.types.X".
MODULE_PREFIX_REWRITES: dict[str, str] = {
    "types.": "",
    "genai_types.": "",
}

# Module-qualified prefixes that need their own imports (kept in type string).
STDLIB_MODULE_REFS: dict[str, str] = {
    "ssl.": "import ssl",
    "a2a.types.": "import a2a.types",
}

# Module imports from STDLIB_MODULE_REFS that require optional dependencies.
# These are emitted as try/except with a pass fallback instead of bare imports.
OPTIONAL_MODULE_IMPORTS: set[str] = {
    "import a2a.types",
}

# Stdlib typing names that need explicit imports when referenced in stubs.
TYPING_NAMES: dict[str, str] = {
    "Union": "typing",
    "Optional": "typing",
    "Literal": "typing",
    "Awaitable": "collections.abc",
    "AsyncIterator": "collections.abc",
    "Mapping": "collections.abc",
    "Sequence": "collections.abc",
    "Dict": "typing",
    "TextIO": "typing",
}


# ---------------------------------------------------------------------------
# TYPE IMPORT MAP BUILDER
# ---------------------------------------------------------------------------


def build_type_import_map(manifest: dict) -> dict[str, str]:
    """Build a map of short type names to their fully-qualified import paths.

    Scans all ``type_raw`` fields in the manifest to discover every ADK/genai
    type and its module path, producing entries like:
        ``{"BaseAgent": "from google.adk.agents.base_agent import BaseAgent"}``

    Also performs runtime discovery for types referenced in ``type_str`` but
    missing from ``type_raw`` (e.g. types from forward-reference annotations).
    """
    type_map: dict[str, str] = {}

    # Phase 0: apply explicit overrides (correct defining modules)
    type_map.update(IMPORT_OVERRIDES)

    # Phase 1: extract from fully-qualified type_raw strings
    for cls in manifest.get("classes", []):
        all_params = cls.get("fields", []) + cls.get("init_params", [])
        for field in all_params:
            raw = field.get("type_raw", "")
            for fqn in re.findall(r"(google\.\w+(?:\.\w+)+)", raw):
                short_name = fqn.split(".")[-1]
                module_path = ".".join(fqn.split(".")[:-1])
                if short_name not in type_map:
                    type_map[short_name] = f"from {module_path} import {short_name}"

    # Phase 2: collect type names from type_str that we can't resolve yet
    _IDENT = re.compile(r"\b([A-Z]\w+)")
    _SKIP = {
        "Any",
        "Self",
        "None",
        "Callable",
        "AsyncGenerator",
        "BuilderBase",
        "Union",
        "Optional",
        "Literal",
        "List",
        "Dict",
        "Tuple",
        "Set",
    }
    unresolved: set[str] = set()
    for cls in manifest.get("classes", []):
        # Scan both fields and init_params for type references
        all_params = cls.get("fields", []) + cls.get("init_params", [])
        for field in all_params:
            for name in _IDENT.findall(field.get("type_str", "")):
                if name not in type_map and name not in _SKIP:
                    unresolved.add(name)

    # Phase 3: runtime discovery for unresolved types
    # Walk in sorted module order and prefer the defining module (__module__)
    # for deterministic output across environments.
    if unresolved:
        import importlib
        import pkgutil

        try:
            import google.adk

            # Collect all (modname, name) candidates first, then pick best
            candidates: dict[str, list[str]] = defaultdict(list)
            all_modules = sorted(
                modname for _imp, modname, _ispkg in pkgutil.walk_packages(google.adk.__path__, "google.adk.")
            )
            for modname in all_modules:
                if not unresolved:
                    break
                try:
                    mod = importlib.import_module(modname)
                except Exception:
                    continue
                for name in list(unresolved):
                    obj = getattr(mod, name, None)
                    if obj is not None:
                        # Prefer the module where the type is defined
                        defining_mod = getattr(obj, "__module__", None)
                        if defining_mod == modname:
                            # Exact match — use it immediately
                            type_map[name] = f"from {modname} import {name}"
                            unresolved.discard(name)
                            candidates.pop(name, None)
                        elif name not in type_map:
                            candidates[name].append(modname)

            # For remaining unresolved, use first sorted candidate
            for name in sorted(candidates):
                if name in unresolved and candidates[name]:
                    best = candidates[name][0]  # already sorted
                    type_map[name] = f"from {best} import {name}"
                    unresolved.discard(name)
        except ImportError:
            pass

    # Add pydantic BaseModel if referenced (fallback if override not present)
    if "BaseModel" not in type_map:
        type_map["BaseModel"] = "from pydantic import BaseModel"

    return type_map
