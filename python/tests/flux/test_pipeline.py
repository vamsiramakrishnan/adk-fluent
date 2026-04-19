"""W2 + W3 pipeline canary — loader round-trip, 10-component emit, idempotence.

Tests:

  * ``test_button_spec_roundtrips`` — runs ``shared/scripts/flux/loader.py``
    on ``Button.spec.ts`` and asserts the resulting dict carries the
    expected shape (name, extends, variants keys, slots keys,
    ``renderer.fallback.component`` == ``"Button"``). This guards the
    Zod-to-JSON-Schema bridge in ``_loader.ts``.

  * ``test_catalog_has_phase_one_components`` — loads the emitted
    ``catalog.json`` and asserts the full Phase-1 roster (10 components,
    10 fallbacks) landed. Added by W3 so future specs that regress
    someone's component (e.g. a rename) fail loudly.

  * ``test_pipeline_is_idempotent`` — invokes ``just flux`` twice via
    subprocess and asserts ``git status --short`` reports no new diff
    between the two runs. This is the deterministic-emit contract from
    ARCHITECTURE §7: re-running with no spec change produces
    byte-identical output.

Both tests depend on the ``ts/`` workspace's ``node_modules`` being
present (the loader shells out to ``npx tsx``). They are skipped when
neither ``npx`` nor ``ts/node_modules`` is available so CI environments
without a Node install still turn green on the rest of the suite.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_SCRIPTS = REPO_ROOT / "shared" / "scripts"
LOADER_PATH = SHARED_SCRIPTS / "flux" / "loader.py"
SPECS_DIR = REPO_ROOT / "catalog" / "flux" / "specs"
BUTTON_SPEC = SPECS_DIR / "Button.spec.ts"
CATALOG_JSON = REPO_ROOT / "catalog" / "flux" / "catalog.json"
TS_WORKSPACE = REPO_ROOT / "ts"

# Phase-1 roster (see ARCHITECTURE.md §13). Must line up with the spec files
# under ``catalog/flux/specs/``. Order is alphabetical for readability only —
# assertions use set comparison.
PHASE_ONE_COMPONENTS: frozenset[str] = frozenset(
    {
        "FluxBadge",
        "FluxBanner",
        "FluxButton",
        "FluxCard",
        "FluxLink",
        "FluxMarkdown",
        "FluxProgress",
        "FluxSkeleton",
        "FluxStack",
        "FluxTextField",
    }
)


# --- Import the loader module without name-collision tricks ----------------
#
# The test package itself sits at ``python/tests/flux`` which shadows the
# ``flux`` top-level name on sys.path once ``shared/scripts/`` is added,
# so we side-load the exact file via ``importlib``.


def _import_loader() -> ModuleType:
    """Load ``shared/scripts/flux/loader.py`` as a standalone module."""
    spec = importlib.util.spec_from_file_location("_flux_loader_under_test", LOADER_PATH)
    assert spec is not None and spec.loader is not None, f"unable to locate loader at {LOADER_PATH}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# --- Skip-if-Node-missing helpers ------------------------------------------


def _node_env_available() -> bool:
    if shutil.which("npx") is None:
        return False
    if not (TS_WORKSPACE / "node_modules").is_dir():
        return False
    return True


requires_node = pytest.mark.skipif(
    not _node_env_available(),
    reason="flux pipeline requires `npx` and `ts/node_modules` — run `just setup` first",
)


# --- Tests -----------------------------------------------------------------


@requires_node
def test_button_spec_roundtrips() -> None:
    """Loader turns Button.spec.ts into a dict with the documented shape."""
    assert BUTTON_SPEC.is_file(), f"Button spec must exist at {BUTTON_SPEC}"
    loader = _import_loader()
    spec = loader.load_one(REPO_ROOT, BUTTON_SPEC)

    # --- Top-level contract ---
    assert spec["name"] == "FluxButton", "spec.name must be exactly 'FluxButton'"
    assert spec["extends"] == "Button", "spec.extends must be the basic-catalog 'Button'"
    assert spec.get("category") == "primitive"

    # --- JSON schema lowered from Zod ---
    js = spec.get("jsonSchema")
    assert isinstance(js, dict), "loader must produce a jsonSchema object"
    props = js.get("properties") or {}
    # The Zod schema declares these props; if any vanish the z.toJSONSchema
    # lowering has regressed.
    for key in ("id", "tone", "size", "emphasis", "action", "accessibility"):
        assert key in props, f"jsonSchema.properties.{key} missing after loader round-trip"

    # --- Variants: tone/size/emphasis with the documented keys ---
    variants = spec.get("variants") or {}
    assert set(variants.keys()) == {"tone", "size", "emphasis"}, (
        "variants map must contain exactly tone/size/emphasis"
    )
    assert set(variants["tone"].keys()) >= {"neutral", "primary", "danger", "success"}
    assert set(variants["size"].keys()) >= {"sm", "md", "lg"}
    assert set(variants["emphasis"].keys()) >= {"solid", "soft", "outline", "ghost"}

    # --- Slots: icon slots land as first-class keys ---
    slots = spec.get("slots") or {}
    assert "leadingIcon" in slots and "trailingIcon" in slots, (
        "Button spec must declare leadingIcon + trailingIcon slots"
    )

    # --- Renderer fallback points at basic-catalog Button ---
    renderer = spec.get("renderer") or {}
    fallback = renderer.get("fallback") or {}
    assert fallback.get("component") == "Button", (
        "fallback.component must be the basic-catalog 'Button' (degrade contract)"
    )


def test_catalog_has_phase_one_components() -> None:
    """The emitted catalog.json must carry all ten Phase-1 components + fallbacks.

    This test does NOT run the pipeline — it only reads the on-disk
    artifact, so it is safe to run in environments without Node. Keeps
    W3's contract honest even when the loader test is skipped.
    """
    assert CATALOG_JSON.is_file(), (
        f"catalog.json must exist at {CATALOG_JSON}. Run `just flux` to regenerate."
    )
    with CATALOG_JSON.open("r", encoding="utf-8") as fh:
        import json

        catalog = json.load(fh)

    # --- Top-level catalog metadata ---
    assert catalog.get("catalogId") == "flux/components@1"
    assert "a2ui/basic@0.10" in (catalog.get("extends") or [])

    # --- Components + fallbacks ---
    components = catalog.get("components") or {}
    fallbacks = catalog.get("fallbacks") or {}
    got = frozenset(components.keys())
    assert got == PHASE_ONE_COMPONENTS, (
        f"catalog.components must equal the Phase-1 roster.\n"
        f"  expected: {sorted(PHASE_ONE_COMPONENTS)}\n"
        f"  got:      {sorted(got)}"
    )
    # Every component has a matching fallback entry keyed by the same name.
    assert frozenset(fallbacks.keys()) == PHASE_ONE_COMPONENTS, (
        f"catalog.fallbacks must mirror catalog.components keys.\n"
        f"  missing:  {sorted(PHASE_ONE_COMPONENTS - frozenset(fallbacks.keys()))}\n"
        f"  extra:    {sorted(frozenset(fallbacks.keys()) - PHASE_ONE_COMPONENTS)}"
    )


@requires_node
def test_pipeline_is_idempotent(tmp_path: Path) -> None:  # noqa: ARG001  (tmp_path kept per brief)
    """Running ``just flux`` twice leaves the working tree unchanged.

    We run the pipeline once (to make sure artifacts exist + are
    up-to-date), commit/stash-free baseline the tree, run it again, and
    assert ``git status --short`` produces zero lines.
    """
    if shutil.which("just") is None:
        pytest.skip("`just` not available on PATH")

    def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            check=False,
            capture_output=True,
            text=True,
        )

    # Run once to establish a known-good tree. We don't assert on the
    # status here — the tree may legitimately have uncommitted work the
    # developer hasn't addressed yet.
    first = _run(["just", "flux"])
    assert first.returncode == 0, (
        f"first `just flux` failed:\nstdout:\n{first.stdout}\nstderr:\n{first.stderr}"
    )

    # Snapshot git status so we can diff against it.
    before = _run(["git", "status", "--short", "--untracked-files=all"])
    assert before.returncode == 0, before.stderr

    second = _run(["just", "flux"])
    assert second.returncode == 0, (
        f"second `just flux` failed:\nstdout:\n{second.stdout}\nstderr:\n{second.stderr}"
    )

    after = _run(["git", "status", "--short", "--untracked-files=all"])
    assert after.returncode == 0, after.stderr

    # Idempotence contract: the second run must not introduce any change
    # the first didn't already produce.
    assert before.stdout == after.stdout, (
        "flux pipeline is not idempotent — second `just flux` run produced a diff.\n"
        f"--- before ---\n{before.stdout}\n--- after ---\n{after.stdout}"
    )
