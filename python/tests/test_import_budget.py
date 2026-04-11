"""Import budget test — ensures `import adk_fluent` stays lightweight.

This test guards against regressions where heavy ADK dependencies get
pulled in at import time. The lazy loading architecture should keep
the module count well below the budget.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

# Budget: importing adk_fluent should load fewer than this many modules.
# Before lazy loading: ~1,468 modules (via BaseAgent chain).
# After lazy loading: ~60-80 modules (just stdlib + adk_fluent internals).
MODULE_BUDGET = 200


@pytest.mark.slow
def test_import_module_count():
    """Importing adk_fluent must not exceed the module budget."""
    code = (
        "import sys; "
        "before = set(sys.modules); "
        "import adk_fluent; "
        "after = set(sys.modules); "
        "new = after - before; "
        "print(len(new))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Import failed: {result.stderr}"
    count = int(result.stdout.strip())
    assert count < MODULE_BUDGET, (
        f"import adk_fluent loaded {count} new modules, "
        f"exceeding budget of {MODULE_BUDGET}. "
        f"Check for eager imports of ADK classes at module level."
    )


@pytest.mark.slow
def test_no_adk_agents_on_import():
    """Importing adk_fluent must not load google.adk.agents."""
    code = (
        "import sys; "
        "import adk_fluent; "
        "adk_mods = [m for m in sys.modules if m.startswith('google.adk.agents')]; "
        "print(','.join(adk_mods) if adk_mods else 'CLEAN')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Import failed: {result.stderr}"
    output = result.stdout.strip()
    assert output == "CLEAN", (
        f"import adk_fluent eagerly loaded ADK agent modules: {output}. These should be deferred to build() time."
    )
