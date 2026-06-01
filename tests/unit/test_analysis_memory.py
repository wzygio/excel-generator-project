from __future__ import annotations

from pathlib import Path

from yield_report.core.analysis_query_parser import AnalysisQueryRequest
from yield_report.core.query_parser import ReportType
from yield_report.infrastructure.analysis_memory import AnalysisMemoryStore


def _request() -> AnalysisQueryRequest:
    return AnalysisQueryRequest(
        source_file_type=ReportType.DAILY_YIELD,
        file_keywords=["月周天"],
        product_models=["M678"],
        start_date="2026-05-25",
        end_date="2026-06-01",
        target_metrics=["CT良率"],
        filter_conditions={"product_model": "M678"},
        analysis_logic="趋势分析",
        user_intent="分析 M678 近一周 CT 良率趋势",
    )


def test_analysis_memory_records_pending_and_confirms(tmp_path: Path) -> None:
    store = AnalysisMemoryStore(tmp_path / "analysis_memory.json")
    source = tmp_path / "daily.xlsx"
    source.write_bytes(b"PK\x03\x04")

    record = store.record_pending(
        request=_request(),
        user_query="请分析M678近一周的日度CT良率变化趋势",
        resolved_file=source,
        report_file_name="V3良率及不良率By月周天汇总报表",
        processing_method="code",
    )

    assert record.status == "pending"
    assert store.list_records()[0].local_file_name == "daily.xlsx"

    confirmed = store.confirm(record.id, corrections={"field_mappings": {"date": "日期"}})
    assert confirmed.status == "confirmed"
    assert confirmed.field_mappings == {"date": "日期"}

    candidates = store.find_candidates(_request())
    assert len(candidates) == 1
    assert candidates[0].record_id == record.id
    assert candidates[0].score > 0


def test_analysis_memory_reject_excludes_from_candidates(tmp_path: Path) -> None:
    store = AnalysisMemoryStore(tmp_path / "analysis_memory.json")
    source = tmp_path / "daily.xlsx"
    source.write_bytes(b"PK\x03\x04")

    record = store.record_pending(
        request=_request(),
        user_query="query",
        resolved_file=source,
        processing_method="code",
    )
    store.confirm(record.id)
    store.reject(record.id)

    assert store.find_candidates(_request()) == []
