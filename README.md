# notebook-agent

Generate and execute Jupyter notebooks from natural-language task descriptions using Claude.

## Features

- Describe your analysis in plain English — Claude generates a complete, runnable notebook.
- Supports CSV data files: the agent inspects column names and dtypes before writing code.
- Executes notebooks via `nbconvert` and saves the output.
- Clean CLI with rich terminal output.
- Extensible `NotebookBuilder` for programmatic notebook construction.

## Installation

```bash
pip install notebook-agent
```

Or from source:

```bash
git clone https://github.com/example/notebook-agent
cd notebook-agent
pip install -e .
```

## Quick start

Set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Generate a notebook

```bash
notebook-agent create "analyse sales.csv and show monthly revenue trends" \
    --data sales.csv \
    --output revenue_analysis.ipynb
```

### Generate and immediately execute

```bash
notebook-agent create "plot the distribution of all numeric columns" \
    --data data.csv \
    --output exploration.ipynb \
    --execute
```

### Execute an existing notebook

```bash
notebook-agent run --notebook exploration.ipynb
```

The executed notebook is saved to `exploration_executed.ipynb` by default.

## CLI reference

### `create`

```
Usage: notebook-agent create [OPTIONS] TASK

  Generate a Jupyter notebook for TASK.

Arguments:
  TASK  Natural-language description of the analysis.

Options:
  --data FILE     Optional CSV data file.
  --output FILE   Destination .ipynb path.  [default: analysis.ipynb]
  --model TEXT    Claude model to use.  [default: claude-sonnet-4-6]
  --execute       Execute the notebook after generating it.
  --help          Show this message and exit.
```

### `run`

```
Usage: notebook-agent run [OPTIONS]

  Execute an existing Jupyter notebook via nbconvert.

Options:
  --notebook FILE   Path to the .ipynb file.  [required]
  --output FILE     Destination for the executed notebook.
  --timeout SECS    Per-cell timeout.  [default: 300]
  --help            Show this message and exit.
```

## Python API

### `NotebookAgent`

```python
from notebook_agent import NotebookAgent

agent = NotebookAgent()  # uses ANTHROPIC_API_KEY from environment

# Generate a notebook
path = agent.create(
    "Analyse sales.csv and plot quarterly trends by region",
    data_file="sales.csv",
    output_path="quarterly.ipynb",
)
print(f"Notebook saved to: {path}")

# Execute it
executed = agent.run(path)
print(f"Executed notebook: {executed}")
```

### `NotebookBuilder`

Build notebooks programmatically without the agent:

```python
from notebook_agent import NotebookBuilder

builder = NotebookBuilder()
builder.add_markdown("# My Analysis")
builder.add_code("import pandas as pd\ndf = pd.read_csv('data.csv')\ndf.head()")
builder.add_markdown("## Summary statistics")
builder.add_code("df.describe()")

path = builder.save("my_analysis.ipynb")
print(f"Saved {builder.cell_count} cells to {path}")
```

## How it works

1. The `NotebookAgent` sends your task description to Claude (`claude-sonnet-4-6`) with a set of tools.
2. Claude may call `read_csv` to inspect your data file before writing any code.
3. Claude calls `write_notebook` with an ordered list of markdown and code cells.
4. The agent saves the notebook to disk using `NotebookBuilder`.
5. Optionally, `nbconvert` executes the notebook and saves a copy with all cell outputs.

## Requirements

- Python 3.10+
- An [Anthropic API key](https://console.anthropic.com)
- `anthropic`, `click`, `rich`, `pandas`, `nbformat`, `nbconvert`, `ipykernel`

## License

MIT
