"""NotebookAgent: uses Claude to generate and execute Jupyter notebooks."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import anthropic

from notebook_agent.builder import NotebookBuilder

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """\
You are an expert data scientist and Python programmer.
Your job is to write Jupyter notebooks that analyse data and answer questions.

When given a task description you must:
1. Think about what analysis or work is needed.
2. Call `write_notebook` with a list of cells (markdown + code) that accomplish the task.
   - Start with a markdown title cell.
   - Use descriptive markdown cells to explain each analysis step.
   - Write clean, well-commented Python code cells.
   - Produce visualisations and summary statistics where relevant.
3. If data files are mentioned you may call `read_csv` first to inspect their shape/columns.
4. Call `read_file` if you need to inspect an existing file.

Always produce a complete, runnable notebook that will work end-to-end.
"""


TOOLS: list[dict[str, Any]] = [
    {
        "name": "read_file",
        "description": "Read the text contents of a file on disk.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative path to the file.",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_notebook",
        "description": (
            "Write a Jupyter notebook (.ipynb) to disk from a list of cells. "
            "Each cell has a 'type' ('markdown' or 'code') and 'source' (string)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Destination path for the .ipynb file.",
                },
                "cells": {
                    "type": "array",
                    "description": "Ordered list of notebook cells.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["markdown", "code"],
                            },
                            "source": {
                                "type": "string",
                                "description": "Cell source text.",
                            },
                        },
                        "required": ["type", "source"],
                    },
                },
            },
            "required": ["path", "cells"],
        },
    },
    {
        "name": "read_csv",
        "description": (
            "Read a CSV file and return a JSON summary: columns, dtypes, shape, "
            "and the first five rows."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the CSV file.",
                }
            },
            "required": ["path"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _tool_read_file(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return f"ERROR: file not found: {path}"
    try:
        return p.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return f"ERROR reading file: {exc}"


def _tool_write_notebook(path: str, cells: list[dict[str, str]]) -> str:
    builder = NotebookBuilder()
    for cell in cells:
        cell_type = cell.get("type", "code")
        source = cell.get("source", "")
        if cell_type == "markdown":
            builder.add_markdown(source)
        else:
            builder.add_code(source)
    try:
        nb_path = builder.save(path)
        return f"Notebook written to {nb_path}"
    except Exception as exc:  # noqa: BLE001
        return f"ERROR writing notebook: {exc}"


def _tool_read_csv(path: str) -> str:
    try:
        import pandas as pd  # noqa: PLC0415
    except ImportError:
        return "ERROR: pandas is not installed"
    p = Path(path)
    if not p.exists():
        return f"ERROR: file not found: {path}"
    try:
        df = pd.read_csv(p)
        summary = {
            "shape": list(df.shape),
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "head": json.loads(df.head().to_json(orient="records")),
        }
        return json.dumps(summary, indent=2)
    except Exception as exc:  # noqa: BLE001
        return f"ERROR reading CSV: {exc}"


def _dispatch_tool(name: str, tool_input: dict[str, Any]) -> str:
    if name == "read_file":
        return _tool_read_file(tool_input["path"])
    if name == "write_notebook":
        return _tool_write_notebook(tool_input["path"], tool_input["cells"])
    if name == "read_csv":
        return _tool_read_csv(tool_input["path"])
    return f"ERROR: unknown tool '{name}'"


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class NotebookAgent:
    """Agent that generates Jupyter notebooks from natural-language task descriptions."""

    def __init__(
        self,
        *,
        model: str = MODEL,
        api_key: str | None = None,
        max_iterations: int = 10,
    ) -> None:
        self.model = model
        self.max_iterations = max_iterations
        self.client = anthropic.Anthropic(api_key=api_key)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def create(
        self,
        task: str,
        *,
        data_file: str | None = None,
        output_path: str = "analysis.ipynb",
    ) -> str:
        """Generate a notebook for *task*, optionally referencing *data_file*.

        Returns the path of the written notebook.
        """
        user_message = self._build_user_message(task, data_file=data_file, output_path=output_path)
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]

        for _ in range(self.max_iterations):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8096,
                system=SYSTEM_PROMPT,
                tools=TOOLS,  # type: ignore[arg-type]
                messages=messages,  # type: ignore[arg-type]
            )

            # Append assistant turn
            messages.append({"role": "assistant", "content": response.content})  # type: ignore[arg-type]

            if response.stop_reason == "end_turn":
                # Agent is done — return the output path
                return output_path

            if response.stop_reason != "tool_use":
                break

            # Execute all tool calls
            tool_results: list[dict[str, Any]] = []
            notebook_written: str | None = None

            for block in response.content:
                if block.type != "tool_use":
                    continue
                result_str = _dispatch_tool(block.name, block.input)  # type: ignore[arg-type]
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_str,
                })
                # Track notebook path
                if block.name == "write_notebook" and not result_str.startswith("ERROR"):
                    notebook_written = block.input.get("path", output_path)  # type: ignore[union-attr]

            messages.append({"role": "user", "content": tool_results})  # type: ignore[arg-type]

            if notebook_written:
                # Let the model finish its turn, but also record the written path
                output_path = notebook_written

        return output_path

    def run(
        self,
        notebook_path: str,
        *,
        output_path: str | None = None,
        timeout: int = 300,
    ) -> str:
        """Execute *notebook_path* via nbconvert and return the output path.

        Parameters
        ----------
        notebook_path:
            Path to the ``.ipynb`` file to execute.
        output_path:
            Destination for the executed notebook.  Defaults to
            ``<stem>_executed.ipynb`` next to the source.
        timeout:
            Per-cell execution timeout in seconds.

        Returns the path of the executed notebook.
        """
        src = Path(notebook_path)
        if not src.exists():
            raise FileNotFoundError(f"Notebook not found: {notebook_path}")

        if output_path is None:
            output_path = str(src.parent / f"{src.stem}_executed{src.suffix}")

        cmd = [
            sys.executable, "-m", "nbconvert",
            "--to", "notebook",
            "--execute",
            f"--ExecutePreprocessor.timeout={timeout}",
            "--output", output_path,
            str(src),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)  # noqa: S603
        if result.returncode != 0:
            raise RuntimeError(
                f"nbconvert failed (exit {result.returncode}):\n"
                f"{result.stderr or result.stdout}"
            )

        return output_path

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_user_message(
        task: str,
        *,
        data_file: str | None,
        output_path: str,
    ) -> str:
        parts = [f"Task: {task}"]
        if data_file:
            parts.append(f"Data file: {data_file}")
        parts.append(f"Save the notebook to: {output_path}")
        return "\n".join(parts)
