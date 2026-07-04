from __future__ import annotations

from pathlib import Path

from yield_report.skills.daily_report.models import DailyReportRequest


def test_daily_report_request_accepts_wrapper_fields(tmp_path: Path) -> None:
    request = DailyReportRequest(
        report_date="2026-06-01",
        product_models=["M678"],
        source_files={"daily_report_generator_root": tmp_path / "generator"},
        output_dir=tmp_path / "output",
        sections=[" gap ", "", "trend"],
        generator_workspace=tmp_path / "duty",
        generator_now="2026-06-01 16:00",
    )

    assert request.product_models == ["M678"]
    assert request.sections == ["gap", "trend"]
    assert request.source_files["daily_report_generator_root"] == tmp_path / "generator"
    assert request.generator_workspace == tmp_path / "duty"
    assert request.generator_now == "2026-06-01 16:00"
