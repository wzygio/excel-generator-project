from __future__ import annotations

import os
from pathlib import Path

from app.daily_report_service import (
    DailyReportFormInput,
    generate_daily_report,
    list_generated_reports,
)
from yield_report.agent.spec_model import ArtifactRef, RunContext, SkillResult


def test_generate_daily_report_returns_downloadable_artifact(tmp_path: Path) -> None:
    output_file = tmp_path / "output" / "artifacts" / "reports" / "generated" / "daily.xlsx"
    output_file.parent.mkdir(parents=True)
    output_file.write_bytes(b"fake excel")
    calls = []

    def fake_runner(request, context: RunContext) -> SkillResult:
        calls.append((request, context))
        return SkillResult(
            skill_name="daily_report",
            success=True,
            summary="generated",
            artifacts=[
                ArtifactRef(
                    kind="excel",
                    path=output_file,
                    description="Generated daily report workbook",
                )
            ],
            data={"output_file": str(output_file), "workflow": ["mod0", "mod4"]},
        )

    result = generate_daily_report(
        DailyReportFormInput(report_date="2026-07-03"),
        workspace=tmp_path,
        runner=fake_runner,
        preflight=False,
    )

    assert result.success is True
    assert result.summary == "generated"
    assert result.output_file == output_file
    assert result.downloads[0].path == output_file
    assert result.workflow == ["mod0", "mod4"]
    assert calls[0][0].report_date == "2026-07-03"
    assert calls[0][0].generator_now is None
    assert calls[0][0].output_dir == tmp_path / "output" / "artifacts" / "reports" / "generated"
    assert calls[0][1].workspace == tmp_path


def test_generate_daily_report_does_not_preflight_agent_repo_business_files(
    tmp_path: Path,
) -> None:
    calls = []

    def fake_runner(request, context: RunContext) -> SkillResult:
        calls.append((request, context))
        return SkillResult(
            skill_name="daily_report",
            success=True,
            summary="delegated",
        )

    result = generate_daily_report(
        DailyReportFormInput(report_date="2026-07-03"),
        workspace=tmp_path,
        runner=fake_runner,
    )

    assert result.success is True
    assert result.summary == "delegated"
    assert calls[0][0].source_files == {}
    assert calls[0][0].generator_workspace is None


def test_list_generated_reports_returns_recent_excel_files(tmp_path: Path) -> None:
    output_dir = tmp_path / "output" / "artifacts" / "reports" / "generated"
    output_dir.mkdir(parents=True)
    older = output_dir / "older.xlsx"
    newer = output_dir / "newer.xlsx"
    temp = output_dir / "~$newer.xlsx"
    note = output_dir / "note.txt"
    older.write_bytes(b"older")
    newer.write_bytes(b"newer")
    temp.write_bytes(b"temp")
    note.write_text("not a workbook", encoding="utf-8")
    os.utime(older, (100, 100))
    os.utime(newer, (200, 200))

    reports = list_generated_reports(output_dir, workspace=tmp_path)

    assert [report.path for report in reports] == [newer, older]
    assert reports[0].label == "newer.xlsx"
    assert reports[0].size_bytes == len(b"newer")
