"""Command-line interface for notebook-agent.

Usage examples
--------------
# Generate a notebook from a task description:
  notebook-agent create "analyse sales.csv and plot monthly trends" \
      --data sales.csv --output analysis.ipynb

# Execute an existing notebook:
  notebook-agent run --notebook analysis.ipynb
"""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax

console = Console()


@click.group()
@click.version_option(package_name="notebook-agent")
def cli() -> None:
    """notebook-agent - generate and execute Jupyter notebooks with Claude."""


@cli.command("create")
@click.argument("task")
@click.option(
    "--data",
    "data_file",
    default=None,
    metavar="FILE",
    help="Optional CSV data file to include in the analysis.",
)
@click.option(
    "--output",
    "output_path",
    default="analysis.ipynb",
    show_default=True,
    metavar="FILE",
    help="Destination path for the generated notebook.",
)
@click.option(
    "--model",
    default="claude-sonnet-4-6",
    show_default=True,
    help="Claude model to use.",
)
@click.option(
    "--execute",
    "run_after",
    is_flag=True,
    default=False,
    help="Execute the notebook after generating it.",
)
def create_cmd(
    task: str,
    data_file: str | None,
    output_path: str,
    model: str,
    run_after: bool,
) -> None:
    """Generate a Jupyter notebook for TASK.

    TASK is a natural-language description of the analysis you want, e.g.:

    \b
        "analyse sales.csv and show trends by quarter"
    """
    from notebook_agent.agent import NotebookAgent  # noqa: PLC0415

    if data_file and not Path(data_file).exists():
        console.print(f"[red]Error:[/red] data file not found: {data_file}")
        sys.exit(1)

    console.print(
        Panel(
            f"[bold]Task:[/bold] {task}"
            + (f"\n[bold]Data:[/bold]  {data_file}" if data_file else ""),
            title="[cyan]notebook-agent[/cyan]",
            expand=False,
        )
    )

    agent = NotebookAgent(model=model)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    ) as progress:
        progress.add_task("Generating notebook with Claude...", total=None)
        try:
            notebook_path = agent.create(
                task,
                data_file=data_file,
                output_path=output_path,
            )
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]Generation failed:[/red] {exc}")
            sys.exit(1)

    console.print(f"[green]Notebook written to:[/green] {notebook_path}")

    if run_after:
        _execute_notebook(agent, notebook_path)


@cli.command("run")
@click.option(
    "--notebook",
    "notebook_path",
    required=True,
    metavar="FILE",
    help="Path to the .ipynb notebook to execute.",
)
@click.option(
    "--output",
    "output_path",
    default=None,
    metavar="FILE",
    help="Destination for the executed notebook (default: <name>_executed.ipynb).",
)
@click.option(
    "--timeout",
    default=300,
    show_default=True,
    metavar="SECONDS",
    help="Per-cell execution timeout.",
)
def run_cmd(
    notebook_path: str,
    output_path: str | None,
    timeout: int,
) -> None:
    """Execute an existing Jupyter notebook via nbconvert."""
    from notebook_agent.agent import NotebookAgent  # noqa: PLC0415

    if not Path(notebook_path).exists():
        console.print(f"[red]Error:[/red] notebook not found: {notebook_path}")
        sys.exit(1)

    agent = NotebookAgent()
    _execute_notebook(agent, notebook_path, output_path=output_path, timeout=timeout)


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _execute_notebook(
    agent: "NotebookAgent",
    notebook_path: str,
    *,
    output_path: str | None = None,
    timeout: int = 300,
) -> None:
    from notebook_agent.agent import NotebookAgent  # noqa: PLC0415, F401

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    ) as progress:
        progress.add_task("Executing notebook...", total=None)
        try:
            executed_path = agent.run(
                notebook_path,
                output_path=output_path,
                timeout=timeout,
            )
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]Execution failed:[/red] {exc}")
            sys.exit(1)

    console.print(f"[green]Executed notebook saved to:[/green] {executed_path}")
    console.print(
        Syntax(
            f"jupyter notebook {executed_path}",
            "bash",
            theme="monokai",
            line_numbers=False,
        )
    )


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
