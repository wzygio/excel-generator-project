"""Models for the daily_report skill."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


class DailyReportRequest(BaseModel):
    """Structured request for daily report generation."""

    report_date: str | None = None
    spec_path: Path | None = None
    template_ref: Path | None = None
    product_models: list[str] | None = None
    source_files: dict[str, Path] = Field(default_factory=dict)
    output_dir: Path | None = None
    sections: list[str] = Field(default_factory=list)
    analysis_results: list[Any] = Field(default_factory=list)
    output_name: str | None = None
    emit_intermediate_artifacts: bool = True
    use_llm_polishing: bool = False
    orchestrator_workspace: Path | None = None
    orchestrator_now: str | None = None
    run_inspection: bool = True
    download_sources: bool = False
    reference_workbook: Path | None = None
    task2_max_anomaly_row: int | None = None
    task0_timeout_seconds: int | None = None

    @field_validator("sections")
    @classmethod
    def normalize_sections(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item and item.strip()]


class ShippedProduct(BaseModel):
    """One product row from the daily shipment source."""

    product_type: str
    product: str
    report_date: str
    target_yield: float | None = None
    actual_yield: float | None = None
    is_qualified: bool | None = None
    daily_gap: float | None = None
    existing_daily_exception: str = ""
    existing_known_exception: str = ""
    source_row: int = 0


class GapItem(BaseModel):
    """Defect Group gap item."""

    defect_group: str
    actual_loss_rate: float
    target_loss_rate: float | None = None
    gap: float
    concentration_reason: str = ""


class TrendResult(BaseModel):
    """CT yield and MVI trend result."""

    checked: bool = True
    is_declining: bool = False
    mvi_share_increasing: bool = False
    date_labels: list[str] = Field(default_factory=list)
    ct_yield_values: list[float] = Field(default_factory=list)
    mvi_share_values: list[float] = Field(default_factory=list)
    skipped_reason: str = ""


class ExceptionRecord(BaseModel):
    """Exception record extracted from the CT exception table."""

    product_model: str
    defect_code: str
    report_datetime: str
    daily_loss: str = ""
    monthly_loss: str = ""
    weekly_loss: str = ""
    batch_loss: str = ""
    exception_reason: str = ""
    inline_monitoring: str = ""
    is_stopped: str = ""
    impact_scope: str = ""
    improvement_measures: str = ""
    raw_reply: str = ""


class ProductDailyReport(BaseModel):
    """Generated report for a single product."""

    product: ShippedProduct
    sections: dict[str, Any] = Field(default_factory=dict)
    gap_top_items: list[GapItem] = Field(default_factory=list)
    top_defect_codes: list[str] = Field(default_factory=list)
    trend: TrendResult = Field(default_factory=TrendResult)
    known_exceptions: list[ExceptionRecord] = Field(default_factory=list)
    new_exceptions: list[ExceptionRecord] = Field(default_factory=list)
    report_text: str = ""
    warnings: list[str] = Field(default_factory=list)


class DailyReportPayload(BaseModel):
    """Structured daily report payload written to artifacts."""

    report_date: str
    products: list[ProductDailyReport] = Field(default_factory=list)
    source_files: dict[str, str] = Field(default_factory=dict)
    downstream_results: list[dict[str, Any]] = Field(default_factory=list)
    blocked_sections: list[dict[str, str]] = Field(default_factory=list)
    output_file: str = ""
    warnings: list[str] = Field(default_factory=list)
