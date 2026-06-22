from __future__ import annotations

from datetime import date
from pathlib import Path

from yield_report.agent.registry import build_default_runtime
from yield_report.agent.run_store import RunStore
from yield_report.agent.spec_builder import SpecBuilder, SpecBuildRequest


def test_spec_builder_builds_anomaly_monitor_spec(tmp_path: Path) -> None:
    builder = SpecBuilder(store=RunStore(workspace=tmp_path), today=date(2026, 6, 8))

    result = builder.build(
        SpecBuildRequest(user_goal="执行 M678 今天异常监控，识别真实异常并生成HL通报")
    )

    assert result.spec.status == "ready"
    assert result.validation_issues == []
    assert result.spec.inputs["report_date"] == "2026-06-08"
    assert result.spec.inputs["product_models"] == ["M678"]
    assert result.spec.workflow[0].skill == "anomaly_monitor"
    assert result.spec.workflow[0].input["mode"] == "detect"
    assert result.spec.workflow[0].input["source_files"]["data_source_dir"].endswith(
        "12.良率监控日报自动化"
    )
    assert result.spec.workflow[0].input["source_files"]["spotfire"].endswith("spotfire.xlsx")
    assert result.spec.outputs["anomaly_monitor_summary"]["format"] == "markdown"


def test_spec_builder_builds_anomaly_monitor_spec_from_ascii_keyword(tmp_path: Path) -> None:
    builder = SpecBuilder(store=RunStore(workspace=tmp_path), today=date(2026, 6, 8))

    result = builder.build(
        SpecBuildRequest(
            user_goal="run anomaly_monitor for M678 and generate HL notice",
            report_date="2026-06-15",
        )
    )

    assert result.spec.workflow[0].skill == "anomaly_monitor"
    assert result.spec.inputs["report_date"] == "2026-06-15"
    assert result.spec.inputs["product_models"] == ["M678"]


def test_default_runtime_registers_anomaly_monitor() -> None:
    runtime = build_default_runtime()

    assert "anomaly_monitor" in runtime._skills
