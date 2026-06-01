"""Implementation adapter for the report_download skill."""

from __future__ import annotations

from pathlib import Path

from yield_report.agent.spec_model import ArtifactRef, SkillError, SkillResult
from yield_report.application.orchestrator import DataAcquisitionOrchestrator, UserQueryResult
from yield_report.core.query_parser import ReportQueryRequest, ReportType
from yield_report.skills.report_download.models import ReportDownloadFile, ReportDownloadRequest

TOOL_NAME = "report_download"


def execute_report_download(
    request: ReportDownloadRequest,
    orchestrator: DataAcquisitionOrchestrator | None = None,
) -> SkillResult:
    """Run report acquisition through the existing application workflow."""
    orchestrator = orchestrator or DataAcquisitionOrchestrator()
    legacy_result = _run_legacy_workflow(request, orchestrator)
    files = [_to_file_model(item).model_dump(mode="json") for item in legacy_result.results]
    artifacts = [
        ArtifactRef(
            kind="excel",
            path=Path(file_model["file_path"]),
            description=file_model["file_description"],
            metadata={"skill": TOOL_NAME},
        )
        for file_model in files
        if file_model["success"] and file_model["file_path"]
    ]
    warnings = [
        f"{file_model['file_description']}: {file_model['error_message']}"
        for file_model in files
        if not file_model["success"] and file_model["error_message"]
    ]

    return SkillResult(
        skill_name=TOOL_NAME,
        success=legacy_result.success,
        summary=legacy_result.summary,
        artifacts=artifacts,
        data={
            "parsed_request": legacy_result.parsed_request.model_dump(mode="json"),
            "files": files,
        },
        warnings=warnings,
        error=None
        if legacy_result.success
        else SkillError(
            code="report_download.execution.failed",
            message=legacy_result.summary,
            recoverable=True,
            details={"files": files},
        ),
    )


def _run_legacy_workflow(
    request: ReportDownloadRequest,
    orchestrator: DataAcquisitionOrchestrator,
) -> UserQueryResult:
    if request.report_type is None and request.report_ref is None and request.user_query.strip():
        return orchestrator.process_user_query(request.user_query.strip())

    report_ref = _normalize_report_ref(request.report_ref)
    filters = dict(report_ref.get("filters", {}))
    filters.update(request.filters)
    report_type = request.report_type or _coerce_report_type(report_ref.get("report_type"))
    report_request = ReportQueryRequest(
        report_type=report_type,
        start_date=request.start_date or _filter_value(filters, "start_date"),
        end_date=request.end_date or _filter_value(filters, "end_date"),
        product_models=request.product_models
        if request.product_models is not None
        else _filter_value(filters, "product_models"),
        user_intent=request.user_query or report_ref.get("alias", "") or "Spec-driven report download",
    )
    return orchestrator.process_request(report_request)


def _normalize_report_ref(report_ref) -> dict:
    if isinstance(report_ref, dict):
        return report_ref
    if isinstance(report_ref, str) and report_ref:
        return {"alias": report_ref, "report_type": report_ref}
    return {}


def _coerce_report_type(value) -> ReportType | None:
    if value is None:
        return None
    try:
        return ReportType(value)
    except Exception:
        return None


def _filter_value(filters: dict, key: str):
    value = filters.get(key)
    if value is None:
        value = filters.get(_camel_to_snake(key))
    return value


def _camel_to_snake(value: str) -> str:
    return value.replace("-", "_")


def _to_file_model(item) -> ReportDownloadFile:
    return ReportDownloadFile(
        success=bool(getattr(item, "success", False)),
        file_description=getattr(item, "file_description", ""),
        file_path=str(getattr(item, "file_path", "") or "") or None,
        error_message=getattr(item, "error_message", ""),
    )
