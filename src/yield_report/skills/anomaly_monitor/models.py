"""Models for the anomaly_monitor skill."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

AnomalyMonitorMode = Literal["detect", "draft_notice", "record", "full"]


class AnomalyMonitorRequest(BaseModel):
    """Structured request for the anomaly-monitor fixed workflow."""

    report_date: str | None = None
    product_models: list[str] | None = None
    source_files: dict[str, Path] = Field(default_factory=dict)
    report_refs: list[Any] = Field(default_factory=list)
    mode: AnomalyMonitorMode = "detect"
    write_ledgers: bool = False
    push_notifications: bool = False
    rules_profile: str = "default"
    emit_intermediate_artifacts: bool = True
    initial_rows: list[dict[str, Any]] = Field(default_factory=list)
    ct_exception_rows: list[dict[str, Any]] = Field(default_factory=list)
    batch_history_rows: list[dict[str, Any]] = Field(default_factory=list)
    detail_rows: list[dict[str, Any]] = Field(default_factory=list)
    key_station_rules: dict[str, list[str]] = Field(default_factory=dict)

    @field_validator("product_models")
    @classmethod
    def normalize_product_models(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [item.strip().upper() for item in value if item and item.strip()]
        return list(dict.fromkeys(normalized))


class NormalizedAnomalyRow(BaseModel):
    """One row from the daily anomaly initial table."""

    row_id: str
    product_model: str
    defect_desc: str
    defect_code: str = ""
    station: str
    batch: str = ""
    batch_date: str = ""
    interface_time: str = ""
    daily_loss: float = 0.0
    month_loss: float = 0.0
    week_loss: float = 0.0
    batch_loss: float = 0.0
    batch_gap: float = 0.0
    batch_output_ratio: float = 0.0
    multiplier: float = 0.0
    ng_qty: int = 0
    owner: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)


class ConcentrationEvidence(BaseModel):
    detected: bool = False
    text: str = "Map/Lot无明显集中性"
    signature: str = ""


class SpecResult(BaseModel):
    available: bool = False
    spec_ratio: float | None = None
    sample_count: int = 0
    exceeds_spec: bool = False
    reason: str = ""


class AlreadyHlResult(BaseModel):
    matched: bool = False
    reason: str = ""
    matched_record: dict[str, Any] | None = None


class AnomalyVerdict(BaseModel):
    row: NormalizedAnomalyRow
    batch_gate_passed: bool
    batch_gate_threshold: float
    concentration: ConcentrationEvidence
    already_hl: AlreadyHlResult
    spec_result: SpecResult
    decision: Literal["HL", "skipped", "blocked"]
    decision_reason: str
    warnings: list[str] = Field(default_factory=list)


class NoticeDraft(BaseModel):
    row_id: str
    product_model: str
    defect_desc: str
    text: str
