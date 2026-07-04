"""Models for the daily_report wrapper skill."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


class DailyReportRequest(BaseModel):
    """Structured request for delegating daily report generation."""

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
    generator_workspace: Path | None = None
    orchestrator_workspace: Path | None = None
    generator_now: str | None = None
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
