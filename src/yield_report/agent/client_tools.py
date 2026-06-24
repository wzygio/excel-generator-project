"""Letta client-tool registry for project Skills."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel

from yield_report.agent.spec_model import RunContext, SkillCall, SkillResult
from yield_report.skills.anomaly_monitor import tool as anomaly_monitor_tool
from yield_report.skills.daily_report import tool as daily_report_tool
from yield_report.skills.data_analysis import tool as data_analysis_tool
from yield_report.skills.report_download import tool as report_download_tool

RiskLevel = Literal["read", "write", "external", "destructive"]
ArgsNormalizer = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class RuntimeTool:
    """Local business capability exposed to Letta as a client tool."""

    name: str
    description: str
    parameters: dict[str, Any]
    skill_name: str
    request_model: type[BaseModel]
    risk_level: RiskLevel
    normalize_args: ArgsNormalizer = lambda args: dict(args)


def build_project_client_tool_registry() -> dict[str, RuntimeTool]:
    """Return the approved Letta client tools for project business Skills."""
    tools = [
        RuntimeTool(
            name="yield_report_download",
            description=(
                "Download or locate OLED yield source reports through the report_download Skill."
            ),
            parameters=_schema_for(report_download_tool.request_model),
            skill_name=report_download_tool.name,
            request_model=report_download_tool.request_model,
            risk_level="external",
        ),
        RuntimeTool(
            name="yield_data_analysis",
            description=(
                "Analyze local Excel source files through the data_analysis Skill."
            ),
            parameters=_schema_for(data_analysis_tool.request_model),
            skill_name=data_analysis_tool.name,
            request_model=data_analysis_tool.request_model,
            risk_level="read",
            normalize_args=_normalize_data_analysis_args,
        ),
        RuntimeTool(
            name="yield_daily_report",
            description=(
                "Generate the final OLED daily report workbook through the daily_report Skill."
            ),
            parameters=_schema_for(daily_report_tool.request_model),
            skill_name=daily_report_tool.name,
            request_model=daily_report_tool.request_model,
            risk_level="external",
            normalize_args=_normalize_daily_report_args,
        ),
        RuntimeTool(
            name="yield_anomaly_monitor",
            description="Run the anomaly_monitor Skill for fixed anomaly monitoring workflows.",
            parameters=_schema_for(anomaly_monitor_tool.request_model),
            skill_name=anomaly_monitor_tool.name,
            request_model=anomaly_monitor_tool.request_model,
            risk_level="write",
        ),
    ]
    return {tool.name: tool for tool in tools}


def to_letta_client_tools(registry: dict[str, RuntimeTool] | list[RuntimeTool]) -> list[dict[str, Any]]:
    tools = registry.values() if isinstance(registry, dict) else registry
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        }
        for tool in tools
    ]


def execute_runtime_tool(
    *,
    tool_name: str,
    arguments: dict[str, Any],
    registry: dict[str, RuntimeTool],
    project_runtime: Any,
    context: RunContext,
) -> tuple[SkillCall, SkillResult, dict[str, Any]]:
    tool = registry.get(tool_name)
    if tool is None:
        raise KeyError(tool_name)
    normalized = tool.normalize_args(arguments)
    tool.request_model(**normalized)
    call = SkillCall(
        id=f"letta_{tool.name}",
        skill=tool.skill_name,
        input=normalized,
    )
    result = project_runtime.run_call(call, context)
    return call, result, compact_tool_result(result)


def compact_tool_result(result: SkillResult) -> dict[str, Any]:
    return {
        "status": "success" if result.success else "error",
        "summary": result.summary,
        "artifacts": [
            {
                "kind": artifact.kind,
                "path": str(artifact.path),
                "description": artifact.description,
            }
            for artifact in result.artifacts
        ],
        "metrics": _metrics_from_data(result.data),
        "warnings": result.warnings,
        "error": result.error.model_dump(mode="json") if result.error else None,
    }


def _schema_for(model: type[BaseModel]) -> dict[str, Any]:
    schema = model.model_json_schema()
    schema.setdefault("type", "object")
    return schema


def _normalize_data_analysis_args(args: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(args)
    analysis_goal = str(normalized.get("analysis_goal") or "").strip()
    if analysis_goal and not str(normalized.get("question") or "").strip():
        normalized["question"] = analysis_goal
    intent = str(normalized.get("analysis_intent") or "").strip()
    if not intent and any(keyword in analysis_goal for keyword in ["趋势", "变化", "波动", "恶化"]):
        normalized["analysis_intent"] = "trend"
    return normalized


def _normalize_daily_report_args(args: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(args)
    end_date = str(normalized.get("end_date") or "").strip()
    if end_date and not str(normalized.get("report_date") or "").strip():
        normalized["report_date"] = end_date
    return normalized


def _metrics_from_data(data: dict[str, Any]) -> dict[str, Any]:
    metric_keys = {"row_count", "duration_ms", "rows_written", "record_count"}
    return {
        key: value
        for key, value in data.items()
        if key in metric_keys and isinstance(value, (int, float, str))
    }
