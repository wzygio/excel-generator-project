"""Models for the data_analysis skill."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class DataAnalysisRequest(BaseModel):
    """Structured request for module-2 data analysis."""

    question: str = ""
    report_refs: list[Any] = Field(default_factory=list)
    file_path: Path | None = None
    file_name: str | None = None
    product_models: list[str] | None = None
    time_range: dict[str, str | None] = Field(default_factory=dict)
    metrics: list[str] = Field(default_factory=list)
    analysis_intent: str = ""
    confirmed_memory_ids: list[str] = Field(default_factory=list)
