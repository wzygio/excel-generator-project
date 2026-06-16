"""Models for the report_download skill."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from yield_report.core.query_parser import ReportType


class ReportDownloadRequest(BaseModel):
    """Structured request for downloading or locating report source files."""

    user_query: str = Field(default="", description="Optional natural-language download request.")
    report_ref: Any | None = Field(default=None, description="Spec report alias or report mapping.")
    report_type: ReportType | None = None
    start_date: str | None = None
    end_date: str | None = None
    product_models: list[str] | None = None
    month_count: int | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    prefer_decrypted: bool = False


class ReportDownloadFile(BaseModel):
    """One file returned by the report_download skill."""

    success: bool
    file_description: str = ""
    file_path: str | None = None
    error_message: str = ""
