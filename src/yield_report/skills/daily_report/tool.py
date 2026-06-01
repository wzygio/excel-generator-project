"""Codex-facing tool entrypoint for daily_report."""

from __future__ import annotations

from yield_report.agent.spec_model import RunContext, SkillResult
from yield_report.skills.daily_report.implementation import TOOL_NAME, execute_daily_report
from yield_report.skills.daily_report.models import DailyReportRequest

name = TOOL_NAME
description = "Generate the final Excel daily yield report from analysis results."
request_model = DailyReportRequest


def run(request: DailyReportRequest, context: RunContext) -> SkillResult:
    result = execute_daily_report(request)
    context.remember("last_daily_report", result)
    return result
