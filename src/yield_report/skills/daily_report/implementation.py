"""Implementation adapter for the daily_report skill.

The V2 daily-report generator has not been implemented yet. This skill exists
now so TaskSpec workflows can reference a stable interface while Task3 is built.
"""

from __future__ import annotations

from yield_report.agent.spec_model import SkillError, SkillResult
from yield_report.skills.daily_report.models import DailyReportRequest

TOOL_NAME = "daily_report"


def execute_daily_report(request: DailyReportRequest) -> SkillResult:
    return SkillResult(
        skill_name=TOOL_NAME,
        success=False,
        summary="日报生成 Skill 已预留接口，V2 实现尚未接入。",
        data={
            "report_date": request.report_date,
            "sections": request.sections,
            "output_name": request.output_name,
        },
        error=SkillError(
            code="daily_report.execution.not_implemented",
            message="日报生成 V2 尚未实现。",
            recoverable=False,
        ),
    )
