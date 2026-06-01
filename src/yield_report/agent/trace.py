"""JSONL trace writer for Agent runs."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class TraceEvent(BaseModel):
    """A single observable Agent runtime event."""

    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    run_id: str
    step_id: str
    skill: str
    status: str
    input_summary: str = ""
    output_summary: str = ""
    artifacts: list[str] = Field(default_factory=list)
    error: dict[str, Any] | None = None


class TraceWriter:
    """Append-only JSONL writer used by the lightweight runtime."""

    def __init__(self, trace_path: Path) -> None:
        self._trace_path = trace_path

    @property
    def trace_path(self) -> Path:
        return self._trace_path

    def write(self, event: TraceEvent) -> None:
        self._trace_path.parent.mkdir(parents=True, exist_ok=True)
        with self._trace_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event.model_dump(mode="json"), ensure_ascii=False) + "\n")
