"""W1 test suite — flux token packs + schemas.

Validates that:
  * both shipped token packs (flux-light, flux-dark) conform to
    ``schema/tokens.schema.json``,
  * the two packs expose the exact same leaf-key set (Phase-1 invariant
    from ARCHITECTURE.md §4.2: "Both expose the same keyset — values
    differ, keys do not."),
  * every token path referenced by the reference component spec
    (``specs/Button.spec.ts``) resolves in both packs,
  * the hand-translated Button fixture validates against
    ``schema/component.schema.json``,
  * unknown keys injected into a pack fail validation with a
    human-readable error message.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema
import pytest

# ---------------------------------------------------------------------------
# Paths (always absolute so pytest can be invoked from any cwd)
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
CATALOG_DIR = REPO_ROOT / "catalog" / "flux"
SCHEMA_DIR = CATALOG_DIR / "schema"
TOKENS_DIR = CATALOG_DIR / "tokens"
SPECS_DIR = CATALOG_DIR / "specs"
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"

TOKENS_SCHEMA_PATH = SCHEMA_DIR / "tokens.schema.json"
COMPONENT_SCHEMA_PATH = SCHEMA_DIR / "component.schema.json"
LIGHT_PACK_PATH = TOKENS_DIR / "flux-light.json"
DARK_PACK_PATH = TOKENS_DIR / "flux-dark.json"
BUTTON_SPEC_PATH = SPECS_DIR / "Button.spec.ts"
BUTTON_FIXTURE_PATH = FIXTURE_DIR / "button.catalog.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict:
    """Read a JSON file from an absolute path, failing loudly if missing."""
    assert path.exists(), f"expected file to exist: {path}"
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _leaf_paths(obj: object, prefix: str = "") -> set[str]:
    """Return the set of dotted leaf-key paths for a nested dict.

    Leaves are any value that is not a dict.
    """
    paths: set[str] = set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            next_prefix = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                paths |= _leaf_paths(value, next_prefix)
            else:
                paths.add(next_prefix)
    return paths


def _resolve_token_path(pack: dict, path: str) -> bool:
    """Return True iff ``path`` resolves to a non-dict value in ``pack``."""
    cursor: object = pack
    for segment in path.split("."):
        if not isinstance(cursor, dict) or segment not in cursor:
            return False
        cursor = cursor[segment]
    # A resolved token is a concrete value, not an interior node.
    return not isinstance(cursor, dict)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def tokens_schema() -> dict:
    return _load_json(TOKENS_SCHEMA_PATH)


@pytest.fixture(scope="module")
def component_schema() -> dict:
    return _load_json(COMPONENT_SCHEMA_PATH)


@pytest.fixture(scope="module")
def light_pack() -> dict:
    return _load_json(LIGHT_PACK_PATH)


@pytest.fixture(scope="module")
def dark_pack() -> dict:
    return _load_json(DARK_PACK_PATH)


@pytest.fixture(scope="module")
def button_spec_source() -> str:
    assert BUTTON_SPEC_PATH.exists(), f"Button spec must exist at {BUTTON_SPEC_PATH}"
    return BUTTON_SPEC_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_light_pack_valid(tokens_schema: dict, light_pack: dict) -> None:
    """flux-light.json validates against tokens.schema.json."""
    try:
        jsonschema.validate(instance=light_pack, schema=tokens_schema)
    except jsonschema.ValidationError as exc:  # pragma: no cover - on failure only
        pytest.fail(f"flux-light.json failed schema validation: {exc.message}\npath: {list(exc.absolute_path)}")


def test_dark_pack_valid(tokens_schema: dict, dark_pack: dict) -> None:
    """flux-dark.json validates against tokens.schema.json."""
    try:
        jsonschema.validate(instance=dark_pack, schema=tokens_schema)
    except jsonschema.ValidationError as exc:  # pragma: no cover - on failure only
        pytest.fail(f"flux-dark.json failed schema validation: {exc.message}\npath: {list(exc.absolute_path)}")


def test_packs_have_identical_keysets(light_pack: dict, dark_pack: dict) -> None:
    """ARCHITECTURE §4.2: both packs expose the same keyset."""
    light_keys = _leaf_paths(light_pack)
    dark_keys = _leaf_paths(dark_pack)

    only_in_light = light_keys - dark_keys
    only_in_dark = dark_keys - light_keys

    assert not only_in_light, (
        "keys present in flux-light but missing in flux-dark — "
        "every key must appear in both packs: "
        f"{sorted(only_in_light)}"
    )
    assert not only_in_dark, (
        "keys present in flux-dark but missing in flux-light — "
        "every key must appear in both packs: "
        f"{sorted(only_in_dark)}"
    )
    assert light_keys == dark_keys, "token pack keysets diverged — see the set-difference assertions above"


# Paths that live OUTSIDE the semantic token namespaces (e.g. ``$meta``) and
# must not be treated as token references even if they appear in a string.
_NON_TOKEN_ROOTS = {
    "$meta",
    "$schema",
}


def _extract_token_refs(ts_source: str) -> set[str]:
    """Pull every ``$a.b.c`` token reference out of a TypeScript source blob.

    We scan string literals only (single, double, or backtick) and keep the
    leading ``$`` stripped payload. The Button spec also ships a separate
    ``tokens: [...]`` array listing the same paths without a leading ``$``;
    those are picked up by the `"..."` pattern below.
    """
    refs: set[str] = set()
    # 1. $-prefixed token refs inside string literals.
    for match in re.finditer(r"""(['"`])\$([a-zA-Z][\w]*(?:\.[\w]+)+)\1""", ts_source):
        refs.add(match.group(2))
    # 2. Plain "a.b.c" entries that appear inside the ``tokens: [...]`` list.
    tokens_block = re.search(r"tokens:\s*\[(.*?)\]", ts_source, re.DOTALL)
    if tokens_block is not None:
        for match in re.finditer(r"""['"`]([a-zA-Z][\w]*(?:\.[\w]+)+)['"`]""", tokens_block.group(1)):
            refs.add(match.group(1))
    # Filter out paths that are not token references.
    return {r for r in refs if r.split(".", 1)[0] not in _NON_TOKEN_ROOTS}


def test_packs_semantic_aliases_cover_baseline(
    button_spec_source: str,
    light_pack: dict,
    dark_pack: dict,
) -> None:
    """Every token path used by Button.spec.ts resolves in BOTH packs."""
    refs = _extract_token_refs(button_spec_source)
    assert refs, "parser did not find any token refs in Button.spec.ts — regex likely broke"

    missing_light = sorted(r for r in refs if not _resolve_token_path(light_pack, r))
    missing_dark = sorted(r for r in refs if not _resolve_token_path(dark_pack, r))

    assert not missing_light, (
        f"token paths referenced by Button.spec.ts that do NOT resolve in flux-light: {missing_light}"
    )
    assert not missing_dark, (
        f"token paths referenced by Button.spec.ts that do NOT resolve in flux-dark: {missing_dark}"
    )


def test_unknown_scale_key_fails_validation(
    tokens_schema: dict,
    light_pack: dict,
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Injecting ``color.brand.13`` into a pack must fail validation.

    This is the schema-strictness canary: if someone relaxes the scale12
    definition (drops ``additionalProperties: false`` or widens the
    pattern), this test catches the regression.
    """
    broken = json.loads(json.dumps(light_pack))  # deep copy
    broken["color"]["brand"]["13"] = "#000000"

    # Write to a tmp file so nothing mutates the committed JSON on disk.
    broken_path = Path(tmp_path) / "flux-light-broken.json"
    broken_path.write_text(json.dumps(broken), encoding="utf-8")
    reloaded = json.loads(broken_path.read_text(encoding="utf-8"))

    with pytest.raises(jsonschema.ValidationError) as exc_info:
        jsonschema.validate(instance=reloaded, schema=tokens_schema)

    message = exc_info.value.message
    assert "13" in message, (
        f"schema error must mention the offending key ('13') so authors can locate it fast; got: {message!r}"
    )
    # Readable-error contract: the path list points at the offending node.
    path = list(exc_info.value.absolute_path)
    assert path[:2] == ["color", "brand"], (
        f"schema error path must point at color.brand where the bad key lives; got: {path}"
    )


def test_button_fixture_validates_component_schema(
    component_schema: dict,
) -> None:
    """The hand-translated Button fixture validates against component.schema.json.

    This locks the component-schema shape against the DSL emit contract:
    once the W2 codegen pipeline lands, its JSON output must match this
    fixture's shape (or the schema tightens first, then the fixture).
    """
    fixture = _load_json(BUTTON_FIXTURE_PATH)
    try:
        jsonschema.validate(instance=fixture, schema=component_schema)
    except jsonschema.ValidationError as exc:  # pragma: no cover - on failure only
        pytest.fail(
            "button.catalog.json does not validate against component.schema.json: "
            f"{exc.message}\npath: {list(exc.absolute_path)}"
        )
