"""JSON-backed Agent-Memory for data-analysis mappings."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from yield_report.core.analysis_query_parser import AnalysisQueryRequest
from yield_report.core.query_parser import ReportType

logger = logging.getLogger(__name__)

MemoryStatus = Literal["pending", "confirmed", "rejected"]


class AnalysisMemoryRecord(BaseModel):
    """A reusable mapping between a user need and analysis implementation details."""

    id: str = Field(default_factory=lambda: uuid4().hex)
    created_at: str = ""
    updated_at: str = ""
    status: MemoryStatus = "pending"
    user_query: str = ""
    normalized_intent: str = ""
    source_file_type: ReportType | None = None
    local_file_name: str = ""
    local_file_path: str = ""
    report_file_name: str = ""
    product_models: list[str] = Field(default_factory=list)
    target_metrics: list[str] = Field(default_factory=list)
    field_mappings: dict[str, str] = Field(default_factory=dict)
    filter_conditions: dict[str, Any] = Field(default_factory=dict)
    analysis_logic: str = ""
    processing_method: str = ""
    notes: str = ""


class AnalysisMemoryCandidate(BaseModel):
    """Compact candidate summary returned to callers."""

    record_id: str
    score: float
    local_file_name: str
    local_file_path: str
    report_file_name: str
    source_file_type: ReportType | None = None
    target_metrics: list[str] = Field(default_factory=list)
    analysis_logic: str = ""


class AnalysisMemoryStore:
    """Persist and match analysis memory records in a gitignored JSON file."""

    def __init__(self, memory_path: Path | None = None) -> None:
        self._memory_path = memory_path or Path("data/memory/analysis_memory.json")

    @property
    def memory_path(self) -> Path:
        return self._memory_path

    def list_records(self) -> list[AnalysisMemoryRecord]:
        return self._load_records()

    def get_record(self, record_id: str) -> AnalysisMemoryRecord | None:
        for record in self._load_records():
            if record.id == record_id:
                return record
        return None

    def find_candidates(
        self,
        request: AnalysisQueryRequest,
        limit: int = 3,
    ) -> list[AnalysisMemoryCandidate]:
        scored: list[tuple[float, AnalysisMemoryRecord]] = []
        for record in self._load_records():
            if record.status != "confirmed":
                continue
            score = self._score_record(request, record)
            if score > 0:
                scored.append((score, record))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            AnalysisMemoryCandidate(
                record_id=record.id,
                score=score,
                local_file_name=record.local_file_name,
                local_file_path=record.local_file_path,
                report_file_name=record.report_file_name,
                source_file_type=record.source_file_type,
                target_metrics=list(record.target_metrics),
                analysis_logic=record.analysis_logic,
            )
            for score, record in scored[:limit]
        ]

    def record_pending(
        self,
        *,
        request: AnalysisQueryRequest,
        user_query: str,
        resolved_file: Path,
        report_file_name: str = "",
        processing_method: str = "",
        field_mappings: dict[str, str] | None = None,
        notes: str = "",
    ) -> AnalysisMemoryRecord:
        now = _now_iso()
        record = AnalysisMemoryRecord(
            created_at=now,
            updated_at=now,
            status="pending",
            user_query=user_query,
            normalized_intent=request.user_intent or user_query,
            source_file_type=request.source_file_type,
            local_file_name=resolved_file.name,
            local_file_path=str(resolved_file),
            report_file_name=report_file_name or resolved_file.stem,
            product_models=list(request.product_models or []),
            target_metrics=list(request.target_metrics),
            field_mappings=field_mappings or {},
            filter_conditions=dict(request.filter_conditions),
            analysis_logic=request.analysis_logic,
            processing_method=processing_method,
            notes=notes or (request.uncertainty_notes or ""),
        )
        self._append_record(record)
        return record

    def confirm(
        self,
        record_id: str,
        corrections: dict[str, Any] | None = None,
    ) -> AnalysisMemoryRecord:
        return self._update_record(record_id, "confirmed", corrections)

    def reject(self, record_id: str) -> AnalysisMemoryRecord:
        return self._update_record(record_id, "rejected", None)

    def _append_record(self, record: AnalysisMemoryRecord) -> None:
        records = self._load_records()
        records.append(record)
        self._write_records(records)

    def _update_record(
        self,
        record_id: str,
        status: MemoryStatus,
        corrections: dict[str, Any] | None,
    ) -> AnalysisMemoryRecord:
        records = self._load_records()
        for index, record in enumerate(records):
            if record.id != record_id:
                continue
            data = record.model_dump(mode="json")
            if corrections:
                data.update(corrections)
            data["status"] = status
            data["updated_at"] = _now_iso()
            updated = AnalysisMemoryRecord(**data)
            records[index] = updated
            self._write_records(records)
            return updated
        raise KeyError(f"Analysis memory record not found: {record_id}")

    def _load_records(self) -> list[AnalysisMemoryRecord]:
        if not self._memory_path.exists():
            return []
        try:
            raw = json.loads(self._memory_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("Analysis memory JSON is invalid: %s", self._memory_path)
            return []
        if not isinstance(raw, list):
            logger.warning("Analysis memory JSON root is not a list: %s", self._memory_path)
            return []
        records: list[AnalysisMemoryRecord] = []
        for item in raw:
            try:
                records.append(AnalysisMemoryRecord(**item))
            except Exception as exc:
                logger.warning("Skipping invalid analysis memory record: %s", exc)
        return records

    def _write_records(self, records: list[AnalysisMemoryRecord]) -> None:
        self._memory_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._memory_path.with_suffix(self._memory_path.suffix + ".tmp")
        payload = [record.model_dump(mode="json") for record in records]
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(self._memory_path)

    @staticmethod
    def _score_record(
        request: AnalysisQueryRequest,
        record: AnalysisMemoryRecord,
    ) -> float:
        score = 0.0

        if request.source_file_type and request.source_file_type == record.source_file_type:
            score += 5.0

        request_models = set(request.product_models or [])
        record_models = set(record.product_models)
        if request_models and record_models:
            score += len(request_models & record_models) * 2.0

        request_metrics = {_norm(item) for item in request.target_metrics}
        record_metrics = {_norm(item) for item in record.target_metrics}
        if request_metrics and record_metrics:
            score += len(request_metrics & record_metrics) * 2.0

        haystack = _norm(
            " ".join(
                [
                    record.local_file_name,
                    record.report_file_name,
                    record.normalized_intent,
                    record.analysis_logic,
                ]
            )
        )
        for keyword in request.file_keywords:
            if _norm(keyword) and _norm(keyword) in haystack:
                score += 1.0
        if request.analysis_logic and _norm(request.analysis_logic) in _norm(record.analysis_logic):
            score += 1.0

        return score


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _norm(value: str) -> str:
    return value.lower().replace(" ", "")
