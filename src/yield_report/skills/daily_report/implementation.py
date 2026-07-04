"""Thin implementation wrapper for the daily_report skill."""

from __future__ import annotations

from pathlib import Path

from yield_report.agent.spec_model import RunContext, SkillResult
from yield_report.skills.daily_report.models import DailyReportRequest

TOOL_NAME = "daily_report"


def execute_daily_report(
    request: DailyReportRequest,
    context: RunContext | None = None,
) -> SkillResult:
    """Run the external daily-report generator pipeline and return a SkillResult."""
    context = context or RunContext(run_id="manual-run", workspace=Path.cwd())
    from yield_report.skills.daily_report.native_pipeline import run_native_daily_report

    return run_native_daily_report(request, context=context)
