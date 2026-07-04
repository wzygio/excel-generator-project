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

from daily_report.config_loader import (  # type: ignore[reportMissingImports] # noqa: E402
    load_mod_config,
)
from daily_report.contract import (  # type: ignore[reportMissingImports] # noqa: E402
    ModSpec,
    PipelineConfig,
)
from daily_report.mods import mod0_basic_preparation  # type: ignore[reportMissingImports] # noqa: E402
from daily_report.orchestrator import (  # type: ignore[reportMissingImports] # noqa: E402
    PipelineRunner,
)

from scripts import daily_report_cli  # type: ignore[reportAttributeAccessIssue] # noqa: E402


def test_native_pipeline_passes_explicit_end_date_to_mod_request(
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
                    "mod_id": request["mod_id"],
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
        shared={"workbook": {"output_stem": "daily-report"}},
        mods=[
            ModSpec(
                mod_id="mod0",
                enabled=True,
                command=["mod0-runner", "{request_json}"],
            )
        ],
    )
    output_dir = tmp_path / "output" / "artifacts" / "reports" / "generated"

    result = PipelineRunner(
        config,
        workspace=tmp_path,
        mode="write",
        mod_filter="mod0",
        end_date="2026-06-23",
        output_dir=output_dir,
    ).run()

    assert result["status"] == "success"
    request = captured_requests[0]
    assert request["mod_id"] == "mod0"
    assert request["end_date"] == "2026-06-23"
    assert request["now"] == "2026-06-23 16:00"
    assert request["download_folder"].startswith("20260623-16")
    assert request["download_dir"].startswith(str(tmp_path / "resources" / "20260623-16"))
    assert Path(request["output_path"]).parent == output_dir.resolve()
    assert Path(request["output_path"]).name.startswith("daily-report-20260623-16")


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
            mod="mod0",
            now=None,
            end_date="2026-06-23",
            output_dir=str(tmp_path / "generated"),
            snapshot_dir=None,
            yield_type=None,
        )
    )

    assert exit_code == 0
    assert captured["workspace"] == tmp_path
    assert captured["mode"] == "write"
    assert captured["mod_filter"] == "mod0"
    assert captured["end_date"] == "2026-06-23"
    assert captured["output_dir"] == tmp_path / "generated"


def test_mod0_write_config_uses_explicit_end_date_download_dir_and_output(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured_commands: list[list[str]] = []
    output_path = tmp_path / "daily-report-20260623-16.xlsx"
    download_dir = tmp_path / "resources" / "20260623-16"
    request = {
        "mod_id": "mod0",
        "mode": "write",
        "workspace": str(tmp_path),
        "workbook_path": None,
        "artifacts": {},
        "shared_config": {},
        "mod_config": load_mod_config(
            GENERATOR_ROOT / "configs" / "mod0_basic_preparation.toml"
        ),
        "now": "2026-06-23 16:00",
        "end_date": "2026-06-23",
        "download_folder": "20260623-16",
        "download_dir": str(download_dir),
        "output_path": str(output_path),
    }
    request_path = tmp_path / "mod0-request.json"
    request_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")

    def fake_run(command, **kwargs):
        captured_commands.append([str(part) for part in command])
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "status": "success",
                    "mod_id": "mod0",
                    "output": str(output_path),
                    "artifacts": {"download_dir": str(download_dir)},
                },
                ensure_ascii=False,
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = mod0_basic_preparation.run(request_path)

    assert result["status"] == "success"
    step0_command = captured_commands[0]
    write_command = captured_commands[1]
    assert "--download-sources" in step0_command
    assert "--write" in write_command
    assert write_command[write_command.index("--end-date") + 1] == "2026-06-23"
    assert write_command[write_command.index("--download-dir") + 1] == str(download_dir)
    assert write_command[write_command.index("--output") + 1] == str(output_path)
