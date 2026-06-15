from __future__ import annotations

from datetime import date
from pathlib import Path

from yield_report.agent.run_store import RunStore
from yield_report.agent.spec_builder import SpecBuilder, SpecBuildRequest


def test_spec_builder_extracts_product_and_today(tmp_path: Path) -> None:
    builder = SpecBuilder(store=RunStore(workspace=tmp_path), today=date(2026, 6, 8))

    result = builder.build(SpecBuildRequest(user_goal="生成 M678 今天良率日报"))

    assert result.spec.status == "ready"
    assert result.spec.inputs["report_date"] == "2026-06-08"
    assert result.spec.inputs["product_models"] == ["M678"]
    assert result.spec.workflow[0].skill == "data_analysis"
    assert result.spec.workflow[1].skill == "daily_report"
    assert result.spec.workflow[0].input["source_files"]["daily_yield"].startswith("resources/")
    assert result.spec.workflow[1].input["source_files"]["spotfire"].endswith("spotfire.xlsx")
    assert result.spec_path.exists()


def test_spec_builder_allows_missing_product_for_all_models(tmp_path: Path) -> None:
    builder = SpecBuilder(store=RunStore(workspace=tmp_path), today=date(2026, 6, 8))

    result = builder.build(SpecBuildRequest(user_goal="生成今天良率日报"))

    assert result.spec.status == "ready"
    assert result.spec.inputs["product_models"] == []
    assert result.warnings == []


def test_spec_builder_requires_confirmation_when_all_products_disabled(tmp_path: Path) -> None:
    builder = SpecBuilder(store=RunStore(workspace=tmp_path), today=date(2026, 6, 8))

    result = builder.build(
        SpecBuildRequest(user_goal="生成今天良率日报", allow_all_products=False)
    )

    assert result.spec.status == "needs_confirmation"
    assert result.warnings == ["缺少产品型号，需要用户确认。"]


def test_spec_builder_parses_explicit_date_and_sections(tmp_path: Path) -> None:
    builder = SpecBuilder(store=RunStore(workspace=tmp_path), today=date(2026, 6, 8))

    result = builder.build(
        SpecBuildRequest(
            user_goal="生成 M678 2026年6月1日良率日报",
            sections=["gap", "trend", "gap"],
        )
    )

    assert result.spec.inputs["report_date"] == "2026-06-01"
    assert result.spec.inputs["date_range"] == {"start": "2026-05-26", "end": "2026-06-01"}
    assert result.spec.workflow[0].input["sections"] == ["gap", "trend"]
    assert result.spec.workflow[1].input["analysis_results"] == ["daily_report_facts"]


def test_spec_builder_builds_data_analysis_spec_for_trend_goal(tmp_path: Path) -> None:
    builder = SpecBuilder(store=RunStore(workspace=tmp_path), today=date(2026, 6, 8))

    result = builder.build(
        SpecBuildRequest(user_goal="请分析C522近一周的良率变化趋势；如果有恶化，请给出恶化原因")
    )

    assert result.spec.status == "ready"
    assert result.spec.constraints["runtime"] == "python_with_pi_fallback"
    assert result.spec.inputs["product_models"] == ["C522"]
    assert result.spec.workflow == [
        result.spec.workflow[0],
    ]
    assert result.spec.workflow[0].skill == "data_analysis"
    assert result.spec.workflow[0].input["product_models"] == ["C522"]
    assert result.spec.workflow[0].input["analysis_intent"] == "trend"
    assert "日度良率" in result.spec.workflow[0].input["metrics"]
    assert result.spec.outputs["analysis_summary"]["format"] == "markdown"


def test_spec_builder_uses_llm_json_then_code_validation(tmp_path: Path) -> None:
    def fake_converter(request: SpecBuildRequest):
        return {
            "schema_version": 1,
            "status": "draft",
            "user_goal": request.user_goal,
            "workflow": [{"id": "analyze", "skill": "data_analysis", "input": {"question": request.user_goal}}],
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
            builder_mode="llm",
        )
    )

    assert result.spec.status == "ready"
    assert result.spec.run_id == result.paths.run_id
    assert result.validation_issues == []
    assert result.spec_path.exists()


def test_spec_builder_falls_back_when_llm_spec_is_invalid(tmp_path: Path) -> None:
    builder = SpecBuilder(
        store=RunStore(workspace=tmp_path),
        today=date(2026, 6, 8),
        llm_converter=lambda request: "not-json",
    )

    result = builder.build(
        SpecBuildRequest(
            user_goal="请分析C522近一周的良率变化趋势",
            builder_mode="llm",
        )
    )

    assert result.spec.workflow[0].skill == "data_analysis"
    assert result.warnings
