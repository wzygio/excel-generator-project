"""Checkpointer helpers for LangGraph Spec construction."""

from __future__ import annotations

from typing import Any


def build_memory_checkpointer() -> Any:
    """Return an in-memory checkpointer for graph tests and local experiments."""

    try:
        from langgraph.checkpoint.memory import InMemorySaver as MemoryCheckpointer
    except ImportError:
        from langgraph.checkpoint.memory import MemorySaver as MemoryCheckpointer

    return MemoryCheckpointer()
