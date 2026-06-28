"""
The LangGraph workflow lives in nodes.py alongside the node implementations.
This module re-exports build_graph so runner.py and api/main.py can import
from either location without caring which file owns the graph definition.
"""
from src.nodes import build_graph  # noqa: F401
