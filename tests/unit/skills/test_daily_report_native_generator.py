from __future__ import annotations

# ruff: noqa: E402,I001
# pyright: reportMissingImports=false, reportAttributeAccessIssue=false

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

GENERATOR_ROOT = Path.home() / ".agents" / "skills" / "daily-report-generator"
if str(GENERATOR_ROOT) not in sys.path:
    sys.path.insert(0, str(GENERATOR_ROOT))

from daily_report.config_loader import (
    load_task_config,  # type: ignore[reportMissingImports] # noqa: E402
)
from daily_report.contract import (  # type: ignore[reportMissingImports] # noqa: E402
    PipelineConfig,
    TaskSpec,
)
from daily_report.orchestrator import (
    PipelineRunner,  # type: ignore[reportMissingImports] # noqa: E402
)
from daily_report.tasks import legacy_task  # type: ignore[reportMissingImports] # noqa: E402

from scripts import daily_report_cli  # type: ignore[reportAttributeAccessIssue] # noqa: E402


def test_native_pipeline_passes_explicit_end_date_to_task_request(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured_requests: list[dict] = []

    def fake_run(command, **kwargs):
        request_path = Path(command[-1])
        request = json.loads(request_path.read_text(encoding="utf-8"))
        captured_requests.append(request)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "status": "success",
                    "task_id": request["task_id"],
                    "workbook_path": request["output_path"],
                    "artifacts": {"download_dir": request["download_dir"]},
                },
                ensure_ascii=False,
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    config = PipelineConfig(
        path=tmp_path / "pipeline.toml",
        shared={"workbook": {"output_stem": "V3良率日报每日异常填报表"}},
        tasks=[
            TaskSpec(
                task_id="task0",
                enabled=True,
                command=["task0-runner", "{request_json}"],
            )
        ],
    )

    result = PipelineRunner(
        config,
        workspace=tmp_path,
        mode="write",
        task_filter="task0",
        end_date="2026-06-23",
    ).run()

    assert result["status"] == "success"
    request = captured_requests[0]
    assert request["end_date"] == "2026-06-23"
    assert request["now"] == "2026-06-23 16:00"
    assert request["download_folder"] == "20260623-16：00"
    assert request["download_dir"] == str(tmp_path / "resources" / "20260623-16：00")
    assert request["output_path"] == str(
        tmp_path / "V3良率日报每日异常填报表-20260623-16：00.xlsx"
    )


def test_native_cli_passes_end_date_to_pipeline_runner(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    class FakeRunner:
        def __init__(self, config, **kwargs) -> None:
            captured["config"] = config
            captured.update(kwargs)

        def run(self):
            return {"status": "success"}

    monkeypatch.setattr(daily_report_cli, "PipelineRunner", FakeRunner)
    config_path = tmp_path / "pipeline.toml"
    config_path.write_text("[shared]\n", encoding="utf-8")

    exit_code = daily_report_cli.run_command(
        SimpleNamespace(
            config=str(config_path),
            workspace=str(tmp_path),
            mode="write",
            task="task0",
            now=None,
            end_date="2026-06-23",
            snapshot_dir=None,
        )
    )

    assert exit_code == 0
    assert captured["workspace"] == tmp_path
    assert captured["mode"] == "write"
    assert captured["task_filter"] == "task0"
    assert captured["end_date"] == "2026-06-23"


def test_task0_write_config_uses_explicit_end_date_download_dir_and_output(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured_commands: list[list[str]] = []
    output_path = tmp_path / "V3良率日报每日异常填报表-20260623-16：00.xlsx"
    download_dir = tmp_path / "resources" / "20260623-16：00"
    request = {
        "task_id": "task0",
        "mode": "write",
        "workspace": str(tmp_path),
        "workbook_path": None,
        "artifacts": {},
        "now": "2026-06-23 16:00",
        "end_date": "2026-06-23",
        "download_folder": "20260623-16：00",
        "download_dir": str(download_dir),
        "output_path": str(output_path),
        "task_config": load_task_config(
            GENERATOR_ROOT / "configs" / "task0_basic_preparation.toml"
        ),
    }
    request_path = tmp_path / "task0-request.json"
    request_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")

    def fake_run(command, **kwargs):
        captured_commands.append([str(part) for part in command])
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "status": "success",
                    "task_id": "task0",
                    "output": str(output_path),
                    "artifacts": {"download_dir": str(download_dir)},
                },
                ensure_ascii=False,
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = legacy_task.run(request_path)

    assert result["status"] == "success"
    command = captured_commands[0]
    assert "--write" in command
    assert "--download-sources" in command
    assert command[command.index("--end-date") + 1] == "2026-06-23"
    assert command[command.index("--download-dir") + 1] == str(download_dir)
    assert command[command.index("--output") + 1] == str(output_path)
