from __future__ import annotations

from pathlib import Path

from yield_report.agent.spec_model import RunContext, SkillResult
from yield_report.application.analysis_orchestrator import (
    AnalysisResult,
    AnalysisWorkflowStep,
)
from yield_report.core.analysis_query_parser import AnalysisQueryRequest
from yield_report.core.query_parser import ReportType
from yield_report.skills.data_analysis import tool
from yield_report.skills.data_analysis.models import DataAnalysisRequest


def _analysis_request() -> AnalysisQueryRequest:
    return AnalysisQueryRequest(
        source_file_type=ReportType.DAILY_YIELD,
        product_models=["M678"],
        target_metrics=["CT良率"],
        analysis_logic="趋势分析",
        user_intent="分析 M678 CT 良率趋势",
    )


def test_data_analysis_skill_uses_upstream_artifact(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "daily.xlsx"
    source.write_bytes(b"PK\x03\x04")
    seen: dict[str, object] = {}

    class FakeOrchestrator:
        def analyze(self, user_query: str, file_path: Path | None = None, file_name: str | None = None):
            seen["query"] = user_query
            seen["file_path"] = file_path
            return AnalysisResult(
                success=True,
                result_text="analysis ok",
                parsed_request=_analysis_request(),
                source_file_path=file_path,
                memory_record_id="mem-1",
                workflow_steps=[
                    AnalysisWorkflowStep(name="需求解析", status="success", detail="ok")
                ],
            )

    monkeypatch.setattr(
        "yield_report.skills.data_analysis.implementation.AnalysisOrchestrator",
        FakeOrchestrator,
    )
    upstream = SkillResult(
        skill_name="report_download",
        success=True,
        artifacts=[],
        data={"files": [{"success": True, "file_path": str(source)}]},
    )

    result = tool.run(
        DataAnalysisRequest(
            question="请分析M678近一周的日度CT良率变化趋势",
            report_refs=[upstream],
        ),
        RunContext(run_id="run-1", workspace=tmp_path),
    )

    assert result.success is True
    assert result.data["result_text"] == "analysis ok"
    assert result.memory_updates[0].record_id == "mem-1"
    assert seen["file_path"] == source


def test_data_analysis_skill_returns_structured_error(monkeypatch, tmp_path: Path) -> None:
    class FakeOrchestrator:
        def analyze(self, user_query: str, file_path: Path | None = None, file_name: str | None = None):
            return AnalysisResult(
                success=False,
                error_message="analysis failed",
                workflow_steps=[
                    AnalysisWorkflowStep(name="文件扫描", status="failed", detail="missing")
                ],
            )

    monkeypatch.setattr(
        "yield_report.skills.data_analysis.implementation.AnalysisOrchestrator",
        FakeOrchestrator,
    )

    result = tool.run(
        DataAnalysisRequest(question="分析不存在的文件"),
        RunContext(run_id="run-1", workspace=tmp_path),
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "data_analysis.execution.failed"
