"""daily-report-generator facade for the daily_report skill."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from shared_kernel.config import ConfigLoader
from shared_kernel.config_model import DailyReportAgentConfig
from yield_report.agent.spec_model import ArtifactRef, RunContext, SkillError, SkillResult
from yield_report.skills.daily_report.models import DailyReportRequest

TOOL_NAME = "daily_report"
RUNTIME_NAME = "daily-report-generator"


def run_native_daily_report(request: DailyReportRequest, context: RunContext) -> SkillResult:
    """Run the user-facing daily-report-generator pipeline."""
    try:
        settings = _load_runtime_settings()
        generator_root = _resolve_generator_root(request, settings=settings)
        workspace = _resolve_workspace(request, settings=settings)
        output_dir = _resolve_output_dir(request, context=context, settings=settings)
        result = _run_generator_cli(
            generator_root=generator_root,
            workspace=workspace,
            output_dir=output_dir,
            request=request,
            context=context,
            settings=settings,
        )
        output_file = _result_output_file(result)
        result_workspace = result.get("workspace") or workspace
        artifacts = []
        if output_file is not None:
            artifacts.append(
                ArtifactRef(
                    kind="excel",
                    path=output_file,
                    description="Generated daily report workbook",
                    metadata={"skill": TOOL_NAME, "runtime": RUNTIME_NAME},
                )
            )
        return SkillResult(
            skill_name=TOOL_NAME,
            success=True,
            summary=f"{RUNTIME_NAME} completed: {output_file or result_workspace or generator_root}",
            artifacts=artifacts,
            data={
                "runtime": RUNTIME_NAME,
                "generator_root": str(generator_root),
                "workspace": str(result_workspace) if result_workspace else "",
                "output_dir": str(output_dir),
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
            summary=f"{RUNTIME_NAME} failed: {exc}",
            data={"runtime": RUNTIME_NAME},
            error=SkillError(
                code="daily_report.native_pipeline.failed",
                message=str(exc),
                recoverable=True,
                details={"exception_type": type(exc).__name__},
            ),
        )


def _run_generator_cli(
    *,
    generator_root: Path,
    workspace: Path | None,
    output_dir: Path,
    request: DailyReportRequest,
    context: RunContext,
    settings: DailyReportAgentConfig,
) -> dict[str, Any]:
    configured_cli = settings.cli_path.strip()
    if not configured_cli:
        raise ValueError("agent.daily_report.cli_path is not configured")
    cli_path = Path(configured_cli).expanduser()
    if not cli_path.is_absolute():
        cli_path = generator_root / cli_path
    cli_path = cli_path.resolve()
    if not cli_path.exists():
        raise FileNotFoundError(f"{RUNTIME_NAME} CLI is missing: {cli_path}")

    command = [
        sys.executable,
        str(cli_path),
        "run",
        "--mode",
        "write",
        "--output-dir",
        str(output_dir),
        "--snapshot-dir",
        str(_resolve_context_output_dir(context)),
    ]
    if workspace is not None:
        command.extend(["--workspace", str(workspace)])
    run_at = request.generator_now or request.orchestrator_now
    if run_at:
        command.extend(["--now", run_at])
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


def _load_runtime_settings() -> DailyReportAgentConfig:
    return ConfigLoader().get().agent.daily_report


def _resolve_generator_root(
    request: DailyReportRequest,
    *,
    settings: DailyReportAgentConfig,
) -> Path:
    env_name = settings.generator_root_env.strip()
    configured = request.generator_root or (os.getenv(env_name) if env_name else None)
    configured = configured or settings.generator_root
    if not configured:
        raise ValueError("agent.daily_report.generator_root is not configured")
    return Path(configured).expanduser().resolve()


def _resolve_workspace(
    request: DailyReportRequest,
    *,
    settings: DailyReportAgentConfig,
) -> Path | None:
    env_name = settings.workspace_env.strip()
    candidates = [
        request.generator_workspace,
        request.orchestrator_workspace,
        os.getenv(env_name) if env_name else None,
    ]
    for configured in candidates:
        if not configured:
            continue
        workspace = Path(configured).expanduser().resolve()
        if not workspace.exists() or not workspace.is_dir():
            raise NotADirectoryError(f"Configured generator workspace is invalid: {workspace}")
        return workspace
    return None


def _resolve_output_dir(
    request: DailyReportRequest,
    *,
    context: RunContext,
    settings: DailyReportAgentConfig,
) -> Path:
    configured = request.output_dir or settings.output_dir
    if not configured:
        raise ValueError("agent.daily_report.output_dir is not configured")
    output_dir = Path(configured).expanduser()
    if not output_dir.is_absolute():
        output_dir = context.workspace / output_dir
    return output_dir.resolve()


def _resolve_context_output_dir(context: RunContext) -> Path:
    output_dir = Path(context.output_dir).expanduser()
    if not output_dir.is_absolute():
        output_dir = context.workspace / output_dir
    return output_dir.resolve()


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
        if artifacts:
            output = artifacts.get("output") or artifacts.get("workbook")
    return Path(output).resolve() if output else None


def _workflow_from_result(result: dict[str, Any]) -> list[str]:
    steps = result.get("mods")
    if not isinstance(steps, list):
        steps = result.get("tasks")
    if not isinstance(steps, list):
        return []

    workflow: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        step_id = step.get("mod_id") or step.get("task_id")
        if step_id:
            workflow.append(str(step_id))
    return workflow
