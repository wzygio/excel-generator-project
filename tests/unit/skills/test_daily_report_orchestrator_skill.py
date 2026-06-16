from __future__ import annotations

import subprocess
from pathlib import Path
from zipfile import BadZipFile

from openpyxl import Workbook

from yield_report.agent.registry import build_default_runtime
from yield_report.agent.spec_model import RunContext, SkillCall, TaskSpec
from yield_report.skills.daily_report import task0_task2_orchestrator as orchestrator_module
from yield_report.skills.daily_report import tool
from yield_report.skills.daily_report.models import DailyReportRequest


def _write_minimal_data_packet(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "Data Packet"
    sheet.append(
        [
            "产品类型",
            "产品",
            "日期",
            "Top3 Group Gap",
            "Top3 Group Batch Info",
            "1.1 过货影响",
            "1.3 当日异常",
            "1.4 已知异常",
        ]
    )
    sheet.append(
        [
            "C522",
            "C522",
            "2026-06-15",
            "{Group：Array_Pixel}-{当日良率：89.56%}-{良率目标：92.00%}-{Gap：-2.44%}",
            "{Group：Array_Pixel}-{最新批次：26/06/15}-{批次良率：89.00%}-{批次情况：该Group最新批次有异常}",
            "1.1 Array_Pixel 过货影响",
            "1.3 当日异常",
            "【异常】已知异常",
        ]
    )
    workbook.save(path)
    workbook.close()


def test_daily_report_skill_runs_task0_task2_orchestrator(monkeypatch, tmp_path: Path) -> None:
    duty_workspace = tmp_path / "duty"
    scripts_dir = duty_workspace / "scripts"
    scripts_dir.mkdir(parents=True)
    for name in (
        "task0_report_download.py",
        "task1_gap_analysis.py",
        "task2_extract_anomalies.py",
    ):
        (scripts_dir / name).write_text("# test script\n", encoding="utf-8")
    monkeypatch.setattr(orchestrator_module, "TASK1_GAP_ANALYSIS_SCRIPT", scripts_dir / "task1_gap_analysis.py")

    output_dir = tmp_path / "run" / "outputs"
    output_path = output_dir / "generated.xlsx"
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        command_text = [str(part) for part in command]
        calls.append(command_text)
        if "task0_report_download.py" in command_text[1]:
            _write_minimal_data_packet(output_path)
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout='{"ok": true}',
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = tool.run(
        DailyReportRequest(
            report_date="2026-06-15",
            output_dir=output_dir,
            output_name="generated.xlsx",
            orchestrator_workspace=duty_workspace,
            orchestrator_now="2026-06-15 16:00",
            run_inspection=False,
            task2_max_anomaly_row=2365,
        ),
        RunContext(run_id="run-1", workspace=tmp_path, output_dir=output_dir),
    )

    assert result.success is True
    assert result.skill_name == "daily_report"
    assert [Path(call[1]).name for call in calls] == [
        "task0_report_download.py",
        "task1_gap_analysis.py",
        "task1_gap_analysis.py",
        "task2_extract_anomalies.py",
    ]
    assert [call[0] for call in calls] == ["python", "python", "python", "python"]
    assert calls[1][2:] == ["--self-test"]
    assert calls[2][2:] == [str(output_path), "--write", "--now", "2026-06-15 16:00"]
    assert calls[3][-2:] == ["--max-anomaly-row", "2365"]
    assert result.artifacts[0].kind == "excel"
    assert Path(result.artifacts[0].path) == output_path
    assert result.data["workflow"] == [
        "task0-report-download",
        "task1-gap-analysis",
        "task2-extract-anomalies",
    ]
    assert result.data["verification"]["row_count"] == 1


def test_agent_runtime_runs_daily_report_orchestrator(monkeypatch, tmp_path: Path) -> None:
    duty_workspace = tmp_path / "duty"
    scripts_dir = duty_workspace / "scripts"
    scripts_dir.mkdir(parents=True)
    for name in (
        "task0_report_download.py",
        "task1_gap_analysis.py",
        "task2_extract_anomalies.py",
    ):
        (scripts_dir / name).write_text("# test script\n", encoding="utf-8")
    monkeypatch.setattr(orchestrator_module, "TASK1_GAP_ANALYSIS_SCRIPT", scripts_dir / "task1_gap_analysis.py")

    output_dir = tmp_path / "specs" / "runs" / "run-daily" / "outputs"
    output_path = output_dir / "runtime-generated.xlsx"
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        command_text = [str(part) for part in command]
        calls.append(command_text)
        if "task0_report_download.py" in command_text[1]:
            _write_minimal_data_packet(output_path)
        return subprocess.CompletedProcess(command, 0, stdout='{"ok": true}', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    spec = TaskSpec(
        run_id="run-daily",
        user_goal="生成 2026-06-15 16:00 良率日报",
        workflow=[
            SkillCall(
                id="generate_daily_report",
                skill="daily_report",
                input={
                    "report_date": "2026-06-15",
                    "output_dir": str(output_dir),
                    "output_name": "runtime-generated.xlsx",
                    "orchestrator_workspace": str(duty_workspace),
                    "orchestrator_now": "2026-06-15 16:00",
                    "run_inspection": False,
                },
            )
        ],
    )
    context = RunContext(run_id="run-daily", workspace=tmp_path, output_dir=output_dir)

    results = build_default_runtime().run_spec(spec, context)

    assert results[0].success is True
    assert Path(results[0].data["output_file"]) == output_path
    assert [Path(call[1]).name for call in calls] == [
        "task0_report_download.py",
        "task1_gap_analysis.py",
        "task1_gap_analysis.py",
        "task2_extract_anomalies.py",
    ]
    assert (tmp_path / "specs" / "runs" / "run-daily" / "run_summary.json").exists()


def test_daily_report_skill_compares_generated_workbook_to_reference(
    monkeypatch,
    tmp_path: Path,
) -> None:
    duty_workspace = tmp_path / "duty"
    scripts_dir = duty_workspace / "scripts"
    scripts_dir.mkdir(parents=True)
    for name in (
        "task0_report_download.py",
        "task1_gap_analysis.py",
        "task2_extract_anomalies.py",
    ):
        (scripts_dir / name).write_text("# test script\n", encoding="utf-8")
    monkeypatch.setattr(orchestrator_module, "TASK1_GAP_ANALYSIS_SCRIPT", scripts_dir / "task1_gap_analysis.py")

    output_dir = tmp_path / "output"
    output_path = output_dir / "generated.xlsx"
    reference_path = tmp_path / "reference.xlsx"
    _write_minimal_data_packet(reference_path)

    def fake_run(command, **kwargs):
        command_text = [str(part) for part in command]
        if "task0_report_download.py" in command_text[1]:
            _write_minimal_data_packet(output_path)
        return subprocess.CompletedProcess(command, 0, stdout='{"ok": true}', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = tool.run(
        DailyReportRequest(
            report_date="2026-06-15",
            output_dir=output_dir,
            output_name="generated.xlsx",
            orchestrator_workspace=duty_workspace,
            orchestrator_now="2026-06-15 16:00",
            run_inspection=False,
            reference_workbook=reference_path,
        ),
        RunContext(run_id="run-compare", workspace=tmp_path, output_dir=output_dir),
    )

    assert result.success is True
    assert result.data["comparison"]["match"] is True
    assert result.data["comparison"]["differences"] == []


def test_daily_report_verification_falls_back_to_excel_com_for_encrypted_workbooks(
    monkeypatch,
    tmp_path: Path,
) -> None:
    encrypted_path = tmp_path / "encrypted.xlsx"
    encrypted_path.write_text("not a zip workbook", encoding="utf-8")

    def raise_bad_zip(*args, **kwargs):
        raise BadZipFile("File is not a zip file")

    monkeypatch.setattr(orchestrator_module, "load_workbook", raise_bad_zip)
    monkeypatch.setattr(
        orchestrator_module,
        "_read_sheet_values_with_excel_com",
        lambda path, sheet_name: [
            [
                "产品类型",
                "1.1 过货影响",
                "1.3 当日异常",
                "1.4 已知异常",
            ],
            ["C522", "impact", "today", "known"],
        ],
    )

    verification = orchestrator_module.verify_daily_report_workbook(encrypted_path)

    assert verification["row_count"] == 1
    assert verification["nonblank_counts"] == {
        "1.1 过货影响": 1,
        "1.3 当日异常": 1,
        "1.4 已知异常": 1,
    }
