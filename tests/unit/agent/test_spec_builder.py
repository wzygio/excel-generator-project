from __future__ import annotations

from datetime import date
from pathlib import Path

from yield_report.agent.run_store import RunStore
from yield_report.agent.spec_builder import SpecBuilder, SpecBuildRequest


def _daily_report_spec_payload(request: SpecBuildRequest) -> dict:
    return {
        "schema_version": 1,
        "status": "draft",
        "user_goal": request.user_goal,
        "constraints": {"capability": "daily-report"},
        "inputs": {"report_date": "2026-06-08", "product_models": ["M678"]},
        "workflow": [
            {
                "id": "generate_daily_report",
                "skill": "daily_report",
                "input": {
                    "report_date": "2026-06-08",
                    "product_models": ["M678"],
                    "source_files": {"spotfire": "resources/project_files/spotfire.xlsx"},
                    "sections": ["gap", "trend"],
                    "analysis_results": [],
                    "download_sources": False,
                    "run_inspection": False,
                    "task0_timeout_seconds": 90,
                },
            }
        ],
        "outputs": {"daily_report": {"required": True, "format": "xlsx"}},
        "memory": {"reuse_policy": "confirmed_only"},
    }


def _analysis_spec_payload(request: SpecBuildRequest) -> dict:
    return {
        "schema_version": 1,
        "status": "draft",
        "user_goal": request.user_goal,
        "constraints": {"capability": "yield-trend", "pi_runtime_allowed": True},
        "inputs": {
            "report_date": "2026-06-08",
            "product_models": ["C522"],
            "date_range": {"start": "2026-06-02", "end": "2026-06-08"},
            "analysis": {
                "time_grain": "daily",
                "requested_periods": 7,
                "metrics": ["日度良率"],
                "analysis_intent": "trend",
            },
        },
        "workflow": [
            {
                "id": "analyze_yield_trend",
                "skill": "data_analysis",
                "input": {
                    "question": request.user_goal,
                    "product_models": ["C522"],
                    "time_range": {"start": "2026-06-02", "end": "2026-06-08"},
                    "metrics": ["日度良率"],
                    "time_grain": "daily",
                    "requested_periods": 7,
                    "analysis_intent": "trend",
                },
            }
        ],
        "outputs": {"analysis_summary": {"required": True, "format": "markdown"}},
        "memory": {"reuse_policy": "confirmed_only"},
    }


def test_spec_builder_extracts_product_and_today(tmp_path: Path) -> None:
    builder = SpecBuilder(
        store=RunStore(workspace=tmp_path),
        today=date(2026, 6, 8),
        llm_converter=_daily_report_spec_payload,
    )

    result = builder.build(SpecBuildRequest(user_goal="生成 M678 今天良率日报"))

    assert result.spec.status == "ready"
    assert result.spec.run_id == "agent-daily-report-20260608-000000"
    assert result.spec.constraints["spec_builder"] == "langgraph"
    assert result.spec.inputs["report_date"] == "2026-06-08"
    assert result.spec.inputs["product_models"] == ["M678"]
    assert len(result.spec.workflow) == 1
    assert result.spec.workflow[0].skill == "daily_report"
    assert result.spec.workflow[0].input["product_models"] == ["M678"]
    assert result.spec.workflow[0].input["source_files"]["spotfire"].endswith("spotfire.xlsx")
    assert result.spec.workflow[0].input["download_sources"] is False
    assert result.spec.workflow[0].input["run_inspection"] is False
    assert result.spec.workflow[0].input["task0_timeout_seconds"] == 90
    assert result.spec_path.exists()


def test_spec_builder_allows_missing_product_for_all_models(tmp_path: Path) -> None:
    builder = SpecBuilder(
        store=RunStore(workspace=tmp_path),
        today=date(2026, 6, 8),
        llm_converter=lambda request: {
            **_daily_report_spec_payload(request),
            "inputs": {"report_date": "2026-06-08", "product_models": []},
        },
    )

    result = builder.build(SpecBuildRequest(user_goal="生成今天良率日报"))

    assert result.spec.status == "ready"
    assert result.spec.inputs["product_models"] == []
    assert result.warnings == []


def test_spec_builder_requires_confirmation_when_all_products_disabled(tmp_path: Path) -> None:
    builder = SpecBuilder(store=RunStore(workspace=tmp_path), today=date(2026, 6, 8))

    result = builder.build(
        SpecBuildRequest(
            user_goal="生成今天良率日报",
            allow_all_products=False,
            capability="daily_report",
            fixed_flow=True,
        )
    )

    assert result.spec.status == "needs_confirmation"
    assert result.warnings == ["缺少产品型号，需要用户确认。"]


def test_spec_builder_uses_minimal_daily_report_wrapper_input(tmp_path: Path) -> None:
    builder = SpecBuilder(store=RunStore(workspace=tmp_path), today=date(2026, 6, 8))

    result = builder.build(
        SpecBuildRequest(
            user_goal="生成 M678 2026年6月1日良率日报",
            sections=["gap", "trend", "gap"],
            capability="daily_report",
            fixed_flow=True,
        )
    )

    assert result.spec.inputs["report_date"] == "2026-06-01"
    assert result.spec.inputs["date_range"] == {"start": "2026-05-26", "end": "2026-06-01"}
    assert result.spec.workflow[0].input == {"report_date": "2026-06-01"}


def test_spec_builder_builds_data_analysis_spec_for_trend_goal(tmp_path: Path) -> None:
    builder = SpecBuilder(
        store=RunStore(workspace=tmp_path),
        today=date(2026, 6, 8),
        llm_converter=_analysis_spec_payload,
    )

    result = builder.build(
        SpecBuildRequest(user_goal="请分析C522近一周的良率变化趋势；如果有恶化，请给出恶化原因")
    )

    assert result.spec.status == "ready"
    assert result.spec.constraints.get("runtime") != "omp"
    assert result.spec.constraints["pi_runtime_allowed"] is True
    assert result.spec.inputs["product_models"] == ["C522"]
    assert result.spec.workflow == [
        result.spec.workflow[0],
    ]
    assert result.spec.workflow[0].skill == "data_analysis"
    assert result.spec.workflow[0].input["product_models"] == ["C522"]
    assert result.spec.workflow[0].input["analysis_intent"] == "trend"
    assert "日度良率" in result.spec.workflow[0].input["metrics"]
    assert result.spec.outputs["analysis_summary"]["format"] == "markdown"


def test_spec_builder_builds_batch_report_download_spec_for_query_goal(
    tmp_path: Path,
) -> None:
    def download_payload(request: SpecBuildRequest) -> dict:
        return {
            "schema_version": 1,
            "status": "draft",
            "user_goal": request.user_goal,
            "constraints": {"capability": "report-download"},
            "inputs": {
                "report_date": "2026-06-08",
                "product_models": ["M626"],
                "date_range": {"start": "2026-03-10", "end": "2026-06-08"},
                "reports": [{"alias": "source_batch_yield", "report_type": "batch_yield"}],
            },
            "workflow": [
                {
                    "id": "download_batch_yield",
                    "skill": "report_download",
                    "input": {
                        "user_query": request.user_goal,
                        "report_type": "batch_yield",
                        "start_date": "2026-03-10",
                        "end_date": "2026-06-08",
                        "product_models": ["M626"],
                    },
                }
            ],
            "outputs": {"source_report": {"required": True, "format": "xlsx"}},
            "memory": {"reuse_policy": "confirmed_only"},
        }

    builder = SpecBuilder(
        store=RunStore(workspace=tmp_path),
        today=date(2026, 6, 8),
        llm_converter=download_payload,
    )

    result = builder.build(SpecBuildRequest(user_goal="请查询M626的最近的批次良率"))

    assert result.spec.status == "ready"
    assert result.spec.workflow[0].skill == "report_download"
    assert result.spec.workflow[0].id == "download_batch_yield"
    assert result.spec.workflow[0].input["report_type"] == "batch_yield"
    assert result.spec.workflow[0].input["product_models"] == ["M626"]
    assert result.spec.workflow[0].input["start_date"] == "2026-03-10"
    assert result.spec.workflow[0].input["end_date"] == "2026-06-08"
    assert result.spec.inputs["reports"][0]["alias"] == "source_batch_yield"
    assert result.spec.inputs["reports"][0]["report_type"] == "batch_yield"


def test_spec_builder_preserves_monthly_grain_for_monthly_trend_goal(tmp_path: Path) -> None:
    def monthly_payload(request: SpecBuildRequest) -> dict:
        payload = _analysis_spec_payload(request)
        payload["constraints"]["capability"] = "yield-trend"
        payload["inputs"]["date_range"] = {"start": "2026-03-15", "end": "2026-06-15"}
        payload["inputs"]["analysis"] = {
            "time_grain": "monthly",
            "requested_periods": 3,
            "metrics": ["月度良率"],
            "analysis_intent": "trend",
        }
        payload["workflow"][0]["input"].update(
            {
                "time_range": {"start": "2026-03-15", "end": "2026-06-15"},
                "metrics": ["月度良率"],
                "time_grain": "monthly",
                "requested_periods": 3,
            }
        )
        return payload

    builder = SpecBuilder(
        store=RunStore(workspace=tmp_path),
        today=date(2026, 6, 15),
        llm_converter=monthly_payload,
    )

    result = builder.build(
        SpecBuildRequest(
            user_goal="请分析M678最近三个月的月度良率变化趋势；如果有恶化，请给出恶化原因"
        )
    )

    step_input = result.spec.workflow[0].input
    assert result.spec.inputs["date_range"] == {"start": "2026-03-15", "end": "2026-06-15"}
    assert result.spec.inputs["analysis"]["time_grain"] == "monthly"
    assert result.spec.inputs["analysis"]["requested_periods"] == 3
    assert step_input["time_grain"] == "monthly"
    assert step_input["requested_periods"] == 3
    assert step_input["metrics"] == ["月度良率"]
    assert "日度良率" not in step_input["metrics"]


def test_spec_builder_uses_langgraph_agent_then_code_validation(tmp_path: Path) -> None:
    def fake_converter(request: SpecBuildRequest):
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

    builder = SpecBuilder(
        store=RunStore(workspace=tmp_path),
        today=date(2026, 6, 8),
        llm_converter=fake_converter,
    )

    result = builder.build(
        SpecBuildRequest(
            user_goal="请分析C522近一周的良率变化趋势",
        )
    )

    assert result.spec.status == "ready"
    assert result.spec.run_id == "agent-data-analysis-20260608-000000"
    assert result.spec.constraints["spec_builder"] == "langgraph"
    assert result.validation_issues == []
    assert result.spec_path.exists()


def test_spec_builder_repairs_invalid_langgraph_draft(tmp_path: Path) -> None:
    calls = 0

    def converter(request: SpecBuildRequest):
        nonlocal calls
        calls += 1
        if calls == 1:
            return "not-json"
        return _analysis_spec_payload(request)

    builder = SpecBuilder(
        store=RunStore(workspace=tmp_path),
        today=date(2026, 6, 8),
        llm_converter=converter,
    )

    result = builder.build(
        SpecBuildRequest(
            user_goal="请分析C522近一周的良率变化趋势",
        )
    )

    assert calls == 2
    assert result.spec.status == "ready"
    assert result.spec.workflow[0].skill == "data_analysis"
    assert result.warnings


def test_spec_builder_rejects_rule_mode_for_non_fixed_capability(tmp_path: Path) -> None:
    builder = SpecBuilder(store=RunStore(workspace=tmp_path), today=date(2026, 6, 8))

    result = builder.build(
        SpecBuildRequest(
            user_goal="请查询M626的最近的批次良率",
            capability="report_download",
            fixed_flow=True,
        )
    )

    assert result.spec.status == "needs_confirmation"
    assert result.validation_issues
