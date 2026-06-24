"""Routing functions for the LangGraph Spec sub-agent."""

from __future__ import annotations

from yield_report.agent.spec_graph.state import SpecAgentState, SpecGraphDeps


class SpecGraphEdges:
    """Conditional edge handlers for TaskSpec construction."""

    def __init__(self, deps: SpecGraphDeps) -> None:
        self.deps = deps

    def next_after_validation(self, state: SpecAgentState) -> str:
        errors = [issue for issue in state.get("validation_issues", []) if issue.severity == "error"]
        if errors and state.get("repair_attempts", 0) < self.deps.max_repair_attempts:
            return "repair"
        return "finalize"
