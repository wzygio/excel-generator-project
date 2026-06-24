from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from yield_report.agent.run_id import RunIdFactory
from yield_report.agent.spec_builder import SpecBuildRequest
from yield_report.agent.spec_graph import LangGraphSpecAgent
from yield_report.agent.spec_graph.checkpointer import build_memory_checkpointer
from yield_report.agent.spec_graph.graph import compile_spec_graph
from yield_report.agent.spec_graph.nodes import SpecGraphNodes
from yield_report.agent.spec_graph.state import SpecGraphDeps
from yield_report.agent.spec_validation import SpecValidationIssue

REGISTERED_SKILLS = {"report_download", "data_analysis", "daily_report", "anomaly_monitor"}


def test_spec_graph_node_parse_validate_enriches_runtime_fields(tmp_path: Path) -> None:
    request = SpecBuildRequest(user_goal="请分析C522近一周的良率变化趋势")
    nodes = SpecGraphNodes(_deps(tmp_path, _analysis_payload))

    update = nodes.parse_validate(
        {
            "request": request,
            "raw_spec": _analysis_payload(request, [], ""),
        }
    )

    spec = update["spec"]
    assert spec.status == "ready"
    assert spec.run_id == "agent-data-analysis-20260608-000000"
    assert spec.constraints["spec_source"] == "agent"
    assert spec.constraints["spec_builder"] == "langgraph"
    assert spec.constraints["builder_mode"] == "langgraph"
    assert spec.constraints["capability"] == "data-analysis"
    assert update["validation_issues"] == []


def test_compile_spec_graph_exposes_expected_nodes(tmp_path: Path) -> None:
    graph = compile_spec_graph(
        _deps(tmp_path, _analysis_payload),
        checkpointer=build_memory_checkpointer(),
    )

    assert {
        "load_context",
        "generate_draft",
        "parse_validate",
        "repair",
        "finalize",
    }.issubset(set(graph.nodes))


def test_langgraph_spec_agent_repairs_invalid_draft(tmp_path: Path) -> None:
    calls = 0

    def draft_generator(
        request: SpecBuildRequest,
        issues: list[SpecValidationIssue],
        context: str,
    ) -> dict[str, Any] | str:
        nonlocal calls
        calls += 1
        if calls == 1:
            return "not-json"
        assert issues
        return _analysis_payload(request, issues, context)

    agent = LangGraphSpecAgent(
        workspace=tmp_path,
        draft_generator=draft_generator,
        registered_skills=REGISTERED_SKILLS,
        today_clock=_clock,
    )

    result = agent.build(SpecBuildRequest(user_goal="请分析C522近一周的良率变化趋势"))

    assert calls == 2
    assert result["spec"].status == "ready"
    assert result["spec"].workflow[0].skill == "data_analysis"
    assert result["warnings"]


def _deps(tmp_path: Path, draft_generator: Any) -> SpecGraphDeps:
    return SpecGraphDeps(
        workspace=tmp_path,
        draft_generator=draft_generator,
        registered_skills=REGISTERED_SKILLS,
        run_id_factory=RunIdFactory(clock=_clock),
    )


def _clock() -> datetime:
    return datetime(2026, 6, 8)


def _analysis_payload(
    request: SpecBuildRequest,
    issues: list[SpecValidationIssue],
    context: str,
) -> dict[str, Any]:
    del issues, context
    return {
        "schema_version": 1,
        "status": "draft",
        "user_goal": request.user_goal,
        "workflow": [
            {
                "id": "analyze",
                "skill": "data_analysis",
                "input": {"question": request.user_goal},
            }
        ],
        "outputs": {"analysis_summary": {"required": True, "format": "markdown"}},
        "memory": {"reuse_policy": "confirmed_only"},
    }
