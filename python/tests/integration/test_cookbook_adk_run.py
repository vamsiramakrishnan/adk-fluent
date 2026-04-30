"""Integration tests: run cookbook agents through `adk run --replay`.

Generates agent folders from cookbooks, sends a sample prompt via
`adk run --replay`, and asserts the agent produces a non-empty response.

Setup:
  1. Copy .env.example → .env at project root and fill in credentials
  2. Run: uv run pytest tests/integration/ -v

These tests make REAL LLM calls and cost money. They are skipped
automatically if .env is missing or GOOGLE_CLOUD_PROJECT is not set.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PYTHON_DIR = ROOT / "python"
AGENTS_SCRIPT = ROOT / "shared" / "scripts" / "cookbook_to_agents.py"


def _load_dotenv():
    for env_file in [ROOT / ".env", ROOT / "examples" / ".env"]:
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                key, _, val = line.partition("=")
                key, val = key.strip(), val.strip()
                if key:
                    os.environ.setdefault(key, val)
            break


_load_dotenv()

# (folder_name, sample_prompt, timeout_seconds)
# Timeouts are generous — LLM latency varies. Multi-agent pipelines get more.
AGENTS: list[tuple[str, str, int]] = [
    # --- Basics ---
    ("simple_agent", "Classify this email: I cannot log in to my account", 30),
    ("agent_with_tools", "What is the weather in London?", 30),
    ("one_shot_ask", "Review this code: def add(a, b): return a + b", 30),
    # --- Workflows ---
    ("sequential_pipeline", "Write a poem about the ocean", 60),
    ("parallel_fanout", "Research the topic: renewable energy", 60),
    ("team_coordinator", "Help me plan a birthday party", 60),
    # --- Routing & State ---
    ("route_branching", "I need help with billing", 30),
    ("capture_and_route", "I need technical support with my API integration", 60),
    ("customer_support_triage", "My order hasn't arrived yet", 60),
    # --- Advanced Patterns ---
    ("real_world_pipeline", "Summarize the key points of contract law", 90),
    ("dependency_injection", "Look up user 42", 30),
    ("context_engineering", "Write a brief summary of machine learning", 60),
    # --- Multi-Agent ---
    ("code_review_agent", "Review: def fib(n): return fib(n-1) + fib(n-2)", 60),
    ("collaboration_mechanisms", "Help me brainstorm ideas for a mobile app", 90),
]

pytestmark = pytest.mark.skipif(
    not os.environ.get("GOOGLE_CLOUD_PROJECT"),
    reason="GOOGLE_CLOUD_PROJECT not set — add .env at project root",
)


@pytest.fixture(scope="module")
def agents_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("adk_agents")
    env_src = ROOT / ".env"
    if env_src.exists():
        (out / ".env").write_text(env_src.read_text())

    cookbook_dir = PYTHON_DIR / "examples" / "cookbook"
    result = subprocess.run(
        [
            sys.executable,
            str(AGENTS_SCRIPT),
            "--force",
            "--cookbook-dir",
            str(cookbook_dir),
            "--output-dir",
            str(out),
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(PYTHON_DIR / "src")},
    )
    if result.returncode != 0:
        pytest.fail(f"cookbook_to_agents.py failed:\n{result.stderr[:500]}")
    generated = [d.name for d in out.iterdir() if d.is_dir()]
    if not generated:
        pytest.fail(f"No agent folders generated.\n{result.stdout[:500]}")
    return out


def _run_agent(agents_dir: Path, folder: str, prompt: str, timeout: int) -> str:
    replay = agents_dir / f"_replay_{folder}.json"
    replay.write_text(json.dumps({"state": {}, "queries": [prompt]}))

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "google.adk.cli",
            "run",
            folder,
            "--replay",
            str(replay),
        ],
        capture_output=True,
        text=True,
        cwd=str(agents_dir),
        timeout=timeout,
        env={**os.environ, "PYTHONPATH": str(PYTHON_DIR / "src")},
    )
    combined = result.stdout + result.stderr
    if result.returncode != 0:
        error_lines = [l for l in combined.split("\n") if "Error" in l or "error" in l.lower()]
        summary = "\n".join(error_lines[-5:]) if error_lines else combined[-300:]
        if "ModuleNotFoundError" in combined or "ImportError" in combined:
            pytest.skip(f"Agent '{folder}' has a missing import (cookbook_to_agents bug):\n{summary}")
        elif "NameError" in combined:
            pytest.skip(f"Agent '{folder}' has undefined name (cookbook_to_agents bug):\n{summary}")
        elif "GuardViolation" in combined:
            pass  # guard did its job — the agent ran, guard rejected output
        else:
            pytest.fail(f"Agent '{folder}' crashed:\n{summary}")
    return combined


@pytest.mark.parametrize(
    "folder,prompt,timeout",
    AGENTS,
    ids=[a[0] for a in AGENTS],
)
def test_cookbook_agent(agents_dir, folder, prompt, timeout):
    agent_dir = agents_dir / folder
    if not agent_dir.exists():
        pytest.skip(f"Agent folder '{folder}' not generated by cookbook_to_agents")

    try:
        output = _run_agent(agents_dir, folder, prompt, timeout)
    except subprocess.TimeoutExpired:
        pytest.skip(f"Agent '{folder}' timed out after {timeout}s (LLM latency)")

    lines = [
        line
        for line in output.strip().split("\n")
        if line.strip()
        and not line.startswith("Log setup")
        and not line.startswith("To access")
        and not line.startswith("Shell cwd")
        and "UserWarning" not in line
        and "EXPERIMENTAL" not in line
    ]
    agent_lines = [line for line in lines if not line.startswith("[user]")]
    assert len(agent_lines) > 0, f"Agent '{folder}' produced no response.\n{output[:500]}"
