"""Built-in skill registry for the lightweight Agent runtime."""

from __future__ import annotations

from yield_report.agent.runtime import AgentRuntime
from yield_report.skills.daily_report import tool as daily_report_tool
from yield_report.skills.data_analysis import tool as data_analysis_tool
from yield_report.skills.report_download import tool as report_download_tool


def build_default_runtime() -> AgentRuntime:
    """Register all project skills that Codex can call through TaskSpec."""
    runtime = AgentRuntime()
    runtime.register(
        report_download_tool.name,
        report_download_tool.request_model,
        report_download_tool.run,
    )
    runtime.register(
        data_analysis_tool.name,
        data_analysis_tool.request_model,
        data_analysis_tool.run,
    )
    runtime.register(
        daily_report_tool.name,
        daily_report_tool.request_model,
        daily_report_tool.run,
    )
    return runtime
