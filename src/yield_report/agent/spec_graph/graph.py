"""Graph assembly for the LangGraph Spec sub-agent."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from yield_report.agent.spec_graph.edges import SpecGraphEdges
from yield_report.agent.spec_graph.nodes import SpecGraphNodes
from yield_report.agent.spec_graph.state import SpecAgentState, SpecGraphDeps


def build_spec_graph(
    deps: SpecGraphDeps,
    *,
    nodes: SpecGraphNodes | None = None,
    edges: SpecGraphEdges | None = None,
) -> StateGraph:
    """Build the uncompiled LangGraph StateGraph for Spec construction."""

    node_handlers = nodes or SpecGraphNodes(deps)
    edge_handlers = edges or SpecGraphEdges(deps)

    graph = StateGraph(SpecAgentState)
    graph.add_node("load_context", node_handlers.load_context)
    graph.add_node("generate_draft", node_handlers.generate_draft)
    graph.add_node("parse_validate", node_handlers.parse_validate)
    graph.add_node("repair", node_handlers.repair)
    graph.add_node("finalize", node_handlers.finalize)
    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "generate_draft")
    graph.add_edge("generate_draft", "parse_validate")
    graph.add_conditional_edges(
        "parse_validate",
        edge_handlers.next_after_validation,
        {"repair": "repair", "finalize": "finalize"},
    )
    graph.add_edge("repair", "parse_validate")
    graph.add_edge("finalize", END)
    return graph


def compile_spec_graph(
    deps: SpecGraphDeps,
    *,
    nodes: SpecGraphNodes | None = None,
    edges: SpecGraphEdges | None = None,
    checkpointer: Any | None = None,
) -> Any:
    """Compile the Spec construction graph with optional persistence."""

    graph = build_spec_graph(deps, nodes=nodes, edges=edges)
    if checkpointer is None:
        return graph.compile()
    return graph.compile(checkpointer=checkpointer)
