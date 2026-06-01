from __future__ import annotations

from pathlib import Path

from yield_report.agent.spec_model import RunContext
from yield_report.application.orchestrator import AcquisitionResult, UserQueryResult
from yield_report.core.query_parser import ReportQueryRequest, ReportType
from yield_report.skills.report_download import tool
from yield_report.skills.report_download.models import ReportDownloadRequest


def test_report_download_skill_wraps_structured_request(monkeypatch, tmp_path: Path) -> None:
    calls: list[ReportQueryRequest] = []

    class FakeOrchestrator:
        def process_request(self, request: ReportQueryRequest) -> UserQueryResult:
            calls.append(request)
            return UserQueryResult(
                success=True,
                parsed_request=request,
                results=[
                    AcquisitionResult(
                        success=True,
                        file_description="V3良率及不良率By月周天汇总报表",
                        file_path=tmp_path / "daily.xlsx",
                    )
                ],
                summary="ok",
            )

    monkeypatch.setattr(
        "yield_report.skills.report_download.implementation.DataAcquisitionOrchestrator",
        FakeOrchestrator,
    )

    result = tool.run(
        ReportDownloadRequest(
            report_type=ReportType.DAILY_YIELD,
            end_date="2026-06-01",
            product_models=["M678"],
        ),
        RunContext(run_id="run-1", workspace=tmp_path),
    )

    assert result.success is True
    assert result.artifacts[0].path == tmp_path / "daily.xlsx"
    assert result.data["parsed_request"]["report_type"] == "daily_yield"
    assert calls[0].product_models == ["M678"]


def test_report_download_skill_accepts_spec_report_ref(monkeypatch, tmp_path: Path) -> None:
    calls: list[ReportQueryRequest] = []

    class FakeOrchestrator:
        def process_request(self, request: ReportQueryRequest) -> UserQueryResult:
            calls.append(request)
            return UserQueryResult(
                success=True,
                parsed_request=request,
                results=[],
                summary="ok",
            )

    monkeypatch.setattr(
        "yield_report.skills.report_download.implementation.DataAcquisitionOrchestrator",
        FakeOrchestrator,
    )

    result = tool.run(
        ReportDownloadRequest(
            report_ref={
                "alias": "daily_yield",
                "report_type": "daily_yield",
                "filters": {
                    "end_date": "2026-06-01",
                    "product_models": ["M678"],
                },
            }
        ),
        RunContext(run_id="run-1", workspace=tmp_path),
    )

    assert result.success is True
    assert calls[0].report_type == ReportType.DAILY_YIELD
    assert calls[0].end_date == "2026-06-01"
    assert calls[0].product_models == ["M678"]


def test_report_download_skill_returns_structured_error(monkeypatch, tmp_path: Path) -> None:
    class FakeOrchestrator:
        def process_request(self, request: ReportQueryRequest) -> UserQueryResult:
            return UserQueryResult(
                success=False,
                parsed_request=request,
                results=[
                    AcquisitionResult(
                        success=False,
                        file_description="V3良率及不良率By月周天汇总报表",
                        error_message="download failed",
                    )
                ],
                summary="failed",
            )

    monkeypatch.setattr(
        "yield_report.skills.report_download.implementation.DataAcquisitionOrchestrator",
        FakeOrchestrator,
    )

    result = tool.run(
        ReportDownloadRequest(report_type=ReportType.DAILY_YIELD),
        RunContext(run_id="run-1", workspace=tmp_path),
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "report_download.execution.failed"
    assert result.warnings == ["V3良率及不良率By月周天汇总报表: download failed"]
