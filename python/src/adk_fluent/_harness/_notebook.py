"""Notebook tools — .ipynb reading and editing.

Claude Code can edit Jupyter notebooks. This module provides sandboxed
tool closures for reading, editing, and listing notebook cells::

    nb_tools = H.notebook()  # [read_notebook, edit_notebook_cell]

    agent = Agent("data-scientist").tools(H.workspace("/project") + nb_tools)

The tools parse ``.ipynb`` JSON directly — no Jupyter dependency needed.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from adk_fluent._harness._sandbox import SandboxPolicy

__all__ = ["make_read_notebook", "make_edit_notebook_cell", "notebook_tools"]


def _load_notebook(path: str) -> dict:
    """Load and parse a .ipynb file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_notebook(path: str, nb: dict) -> None:
    """Save a notebook dict to a .ipynb file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)
        f.write("\n")


def _format_cell(index: int, cell: dict) -> str:
    """Format a single cell for display."""
    cell_type = cell.get("cell_type", "unknown")
    source = "".join(cell.get("source", []))
    header = f"[Cell {index}] ({cell_type})"

    parts = [header, source]

    # Include outputs for code cells
    outputs = cell.get("outputs", [])
    if outputs:
        output_texts = []
        for out in outputs:
            if "text" in out:
                output_texts.append("".join(out["text"]))
            elif "data" in out:
                data = out["data"]
                if "text/plain" in data:
                    output_texts.append("".join(data["text/plain"]))
                elif "image/png" in data:
                    output_texts.append("[image/png output]")
        if output_texts:
            parts.append("--- Output ---")
            parts.extend(output_texts)

    return "\n".join(parts)


def make_read_notebook(sandbox: SandboxPolicy) -> Callable:
    """Create a sandboxed notebook reading tool.

    Args:
        sandbox: Sandbox policy for path validation.
    """

    def read_notebook(path: str, cell_index: int | None = None) -> str:
        """Read a Jupyter notebook (.ipynb) and display its cells.

        Shows cell type, source code, and outputs. Use ``cell_index``
        to read a specific cell, or omit to read all cells.

        Args:
            path: Path to the .ipynb file.
            cell_index: Optional specific cell index to read (0-based).
        """
        resolved = sandbox.resolve_path(path)
        if not sandbox.validate_path(resolved, write=False):
            return f"Error: path '{path}' is outside the allowed workspace."

        if not resolved.endswith(".ipynb"):
            return f"Error: '{path}' is not a .ipynb file."

        try:
            nb = _load_notebook(resolved)
        except FileNotFoundError:
            return f"Error: file not found: {path}"
        except json.JSONDecodeError:
            return f"Error: '{path}' is not valid JSON (corrupt notebook)."
        except Exception as e:
            return f"Error reading notebook: {e}"

        cells = nb.get("cells", [])
        if not cells:
            return f"Notebook '{path}' has no cells."

        if cell_index is not None:
            if cell_index < 0 or cell_index >= len(cells):
                return f"Error: cell index {cell_index} out of range (0-{len(cells) - 1})."
            return _format_cell(cell_index, cells[cell_index])

        parts = [f"Notebook: {path} ({len(cells)} cells)\n"]
        for i, cell in enumerate(cells):
            parts.append(_format_cell(i, cell))
            parts.append("")  # blank line between cells
        return "\n".join(parts)

    return read_notebook


def make_edit_notebook_cell(sandbox: SandboxPolicy) -> Callable:
    """Create a sandboxed notebook cell editing tool.

    Args:
        sandbox: Sandbox policy for path validation.
    """

    def edit_notebook_cell(path: str, cell_index: int, new_source: str) -> str:
        """Replace the source content of a specific notebook cell.

        Args:
            path: Path to the .ipynb file.
            cell_index: Cell index to edit (0-based).
            new_source: New source content for the cell.
        """
        resolved = sandbox.resolve_path(path)
        if not sandbox.validate_path(resolved, write=True):
            return f"Error: path '{path}' is outside the allowed workspace."

        if not resolved.endswith(".ipynb"):
            return f"Error: '{path}' is not a .ipynb file."

        try:
            nb = _load_notebook(resolved)
        except FileNotFoundError:
            return f"Error: file not found: {path}"
        except Exception as e:
            return f"Error reading notebook: {e}"

        cells = nb.get("cells", [])
        if cell_index < 0 or cell_index >= len(cells):
            return f"Error: cell index {cell_index} out of range (0-{len(cells) - 1})."

        # Replace source — notebook stores source as list of lines
        if not new_source.endswith("\n"):
            new_source += "\n"
        cells[cell_index]["source"] = new_source.splitlines(keepends=True)
        # Clear outputs for code cells (stale after edit)
        if cells[cell_index].get("cell_type") == "code":
            cells[cell_index]["outputs"] = []
            cells[cell_index]["execution_count"] = None

        try:
            _save_notebook(resolved, nb)
            return f"Successfully edited cell {cell_index} in {path}"
        except Exception as e:
            return f"Error writing notebook: {e}"

    return edit_notebook_cell


def notebook_tools(sandbox: SandboxPolicy) -> list[Callable]:
    """Create the notebook tool set.

    Args:
        sandbox: Sandbox policy.

    Returns:
        List of [read_notebook, edit_notebook_cell] tools.
    """
    return [
        make_read_notebook(sandbox),
        make_edit_notebook_cell(sandbox),
    ]
