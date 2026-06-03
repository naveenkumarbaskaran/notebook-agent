"""NotebookBuilder: construct valid .ipynb JSON structures programmatically."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class NotebookBuilder:
    """Build a valid Jupyter notebook (.ipynb) programmatically.

    Example
    -------
    >>> builder = NotebookBuilder()
    >>> builder.add_markdown("# Hello")
    >>> builder.add_code("print('hello world')")
    >>> path = builder.save("hello.ipynb")
    """

    # nbformat version used for all notebooks produced by this builder.
    NBFORMAT = 4
    NBFORMAT_MINOR = 5

    def __init__(self) -> None:
        self._cells: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Cell helpers
    # ------------------------------------------------------------------

    def add_markdown(self, source: str) -> "NotebookBuilder":
        """Append a markdown cell."""
        self._cells.append(self._markdown_cell(source))
        return self

    def add_code(self, source: str) -> "NotebookBuilder":
        """Append a code cell."""
        self._cells.append(self._code_cell(source))
        return self

    def clear(self) -> "NotebookBuilder":
        """Remove all cells."""
        self._cells.clear()
        return self

    @property
    def cell_count(self) -> int:
        """Number of cells currently in the builder."""
        return len(self._cells)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Return the notebook as a plain Python dictionary."""
        return {
            "nbformat": self.NBFORMAT,
            "nbformat_minor": self.NBFORMAT_MINOR,
            "metadata": self._default_metadata(),
            "cells": list(self._cells),  # shallow copy
        }

    def to_json(self, *, indent: int = 1) -> str:
        """Serialise the notebook to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def save(self, path: str | Path) -> str:
        """Write the notebook JSON to *path* and return the resolved path string."""
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(self.to_json(), encoding="utf-8")
        return str(dest)

    # ------------------------------------------------------------------
    # Class-level cell factories
    # ------------------------------------------------------------------

    @classmethod
    def _markdown_cell(cls, source: str) -> dict[str, Any]:
        return {
            "cell_type": "markdown",
            "metadata": {},
            "source": cls._to_source_list(source),
        }

    @classmethod
    def _code_cell(cls, source: str) -> dict[str, Any]:
        return {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": cls._to_source_list(source),
        }

    @staticmethod
    def _to_source_list(source: str) -> list[str]:
        """Split *source* into a list of lines, each ending with ``\\n``
        except the last line — exactly the format nbformat uses."""
        if not source:
            return []
        lines = source.splitlines(keepends=False)
        result: list[str] = []
        for i, line in enumerate(lines):
            if i < len(lines) - 1:
                result.append(line + "\n")
            else:
                result.append(line)
        return result

    @staticmethod
    def _default_metadata() -> dict[str, Any]:
        return {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3.11.0",
            },
        }
