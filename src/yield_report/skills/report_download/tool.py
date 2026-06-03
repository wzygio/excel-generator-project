"""Codex-facing tool entrypoint for report_download."""

from __future__ import annotations

from yield_report.agent.spec_model import RunContext, SkillResult
from yield_report.infrastructure.logging_config import configure_yield_report_logging_for_context
from yield_report.skills.report_download.implementation import TOOL_NAME, execute_report_download
from yield_report.skills.report_download.models import ReportDownloadRequest

name = TOOL_NAME
description = "Download or locate yield-report source files from FineReport/local sources."
request_model = ReportDownloadRequest


def run(request: ReportDownloadRequest, context: RunContext) -> SkillResult:
    configure_yield_report_logging_for_context(context)
    result = execute_report_download(request)
    context.remember("last_report_download", result)
    return result
