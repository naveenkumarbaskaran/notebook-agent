"""notebook-agent: Generate and execute Jupyter notebooks from task descriptions."""

from notebook_agent.agent import NotebookAgent
from notebook_agent.builder import NotebookBuilder

__all__ = ["NotebookAgent", "NotebookBuilder"]
__version__ = "0.1.0"
