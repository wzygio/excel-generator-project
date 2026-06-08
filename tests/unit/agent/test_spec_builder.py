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
