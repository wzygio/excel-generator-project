"""Native daily-report-generator facade for the daily_report skill."""
# pyright: reportMissingImports=false

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from yield_report.agent.spec_model import ArtifactRef, RunContext, SkillError, SkillResult
from yield_report.skills.daily_report.models import DailyReportRequest

TOOL_NAME = "daily_report"
GENERATOR_ROOT_ENV = "YIELD_REPORT_DAILY_REPORT_GENERATOR_ROOT"
DUTY_WORKSPACE_ENV = "YIELD_REPORT_DUTY_WORKSPACE"
DEFAULT_GENERATOR_ROOT = Path.home() / ".agents" / "skills" / "daily-report-generator"
DEFAULT_DUTY_WORKSPACE = Path(
    "D:/wzy/\u5de5\u4f5c-\u503c\u73ed\u5de5\u4f5c/\u76f8\u5173\u6587\u4ef6"
)
TASK0_SCRIPT = Path("scripts") / "task0_report_download.py"


def run_native_daily_report(request: DailyReportRequest, context: RunContext) -> SkillResult:
    """Run the user-installed native daily-report-generator pipeline."""
    try:
        runner_request = _normalize_runner_request(request)
        generator_root = _resolve_generator_root(request)
        workspace = _resolve_workspace(runner_request)
        result = _run_generator(
            generator_root=generator_root,
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
                    metadata={"skill": TOOL_NAME, "runtime": "daily-report-generator"},
                )
            )
        return SkillResult(
            skill_name=TOOL_NAME,
            success=True,
            summary=f"Native daily-report pipeline completed: {output_file or workspace}",
            artifacts=artifacts,
            data={
                "runtime": "daily-report-generator",
                "generator_root": str(generator_root),
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
            summary=f"Native daily-report pipeline failed: {exc}",
            data={
                "runtime": "daily-report-generator",
                "workspace": str(_resolve_workspace(_normalize_runner_request(request))),
            },
            error=SkillError(
                code="daily_report.native_pipeline.failed",
                message=str(exc),
                recoverable=True,
                details={"exception_type": type(exc).__name__},
            ),
        )


def _run_generator(
    *,
    generator_root: Path,
    workspace: Path,
    request: DailyReportRequest,
    context: RunContext,
) -> dict[str, Any]:
    if not generator_root.exists():
        raise FileNotFoundError(f"daily-report-generator skill is missing: {generator_root}")
    if str(generator_root) not in sys.path:
        sys.path.insert(0, str(generator_root))

    from daily_report.config_loader import (
        load_pipeline_config,  # type: ignore[reportMissingImports]
    )
    from daily_report.orchestrator import PipelineRunner  # type: ignore[reportMissingImports]

    config = load_pipeline_config(generator_root / "configs" / "pipeline.toml")
    runner = PipelineRunner(
        config,
        workspace=workspace,
        mode="write",
        task_filter="all",
        now=request.orchestrator_now,
        end_date=request.report_date,
        snapshot_dir=Path(context.output_dir),
    )
    return dict(runner.run())


def _normalize_runner_request(request: DailyReportRequest) -> DailyReportRequest:
    if not request.report_date:
        return request
    return request.model_copy(
        update={"orchestrator_now": f"{request.report_date} 16:00"},
    )


def _resolve_generator_root(request: DailyReportRequest) -> Path:
    configured = (
        request.source_files.get("daily_report_generator_root")
        or os.getenv(GENERATOR_ROOT_ENV)
        or DEFAULT_GENERATOR_ROOT
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
