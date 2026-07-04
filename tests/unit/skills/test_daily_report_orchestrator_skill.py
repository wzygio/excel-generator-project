from __future__ import annotations

import json
import subprocess
from pathlib import Path

from yield_report.agent.registry import build_default_runtime
from yield_report.agent.spec_model import ArtifactRef, RunContext, SkillCall, SkillResult, TaskSpec
from yield_report.skills.daily_report import native_pipeline, tool
from yield_report.skills.daily_report.models import DailyReportRequest


def test_daily_report_skill_delegates_to_native_pipeline(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[DailyReportRequest, RunContext]] = []
    duty_workspace = tmp_path / "duty"
    output_path = duty_workspace / "daily-report.xlsx"

    def fake_run_native_daily_report(
        request: DailyReportRequest,
        context: RunContext,
    ) -> SkillResult:
        calls.append((request, context))
        return SkillResult(
            skill_name="daily_report",
            success=True,
            summary=f"daily-report-generator completed: {output_path}",
            artifacts=[
                ArtifactRef(
                    kind="excel",
                    path=output_path,
                    description="Generated daily report workbook",
                )
            ],
            data={
                "runtime": "daily-report-generator",
                "workspace": str(duty_workspace),
                "output_file": str(output_path),
                "workflow": ["mod0", "mod1", "mod2", "mod3", "mod4"],
            },
        )

    monkeypatch.setattr(
        native_pipeline,
        "run_native_daily_report",
        fake_run_native_daily_report,
    )

    result = tool.run(
        DailyReportRequest(
            report_date="2026-06-23",
            generator_workspace=duty_workspace,
            generator_now="2026-06-23 16:00",
        ),
        RunContext(run_id="run-native", workspace=tmp_path),
    )

    assert result.success is True
    assert Path(result.artifacts[0].path) == output_path
    assert result.data["runtime"] == "daily-report-generator"
    assert calls[0][0].report_date == "2026-06-23"
    assert calls[0][0].generator_workspace == duty_workspace


def test_agent_runtime_runs_daily_report_native_facade(
    monkeypatch,
    tmp_path: Path,
) -> None:
    duty_workspace = tmp_path / "duty"
    output_path = duty_workspace / "daily-report.xlsx"

    def fake_run_native_daily_report(
        request: DailyReportRequest,
        context: RunContext,
    ) -> SkillResult:
        return SkillResult(
            skill_name="daily_report",
            success=True,
            summary="daily-report-generator completed.",
            artifacts=[
                ArtifactRef(
                    kind="excel",
                    path=output_path,
                    description="Generated daily report workbook",
                )
            ],
            data={
                "runtime": "daily-report-generator",
                "workspace": str(duty_workspace),
                "output_file": str(output_path),
            },
        )

    monkeypatch.setattr(
        native_pipeline,
        "run_native_daily_report",
        fake_run_native_daily_report,
    )
    spec = TaskSpec(
        run_id="run-daily-native",
        user_goal="Generate 2026-06-23 daily report",
        workflow=[
            SkillCall(
                id="generate_daily_report",
                skill="daily_report",
                input={
                    "report_date": "2026-06-23",
                    "generator_workspace": str(duty_workspace),
                    "generator_now": "2026-06-23 16:00",
                },
                save_as="daily_report_file",
            )
        ],
    )
    context = RunContext(run_id="run-daily-native", workspace=tmp_path)

    results = build_default_runtime().run_spec(spec, context)

    assert results[0].success is True
    assert Path(results[0].data["output_file"]) == output_path
    assert (tmp_path / "specs" / "runs" / "run-daily-native" / "run_summary.json").exists()


def test_native_facade_ignores_invalid_agent_workspace(
    monkeypatch,
    tmp_path: Path,
) -> None:
    invalid_workspace = tmp_path / "project"
    generator_root = tmp_path / "daily-report-generator"
    generator_root.mkdir()
    output_path = tmp_path / "daily-report.xlsx"
    calls: list[Path] = []

    def fake_run_generator_cli(**kwargs) -> dict[str, object]:
        calls.append(kwargs["workspace"])
        return {
            "status": "success",
            "workbook_path": str(output_path),
            "mods": [{"mod_id": "mod0"}],
        }

    monkeypatch.setattr(native_pipeline, "_run_generator_cli", fake_run_generator_cli)

    result = native_pipeline.run_native_daily_report(
        DailyReportRequest(
            report_date="2026-06-23",
            generator_workspace=invalid_workspace,
            source_files={"daily_report_generator_root": generator_root},
        ),
        RunContext(run_id="run-native-invalid-workspace", workspace=tmp_path),
    )

    assert result.success is True
    assert calls == [tmp_path.resolve()]
    assert Path(result.data["workspace"]) == tmp_path.resolve()


def test_native_facade_uses_report_date_for_runner_now(
    monkeypatch,
    tmp_path: Path,
) -> None:
    duty_workspace = tmp_path / "duty"
    duty_workspace.mkdir()
    generator_root = tmp_path / "daily-report-generator"
    generator_root.mkdir()
    output_path = duty_workspace / "daily-report.xlsx"
    calls: list[str | None] = []

    def fake_run_generator_cli(**kwargs) -> dict[str, object]:
        calls.append(kwargs["request"].generator_now)
        return {
            "status": "success",
            "workbook_path": str(output_path),
            "mods": [{"mod_id": "mod0"}],
        }

    monkeypatch.setattr(native_pipeline, "_run_generator_cli", fake_run_generator_cli)

    result = native_pipeline.run_native_daily_report(
        DailyReportRequest(
            report_date="2026-06-23",
            generator_workspace=duty_workspace,
            generator_now="2026-06-24T16:00:00",
            source_files={"daily_report_generator_root": generator_root},
        ),
        RunContext(run_id="run-native-report-date-now", workspace=tmp_path),
    )

    assert result.success is True
    assert calls == ["2026-06-23 16:00"]


def test_native_facade_calls_daily_report_generator_cli(
    monkeypatch,
    tmp_path: Path,
) -> None:
    duty_workspace = tmp_path / "duty"
    duty_workspace.mkdir()
    generator_root = tmp_path / "daily-report-generator"
    cli_path = generator_root / "scripts" / "daily_report_cli.py"
    cli_path.parent.mkdir(parents=True)
    cli_path.write_text("", encoding="utf-8")
    output_path = duty_workspace / "daily-report.xlsx"
    captured: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "status": "success",
                    "workbook_path": str(output_path),
                    "mods": [{"mod_id": "mod0"}, {"mod_id": "mod4"}],
                },
                ensure_ascii=False,
            ),
            stderr="",
        )

    monkeypatch.setattr(native_pipeline.subprocess, "run", fake_run)

    result = native_pipeline.run_native_daily_report(
        DailyReportRequest(
            report_date="2026-06-23",
            generator_workspace=duty_workspace,
            source_files={"daily_report_generator_root": generator_root},
        ),
        RunContext(run_id="run-native-generator-cli", workspace=tmp_path),
    )

    command = captured["command"]
    assert isinstance(command, list)
    assert result.success is True
    assert result.data["runtime"] == "daily-report-generator"
    assert result.data["generator_root"] == str(generator_root.resolve())
    assert result.data["output_dir"] == str(
        tmp_path / "output" / "artifacts" / "reports" / "generated"
    )
    assert str(cli_path.resolve()) in command
    assert "--workspace" in command
    assert str(duty_workspace.resolve()) in command
    assert "--output-dir" in command
    assert str(tmp_path / "output" / "artifacts" / "reports" / "generated") in command
    assert "--now" in command
    assert "2026-06-23 16:00" in command
    assert "--end-date" in command
    assert "2026-06-23" in command
    assert result.data["workflow"] == ["mod0", "mod4"]
