"""Facade for the LangGraph-backed Spec construction sub-agent."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from yield_report.agent.run_id import RunIdFactory
from yield_report.agent.spec_graph.graph import compile_spec_graph
from yield_report.agent.spec_graph.nodes import SpecGraphNodes
from yield_report.agent.spec_graph.state import DraftGenerator, SpecAgentResult, SpecGraphDeps
from yield_report.agent.spec_model import TaskSpec

if TYPE_CHECKING:
    from yield_report.agent.spec_builder import SpecBuildRequest


class LangGraphSpecAgent:
    """Generate, validate, and repair TaskSpecs through a LangGraph state machine."""

    def __init__(
        self,
        *,
        workspace: Path,
        draft_generator: DraftGenerator,
        registered_skills: set[str],
        today_clock: Callable[[], Any],
        max_repair_attempts: int = 2,
    ) -> None:
        deps = SpecGraphDeps(
            workspace=workspace,
            draft_generator=draft_generator,
            registered_skills=registered_skills,
            run_id_factory=RunIdFactory(clock=today_clock),
            max_repair_attempts=max_repair_attempts,
        )
        self._nodes = SpecGraphNodes(deps)
        self._graph = compile_spec_graph(deps, nodes=self._nodes)

    def build(self, request: SpecBuildRequest) -> SpecAgentResult:
        state = self._graph.invoke(
            {
                "request": request,
                "warnings": [],
                "validation_issues": [],
                "repair_attempts": 0,
            }
        )
        spec = state.get("spec")
        validation_issues = state.get("validation_issues", [])
        if not isinstance(spec, TaskSpec):
            spec = self._nodes.fallback_spec(request, validation_issues)
        return {
            "spec": spec,
            "warnings": state.get("warnings", []),
            "validation_issues": validation_issues,
        }
