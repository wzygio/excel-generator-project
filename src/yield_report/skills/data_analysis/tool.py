"""Codex-facing tool entrypoint for data_analysis."""

from __future__ import annotations

from typing import Any

from yield_report.agent.spec_model import RunContext, SkillResult
from yield_report.skills.data_analysis import implementation
from yield_report.skills.data_analysis.models import DataAnalysisRequest

name = implementation.TOOL_NAME
description = "Analyze yield-report source files and return structured conclusions."
request_model = DataAnalysisRequest


def run(request: DataAnalysisRequest, context: RunContext) -> SkillResult:
    result = implementation.execute_data_analysis(request, context=context)
    context.remember("last_data_analysis", result)
    return result


def confirm_memory(record_id: str, corrections: dict[str, Any] | None = None):
    return implementation.confirm_memory(record_id, corrections=corrections)


def reject_memory(record_id: str):
    return implementation.reject_memory(record_id)
