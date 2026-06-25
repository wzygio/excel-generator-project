"""Task0-Task4 orchestrator facade for the daily_report skill."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from yield_report.agent.spec_model import ArtifactRef, RunContext, SkillError, SkillResult
from yield_report.skills.daily_report.models import DailyReportRequest

TOOL_NAME = "daily_report"
RUNTIME_NAME = "task0-task4-orchestrator"
ORCHESTRATOR_ROOT_ENV = "YIELD_REPORT_TASK0_TASK4_ORCHESTRATOR_ROOT"
DUTY_WORKSPACE_ENV = "YIELD_REPORT_DUTY_WORKSPACE"
DEFAULT_ORCHESTRATOR_ROOT = Path.home() / ".agents" / "skills" / "task0-task4-orchestrator"
DEFAULT_DUTY_WORKSPACE = Path("D:/wzy/工作-值班工作/相关文件")
ORCHESTRATOR_CLI = Path("scripts") / "daily_report_cli.py"
TASK0_SCRIPT = Path("scripts") / "task0_report_download.py"


def run_native_daily_report(request: DailyReportRequest, context: RunContext) -> SkillResult:
    """Run the user-facing Task0-Task4 orchestrator pipeline."""
    try:
        runner_request = _normalize_runner_request(request)
        orchestrator_root = _resolve_orchestrator_root(request)
        workspace = _resolve_workspace(runner_request)
        result = _run_orchestrator_cli(
            orchestrator_root=orchestrator_root,
            workspace=workspace,
            request=runner_request,
            context=context,
        )
        output_file = _result_output_file(result)
        artifacts = []
        if output_file is not None:
            artifacts.append(
                ArtifactRef(
                    kind="excel",
                    path=output_file,
                    description="Native generated daily report workbook",
                    metadata={"skill": TOOL_NAME, "runtime": RUNTIME_NAME},
                )
            )
        return SkillResult(
            skill_name=TOOL_NAME,
            success=True,
            summary=f"Task0-Task4 orchestrator completed: {output_file or workspace}",
            artifacts=artifacts,
            data={
                "runtime": RUNTIME_NAME,
                "orchestrator_root": str(orchestrator_root),
                "workspace": str(workspace),
                "output_file": str(output_file) if output_file else "",
                "workflow": _workflow_from_result(result),
                "native_result": result,
            },
            warnings=list(result.get("warnings") or []),
        )
    except Exception as exc:
        return SkillResult(
            skill_name=TOOL_NAME,
            success=False,
            summary=f"Task0-Task4 orchestrator failed: {exc}",
            data={
                "runtime": RUNTIME_NAME,
                "workspace": str(_resolve_workspace(_normalize_runner_request(request))),
            },
            error=SkillError(
                code="daily_report.native_pipeline.failed",
                message=str(exc),
                recoverable=True,
                details={"exception_type": type(exc).__name__},
            ),
        )


def _run_orchestrator_cli(
    *,
    orchestrator_root: Path,
    workspace: Path,
    request: DailyReportRequest,
    context: RunContext,
) -> dict[str, Any]:
    cli_path = orchestrator_root / ORCHESTRATOR_CLI
    if not cli_path.exists():
        raise FileNotFoundError(f"{RUNTIME_NAME} CLI is missing: {cli_path}")

    command = [
        sys.executable,
        str(cli_path),
        "run",
        "--workspace",
        str(workspace),
        "--mode",
        "write",
        "--snapshot-dir",
        str(context.output_dir),
    ]
    if request.orchestrator_now:
        command.extend(["--now", request.orchestrator_now])
    if request.report_date:
        command.extend(["--end-date", request.report_date])

    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(_format_cli_failure(completed))
    return _parse_cli_result(completed.stdout)


def _normalize_runner_request(request: DailyReportRequest) -> DailyReportRequest:
    if not request.report_date:
        return request
    return request.model_copy(
        update={"orchestrator_now": f"{request.report_date} 16:00"},
    )


def _resolve_orchestrator_root(request: DailyReportRequest) -> Path:
    configured = (
        request.source_files.get("task0_task4_orchestrator_root")
        or request.source_files.get("orchestrator_root")
        or os.getenv(ORCHESTRATOR_ROOT_ENV)
        or DEFAULT_ORCHESTRATOR_ROOT
    )
    return Path(configured).expanduser().resolve()


def _resolve_workspace(request: DailyReportRequest) -> Path:
    candidates = [
        request.orchestrator_workspace,
        request.source_files.get("orchestrator_workspace"),
        os.getenv(DUTY_WORKSPACE_ENV),
        DEFAULT_DUTY_WORKSPACE,
    ]
    for configured in candidates:
        if not configured:
            continue
        workspace = Path(configured).expanduser().resolve()
        if _is_native_duty_workspace(workspace):
            return workspace
    return Path(DEFAULT_DUTY_WORKSPACE).expanduser().resolve()


def _is_native_duty_workspace(workspace: Path) -> bool:
    return (workspace / TASK0_SCRIPT).exists()


def _parse_cli_result(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        raise RuntimeError(f"{RUNTIME_NAME} CLI returned empty stdout")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            raise RuntimeError(
                f"{RUNTIME_NAME} CLI did not return JSON stdout: {text[-1000:]}"
            ) from exc
        parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise RuntimeError(f"{RUNTIME_NAME} CLI returned non-object JSON")
    return parsed


def _format_cli_failure(completed: subprocess.CompletedProcess[str]) -> str:
    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    details = []
    if stderr:
        details.append(f"stderr={stderr[-2000:]}")
    if stdout:
        details.append(f"stdout={stdout[-2000:]}")
    suffix = "; ".join(details) if details else "no output"
    return f"{RUNTIME_NAME} CLI failed with exit code {completed.returncode}: {suffix}"


def _result_output_file(result: dict[str, Any]) -> Path | None:
    output = result.get("workbook_path")
    if not output:
        artifacts = result.get("artifacts") if isinstance(result.get("artifacts"), dict) else {}
        output = artifacts.get("output") or artifacts.get("workbook") if artifacts else None
    return Path(output).resolve() if output else None


def _workflow_from_result(result: dict[str, Any]) -> list[str]:
    tasks = result.get("tasks")
    if not isinstance(tasks, list):
        return []
    workflow: list[str] = []
    for task in tasks:
        if isinstance(task, dict) and task.get("task_id"):
            workflow.append(str(task["task_id"]))
    return workflow
