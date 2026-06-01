"""Models for the daily_report skill."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class DailyReportRequest(BaseModel):
    """Structured request for future daily report generation."""

    report_date: str | None = None
    template_ref: Path | None = None
    sections: list[str] = Field(default_factory=list)
    analysis_results: list[Any] = Field(default_factory=list)
    output_name: str | None = None
