#!/usr/bin/env python3
"""
adk-fluent Visual Cookbook Runner — FastAPI dev server.

Auto-discovers cookbook agents, serves the UI, runs agents against real LLMs,
and streams A2UI surfaces to the browser.

Usage:
    uvicorn visual.server:app --reload --port 8099
    # or via justfile:
    just visual
"""

from __future__ import annotations

import importlib.util
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# ── Path setup ─────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
COOKBOOK_DIR = ROOT / "examples" / "cookbook"
EXAMPLES_DIR = ROOT / "examples"
VISUAL_DIR = Path(__file__).parent
SHARED_VISUAL = ROOT.parent / "shared" / "visual"

# Ensure project root is on path
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

logger = logging.getLogger("visual.server")

# ── App setup ──────────────────────────────────────────────────
app = FastAPI(title="adk-fluent Visual Runner", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Serve static surfaces
surfaces_dir = VISUAL_DIR / "surfaces"
if surfaces_dir.exists():
    app.mount("/surfaces", StaticFiles(directory=str(surfaces_dir)), name="surfaces")

# ── Cookbook discovery ──────────────────────────────────────────

# Crawl/Walk/Run grouping from INDEX.md
CRAWL = {1, 2, 3, 8, 10, 11, 21, 22, 23, 24, 26}
WALK = {4, 5, 6, 7, 12, 13, 14, 16, 17, 18, 19, 20, 27, 29, 30, 31, 32, 33, 35, 36, 37, 38, 39, 40, 41, 42, 56}
A2UI = {70, 71, 72, 73, 74}


def _get_group(num: int) -> str:
    if num in CRAWL:
        return "crawl"
    if num in WALK:
        return "walk"
    if num in A2UI:
        return "a2ui"
    return "run"


def _parse_title(filepath: Path) -> str:
    """Extract title from cookbook docstring."""
    try:
        text = filepath.read_text()
        m = re.match(r'"""(.+?)(?:\n|""")', text, re.DOTALL)
        if m:
            return m.group(1).strip().split("\n")[0]
    except Exception:
        pass
    return filepath.stem.replace("_", " ").title()


def discover_cookbooks() -> list[dict]:
    """Discover all cookbook examples and classify them."""
    results = []
    for f in sorted(COOKBOOK_DIR.glob("[0-9][0-9]_*.py")):
        if f.name == "conftest.py":
            continue
        num_match = re.match(r"(\d+)", f.stem)
        num = int(num_match.group(1)) if num_match else 0
        group = _get_group(num)

        # Check if there's a corresponding example folder
        folder_name = re.sub(r"^\d+_", "", f.stem)
        example_folder = EXAMPLES_DIR / folder_name
        has_agent = (example_folder / "agent.py").exists()

        results.append(
            {
                "id": f.stem,
                "name": _parse_title(f),
                "group": group,
                "badge": group,
                "description": f"Cookbook {num:02d} — {folder_name.replace('_', ' ')}",
                "has_agent": has_agent,
                "folder": folder_name if has_agent else None,
                "has_surface": group == "a2ui",
            }
        )
    return results


# Cache discovery
_cookbooks_cache: list[dict] | None = None


def get_cookbooks() -> list[dict]:
    global _cookbooks_cache
    if _cookbooks_cache is None:
        _cookbooks_cache = discover_cookbooks()
    return _cookbooks_cache


# ── Agent loading ──────────────────────────────────────────────

_agent_cache: dict[str, Any] = {}


def _load_agent(cookbook_id: str) -> Any:
    """Load and build an agent from a cookbook's example folder."""
    cb = _validate_cookbook_id(cookbook_id)
    if not cb:
        raise ValueError(f"Cookbook '{cookbook_id}' not found")

    if cookbook_id in _agent_cache:
        return _agent_cache[cookbook_id]

    # Try loading from example folder first (has root_agent)
    if cb.get("folder"):
        agent_file = EXAMPLES_DIR / cb["folder"] / "agent.py"
        if agent_file.exists():
            spec = importlib.util.spec_from_file_location(f"example_{cb['folder']}", agent_file)
            if spec is None or spec.loader is None:
                raise RuntimeError(f"Cannot load module spec for {agent_file}")
            mod = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(mod)
                agent = getattr(mod, "root_agent", None)
                if agent is not None:
                    _agent_cache[cookbook_id] = agent
                    return agent
            except Exception as e:
                raise RuntimeError(f"Failed to load {agent_file}: {e}") from e

    raise ValueError(f"No runnable agent found for '{cookbook_id}'. Run 'just agents' first.")


def _validate_cookbook_id(cookbook_id: str) -> dict | None:
    """Validate cookbook_id against the discovered allowlist. Returns the cookbook entry or None."""
    return next((c for c in get_cookbooks() if c["id"] == cookbook_id), None)


def _get_builder(cookbook_id: str):
    """Load the builder (pre-build) from the cookbook script for introspection."""
    cb = _validate_cookbook_id(cookbook_id)
    if not cb:
        return None

    # Use the validated ID from the allowlist, never raw user input in paths
    cookbook_file = COOKBOOK_DIR / f"{cb['id']}.py"
    if not cookbook_file.exists():
        return None

    try:
        spec = importlib.util.spec_from_file_location(f"cb_{cookbook_id}", cookbook_file)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)

        import contextlib
        import io

        with contextlib.redirect_stdout(io.StringIO()):
            spec.loader.exec_module(mod)

        # Find builder objects
        from adk_fluent._base import BuilderBase  # type: ignore[import-not-found]

        for name, obj in vars(mod).items():
            if isinstance(obj, BuilderBase) and not name.startswith("_"):
                return obj
    except Exception:
        pass
    return None


# ── Routes ─────────────────────────────────────────────────────


@app.get("/")
async def serve_ui():
    return FileResponse(SHARED_VISUAL / "index.html")


@app.get("/api/health")
async def health():
    return {"status": "ok", "language": "Python", "cookbooks": len(get_cookbooks())}


@app.get("/api/cookbooks")
async def list_cookbooks():
    return JSONResponse(get_cookbooks())


@app.get("/api/inspect/{cookbook_id}")
async def inspect_cookbook(cookbook_id: str):
    """Return introspection data for a cookbook agent."""
    builder = _get_builder(cookbook_id)
    result: dict[str, Any] = {"cookbook_id": cookbook_id}

    if builder:
        try:
            result["explain"] = builder._explain_json() if hasattr(builder, "_explain_json") else str(builder)
        except Exception:
            result["explain"] = "(introspection unavailable)"

        try:
            if hasattr(builder, "to_mermaid"):
                result["mermaid"] = builder.to_mermaid()
        except Exception:
            pass

    # Check for pre-compiled A2UI surface
    ui_spec = getattr(builder, "_config", {}).get("_ui_spec") if builder else None
    if ui_spec:
        try:
            from adk_fluent._ui import UISurface, compile_surface  # type: ignore[import-not-found]

            if isinstance(ui_spec, UISurface):
                result["surface_messages"] = compile_surface(ui_spec)
        except Exception:
            pass

    return JSONResponse(result)


@app.post("/api/run")
async def run_agent(body: dict):
    """Run a cookbook agent with a prompt."""
    cookbook_id = body.get("cookbook")
    prompt = body.get("prompt", "")

    if not cookbook_id or not prompt:
        return JSONResponse({"error": "Missing cookbook or prompt"}, status_code=400)

    try:
        agent = _load_agent(cookbook_id)
    except ValueError:
        return JSONResponse({"error": f"Cookbook '{cookbook_id}' not found"}, status_code=404)
    except RuntimeError:
        logger.exception("Failed to load agent for cookbook '%s'", cookbook_id)
        return JSONResponse({"error": "Failed to load agent"}, status_code=500)

    try:
        from google.adk.runners import InMemoryRunner
        from google.genai import types

        runner = InMemoryRunner(agent=agent, app_name="visual_runner")

        session = await runner.session_service.create_session(app_name="visual_runner", user_id="visual_user")

        content = types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
        response_text = ""
        surface_messages = []

        async for event in runner.run_async(user_id="visual_user", session_id=session.id, new_message=content):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        response_text += part.text

        # Extract A2UI surface messages from session state
        final_session = await runner.session_service.get_session(
            app_name="visual_runner", user_id="visual_user", session_id=session.id
        )
        if final_session and final_session.state:
            msgs = final_session.state.get("_a2ui_surface_messages")
            if msgs:
                surface_messages = msgs

        return JSONResponse(
            {
                "response": response_text,
                "surface_messages": surface_messages,
            }
        )

    except Exception as e:
        logger.exception("Agent execution failed for cookbook '%s'", cookbook_id)
        return JSONResponse(
            {"error": f"Agent execution failed: {type(e).__name__}"},
            status_code=500,
        )


@app.get("/api/surfaces")
async def list_surfaces():
    """List all exported A2UI surface files."""
    index_file = surfaces_dir / "_index.json"
    if index_file.exists():
        return JSONResponse(json.loads(index_file.read_text()))
    return JSONResponse([])


# ── Main ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("visual.server:app", host="0.0.0.0", port=8099, reload=True)
