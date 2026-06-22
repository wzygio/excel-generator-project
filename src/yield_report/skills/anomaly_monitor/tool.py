"""Codex-facing tool entrypoint for anomaly_monitor."""

from __future__ import annotations

from yield_report.agent.spec_model import RunContext, SkillResult
from yield_report.infrastructure.logging_config import configure_yield_report_logging_for_context
from yield_report.skills.anomaly_monitor.implementation import TOOL_NAME, execute_anomaly_monitor
from yield_report.skills.anomaly_monitor.models import AnomalyMonitorRequest

name = TOOL_NAME
description = "Identify real HL anomalies and generate traceable notification drafts."
request_model = AnomalyMonitorRequest


def run(request: AnomalyMonitorRequest, context: RunContext) -> SkillResult:
    configure_yield_report_logging_for_context(context)
    result = execute_anomaly_monitor(request, context=context)
    context.remember("last_anomaly_monitor", result)
    return result
