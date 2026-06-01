"""Agent-level memory facade."""

from __future__ import annotations

from pathlib import Path

from yield_report.core.analysis_query_parser import AnalysisQueryRequest
from yield_report.infrastructure.analysis_memory import (
    AnalysisMemoryCandidate,
    AnalysisMemoryRecord,
    AnalysisMemoryStore,
)


class AgentMemory:
    """Facade for cross-skill memory access.

    The current implementation delegates data-analysis mappings to the existing
    JSON-backed store. Additional skill memories can be added behind this module
    without changing Codex-facing runtime code.
    """

    def __init__(self, analysis_memory_path: Path | None = None) -> None:
        self.analysis = AnalysisMemoryStore(analysis_memory_path)

    def find_analysis_candidates(
        self,
        request: AnalysisQueryRequest,
        limit: int = 3,
    ) -> list[AnalysisMemoryCandidate]:
        return self.analysis.find_candidates(request, limit=limit)

    def confirm_analysis(self, record_id: str) -> AnalysisMemoryRecord:
        return self.analysis.confirm(record_id)

    def reject_analysis(self, record_id: str) -> AnalysisMemoryRecord:
        return self.analysis.reject(record_id)
