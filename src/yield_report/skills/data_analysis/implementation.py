"""Implementation adapter for the data_analysis skill."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from yield_report.agent.spec_model import (
    ArtifactRef,
    MemoryCandidate,
    RunContext,
    SkillError,
    SkillResult,
)
from yield_report.application.analysis_orchestrator import AnalysisOrchestrator
from yield_report.skills.data_analysis.daily_report_analysis import run_daily_report_analysis
from yield_report.skills.data_analysis.models import DataAnalysisRequest

TOOL_NAME = "data_analysis"


def execute_data_analysis(
    request: DataAnalysisRequest,
    orchestrator: AnalysisOrchestrator | None = None,
    context: RunContext | None = None,
) -> SkillResult:
    """Run data analysis through the existing module-2 orchestrator."""
    if request.analysis_kind == "daily_report":
        return run_daily_report_analysis(request, context=context)

    orchestrator = orchestrator or AnalysisOrchestrator()
    file_path = request.file_path or _first_report_path(request.report_refs)
    question = _compose_question(request)
    legacy_result = orchestrator.analyze(
        question,
        file_path=file_path,
        file_name=request.file_name,
    )

    artifacts: list[ArtifactRef] = []
    if legacy_result.source_file_path:
        artifacts.append(
            ArtifactRef(
                kind="excel",
                path=legacy_result.source_file_path,
                description="data_analysis source file",
                metadata={"skill": TOOL_NAME},
            )
        )

    memory_updates: list[MemoryCandidate] = []
    if legacy_result.memory_record_id:
        memory_updates.append(
            MemoryCandidate(
                record_id=legacy_result.memory_record_id,
                summary=f"待确认数据分析记忆: {legacy_result.memory_record_id}",
                metadata={"skill": TOOL_NAME},
            )
        )

    return SkillResult(
        skill_name=TOOL_NAME,
        success=legacy_result.success,
        summary=legacy_result.summary(),
        artifacts=artifacts,
        data={
            "result_text": legacy_result.result_text,
            "schema": legacy_result.schema,
            "strategy_used": str(legacy_result.strategy_used or ""),
            "source_file_path": str(legacy_result.source_file_path or ""),
            "memory_record_id": legacy_result.memory_record_id,
            "workflow_steps": [
                {
                    "name": step.name,
                    "status": step.status,
                    "detail": step.detail,
                }
                for step in legacy_result.workflow_steps
            ],
            "parsed_request": legacy_result.parsed_request.model_dump(mode="json")
            if legacy_result.parsed_request
            else None,
        },
        error=None
        if legacy_result.success
        else SkillError(
            code="data_analysis.execution.failed",
            message=legacy_result.error_message,
            recoverable=True,
            details={"workflow_steps": [step.name for step in legacy_result.workflow_steps]},
        ),
        memory_updates=memory_updates,
    )


def confirm_memory(record_id: str, corrections: dict[str, Any] | None = None):
    """Confirm a pending data-analysis memory record."""
    return AnalysisOrchestrator().confirm_memory(record_id, corrections=corrections)


def reject_memory(record_id: str):
    """Reject a pending data-analysis memory record."""
    return AnalysisOrchestrator().reject_memory(record_id)


def _compose_question(request: DataAnalysisRequest) -> str:
    if request.question.strip():
        return request.question.strip()

    parts: list[str] = ["请执行数据分析"]
    if request.product_models:
        parts.append(f"产品型号：{', '.join(request.product_models)}")
    start = request.time_range.get("start")
    end = request.time_range.get("end")
    if start or end:
        parts.append(f"时间范围：{start or '未指定'} ~ {end or '未指定'}")
    if request.metrics:
        parts.append(f"目标指标：{', '.join(request.metrics)}")
    if request.analysis_intent:
        parts.append(f"分析意图：{request.analysis_intent}")
    return "；".join(parts)


def _first_report_path(report_refs: list[Any]) -> Path | None:
    for ref in report_refs:
        path = _path_from_ref(ref)
        if path:
            return path
    return None


def _path_from_ref(ref: Any) -> Path | None:
    if isinstance(ref, (str, Path)):
        candidate = Path(ref)
        return candidate if candidate.suffix.lower() in {".xlsx", ".xlsm", ".xls"} else None

    artifacts = getattr(ref, "artifacts", None)
    if artifacts:
        for artifact in artifacts:
            artifact_path = getattr(artifact, "path", None)
            if artifact_path:
                return Path(artifact_path)

    if isinstance(ref, dict):
        if ref.get("file_path"):
            return Path(ref["file_path"])
        for file_item in ref.get("files", []):
            if isinstance(file_item, dict) and file_item.get("file_path"):
                return Path(file_item["file_path"])
        for artifact in ref.get("artifacts", []):
            if isinstance(artifact, dict) and artifact.get("path"):
                return Path(artifact["path"])

    data = getattr(ref, "data", None)
    if isinstance(data, dict):
        path = _path_from_ref(data)
        if path:
            return path
    return None
