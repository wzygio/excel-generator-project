"""TaskSpec builder for yield-report Agent Workbench runs."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from shared_kernel.config import ConfigLoader
from shared_kernel.config_model import SourceFileConfig
from yield_report.agent.run_id import RunIdFactory, normalize_capability, normalize_source
from yield_report.agent.run_store import RunPaths, RunStore
from yield_report.agent.spec_graph import LangGraphSpecAgent
from yield_report.agent.spec_model import SkillCall, TaskSpec
from yield_report.agent.spec_validation import (
    SpecValidationIssue,
    validate_task_spec,
)
from yield_report.core.analysis_query_parser import (
    infer_analysis_requested_periods,
    infer_analysis_start_date,
    infer_analysis_time_grain,
    metric_for_time_grain,
)

REGISTERED_SKILLS = {"report_download", "data_analysis", "daily_report", "anomaly_monitor"}
RULE_BUILD_CAPABILITIES = {"anomaly-monitor", "daily-report"}
PRODUCT_MODEL_PATTERN = re.compile(r"(?<![A-Z0-9])[A-Z]\d{3,4}(?![A-Z0-9])", re.IGNORECASE)
LOCAL_SOURCE_ALIASES = (
    "spotfire",
    "daily_yield",
    "target_decomposition",
    "ct_exception",
    "code_mapping",
)
ANOMALY_SOURCE_ALIASES = {
    "data_source_dir": "data_source_dir",
    "spotfire": "anomaly_spotfire",
}


class SpecBuildRequest(BaseModel):
    """Request for turning an Agent trigger and user goal into a TaskSpec."""

    user_goal: str
    run_id: str | None = None
    source: str = "agent"
    capability: str | None = None
    fixed_flow: bool = False
    report_date: str | None = None
    product_models: list[str] | None = None
    sections: list[str] = Field(default_factory=list)
    allow_all_products: bool = True
    builder_mode: str = "auto"


class SpecBuildResult(BaseModel):
    """Result of a SpecBuilder run."""

    spec: TaskSpec
    paths: RunPaths
    spec_path: Path
    warnings: list[str] = Field(default_factory=list)
    validation_issues: list[SpecValidationIssue] = Field(default_factory=list)


LlmConverter = Callable[[SpecBuildRequest], dict[str, Any] | str]


class SpecBuilder:
    """Build executable TaskSpecs through LangGraph or fixed-flow rule construction."""

    def __init__(
        self,
        store: RunStore | None = None,
        today: date | None = None,
        llm_converter: LlmConverter | None = None,
        clock: Callable[[], datetime] | None = None,
        source_files: Mapping[str, SourceFileConfig] | None = None,
    ) -> None:
        self.store = store or RunStore()
        self.today = today or date.today()
        self._clock = clock or (
            (lambda: datetime.combine(self.today, time.min)) if today is not None else datetime.now
        )
        self._llm_converter = llm_converter
        catalog = source_files if source_files is not None else ConfigLoader().get().source_files
        self._source_files = dict(catalog)
        self._local_source_files = self._configured_source_paths(LOCAL_SOURCE_ALIASES)
        self._anomaly_source_files = {
            runtime_alias: self._source_path(config_alias)
            for runtime_alias, config_alias in ANOMALY_SOURCE_ALIASES.items()
        }

    def build(self, request: SpecBuildRequest) -> SpecBuildResult:
        """Create a run directory, write ``spec.yaml``, and return the TaskSpec."""
        warnings: list[str] = []
        validation_issues: list[SpecValidationIssue] = []
        if self._uses_rule_builder(request):
            capability = normalize_capability(request.capability or "")
            run_id = self._resolve_rule_run_id(request, capability)
            paths = self.store.create_run(run_id)
            spec = self._build_rule_based(request, paths, warnings)
        elif request.fixed_flow:
            capability = normalize_capability(request.capability or "data-analysis")
            run_id = self._resolve_rule_run_id(request, capability)
            paths = self.store.create_run(run_id)
            spec = self._build_disallowed_rule_spec(request, paths, capability)
            warnings.append(
                "规则构建仅允许 anomaly_monitor 和 daily_report 固定业务流程。"
            )
        else:
            agent = LangGraphSpecAgent(
                workspace=self.store.workspace,
                draft_generator=self._generate_langgraph_draft,
                registered_skills=REGISTERED_SKILLS,
                today_clock=self._clock,
            )
            agent_result = agent.build(request)
            spec = agent_result["spec"]
            warnings.extend(agent_result["warnings"])
            validation_issues.extend(agent_result["validation_issues"])
            paths = self.store.create_run(spec.run_id)

        validation = validate_task_spec(
            spec,
            registered_skills=REGISTERED_SKILLS,
        )
        validation_issues.extend(validation.issues)
        if not validation.ok:
            spec.status = "needs_confirmation"
            warnings.extend(issue.message for issue in validation.errors)

        self.store.save_spec(spec, paths.spec_path)
        return SpecBuildResult(
            spec=spec,
            paths=paths,
            spec_path=paths.spec_path,
            warnings=warnings,
            validation_issues=validation_issues,
        )

    def _uses_rule_builder(self, request: SpecBuildRequest) -> bool:
        if not request.fixed_flow:
            return False
        try:
            capability = normalize_capability(request.capability or "")
        except ValueError:
            return False
        return capability in RULE_BUILD_CAPABILITIES

    def _resolve_rule_run_id(self, request: SpecBuildRequest, capability: str) -> str:
        source = normalize_source(request.source)
        if request.run_id:
            RunIdFactory.validate(request.run_id)
            return request.run_id
        return RunIdFactory(clock=self._clock).create(source=source, capability=capability)

    def _generate_langgraph_draft(
        self,
        request: SpecBuildRequest,
        issues: list[SpecValidationIssue],
        context: str,
    ) -> dict[str, Any] | str:
        return self._convert_with_llm(request, issues=issues, context=context)

    def _convert_with_llm(
        self,
        request: SpecBuildRequest,
        issues: list[SpecValidationIssue] | None = None,
        context: str = "",
    ) -> dict[str, Any] | str:
        if self._llm_converter is not None:
            return self._llm_converter(request)

        from shared_kernel.infrastructure.llm_handler import llm_manager

        system_prompt = (
            "你是良率日报 Agent Workbench 的 Spec Builder。"
            "请严格依据项目 Spec 契约、模板和 Skill 输入模型，把用户自然语言需求转换为 TaskSpec JSON。"
            "只输出 JSON，不输出解释。"
            "Skill 只能使用 report_download、data_analysis、daily_report、anomaly_monitor。"
            "memory.reuse_policy 必须为 confirmed_only。"
            "constraints.capability 必须使用代码枚举。"
            "不得生成 run_id，run_id 由 Agent Runtime 生成。"
        )
        repair_text = ""
        if issues:
            repair_text = "\n请修复以下校验问题：\n" + "\n".join(
                f"- {issue.location}: {issue.code} {issue.message}" for issue in issues
            )
        return llm_manager.chat(
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"{context}\n\n用户目标：{request.user_goal}\n"
                        f"source: {request.source}\n"
                        f"capability_hint: {request.capability or ''}"
                        f"{repair_text}"
                    ),
                }
            ],
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=4096,
        )

    def _build_rule_based(
        self,
        request: SpecBuildRequest,
        paths: RunPaths,
        warnings: list[str],
    ) -> TaskSpec:
        report_date = self._resolve_report_date(request)
        product_models = self._resolve_product_models(request)
        if not product_models and not request.allow_all_products:
            warnings.append("缺少产品型号，需要用户确认。")

        capability = normalize_capability(request.capability or "")
        if capability == "anomaly-monitor":
            return self._build_anomaly_monitor_spec(
                request=request,
                paths=paths,
                report_date=report_date,
                product_models=product_models,
                warnings=warnings,
            )

        spec = TaskSpec(
            run_id=paths.run_id,
            status="needs_confirmation" if warnings else "ready",
            user_goal=request.user_goal.strip(),
            constraints={
                "spec_source": normalize_source(request.source),
                "spec_builder": "rule",
                "builder_mode": "rule",
                "capability": "daily-report",
                "codex_is_agent_core": True,
                "codex_in_execution_chain": False,
                "prefer_existing_tools": True,
                "require_user_confirmation_for_pending_memory": True,
                "fixed_flow": True,
            },
            inputs=self._build_inputs(report_date, product_models),
            workflow=self._build_workflow(report_date),
            outputs=_build_outputs(),
            memory={
                "reuse_policy": "confirmed_only",
                "candidate_policy": "record_pending",
                "allowed_record_ids": [],
            },
            trace={
                "level": "step",
                "include_inputs": True,
                "include_outputs": True,
                "include_errors": True,
                "path": "trace.jsonl",
            },
        )
        return spec

    def _build_disallowed_rule_spec(
        self,
        request: SpecBuildRequest,
        paths: RunPaths,
        capability: str,
    ) -> TaskSpec:
        return TaskSpec(
            run_id=paths.run_id,
            status="needs_confirmation",
            user_goal=request.user_goal.strip(),
            constraints={
                "spec_source": normalize_source(request.source),
                "spec_builder": "rule",
                "builder_mode": "rule",
                "capability": capability,
                "codex_in_execution_chain": False,
                "fixed_flow": True,
                "blocked_reason": "rule_builder_capability_not_allowed",
            },
            outputs={"trace": {"required": True, "format": "jsonl"}},
            memory={"reuse_policy": "confirmed_only"},
            trace={"path": "trace.jsonl"},
        )

    def _build_anomaly_monitor_spec(
        self,
        *,
        request: SpecBuildRequest,
        paths: RunPaths,
        report_date: str,
        product_models: list[str],
        warnings: list[str],
    ) -> TaskSpec:
        return TaskSpec(
            run_id=paths.run_id,
            status="needs_confirmation" if warnings else "ready",
            user_goal=request.user_goal.strip(),
            constraints={
                "spec_source": normalize_source(request.source),
                "spec_builder": "rule",
                "builder_mode": "rule",
                "capability": "anomaly-monitor",
                "codex_is_agent_core": True,
                "codex_in_execution_chain": False,
                "prefer_existing_tools": True,
                "require_user_confirmation_for_pending_memory": True,
                "side_effects_disabled_by_default": True,
                "fixed_flow": True,
            },
            inputs={
                "report_date": report_date,
                "product_models": list(product_models),
                "reports": [],
                "local_files": [
                    {"alias": alias, "path": path}
                    for alias, path in self._anomaly_source_files.items()
                ],
            },
            workflow=[
                SkillCall(
                    id="run_anomaly_monitor",
                    skill="anomaly_monitor",
                    input={
                        "report_date": report_date,
                        "product_models": product_models,
                        "mode": "detect",
                        "source_files": self._anomaly_source_files,
                        "write_ledgers": False,
                        "push_notifications": True,
                    },
                    save_as="anomaly_monitor_result",
                )
            ],
            outputs={
                "anomaly_monitor_summary": {"required": True, "format": "markdown"},
                "anomaly_monitor_result": {"required": True, "format": "json"},
                "trace": {"required": True, "format": "jsonl"},
            },
            memory={
                "reuse_policy": "confirmed_only",
                "candidate_policy": "record_pending",
                "allowed_record_ids": [],
            },
            trace={
                "level": "step",
                "include_inputs": True,
                "include_outputs": True,
                "include_errors": True,
                "path": "trace.jsonl",
            },
        )

    def _build_analysis_spec(
        self,
        *,
        request: SpecBuildRequest,
        paths: RunPaths,
        report_date: str,
        product_models: list[str],
        warnings: list[str],
    ) -> TaskSpec:
        parsed_date = date.fromisoformat(report_date)
        question = request.user_goal.strip()
        time_grain = infer_analysis_time_grain(question)
        requested_periods = infer_analysis_requested_periods(question, time_grain)
        start_date = infer_analysis_start_date(parsed_date, time_grain, requested_periods)
        date_range = {
            "start": start_date.isoformat() if start_date else None,
            "end": report_date,
        }
        metrics = _infer_metrics(question, time_grain)
        return TaskSpec(
            run_id=paths.run_id,
            status="needs_confirmation" if warnings else "ready",
            user_goal=question,
            constraints={
                "codex_is_agent_core": True,
                "prefer_existing_tools": True,
                "pi_runtime_allowed": True,
                "require_user_confirmation_for_pending_memory": True,
            },
            inputs={
                "report_date": report_date,
                "product_models": list(product_models),
                "date_range": date_range,
                "analysis": {
                    "time_grain": time_grain,
                    "requested_periods": requested_periods,
                    "metrics": metrics,
                    "analysis_intent": "trend",
                },
                "reports": [
                    {
                        "alias": "daily_yield",
                        "report_type": "daily_yield",
                        "required": False,
                        "filters": {
                            "product_models": list(product_models),
                            "start_date": date_range["start"],
                            "end_date": date_range["end"],
                        },
                    }
                ],
                "local_files": [
                    {"alias": "daily_yield", "path": self._source_path("daily_yield")},
                ],
            },
            workflow=[
                SkillCall(
                    id="analyze_yield_trend",
                    skill="data_analysis",
                    input={
                        "question": question,
                        "product_models": product_models,
                        "time_range": date_range,
                        "metrics": metrics,
                        "time_grain": time_grain,
                        "requested_periods": requested_periods,
                        "analysis_intent": "trend",
                    },
                    save_as="analysis_result",
                )
            ],
            outputs={
                "analysis_summary": {"required": True, "format": "markdown"},
                "trace": {"required": True, "format": "jsonl"},
            },
            memory={
                "reuse_policy": "confirmed_only",
                "candidate_policy": "record_pending",
                "allowed_record_ids": [],
            },
            trace={
                "level": "step",
                "include_inputs": True,
                "include_outputs": True,
                "include_errors": True,
                "path": "trace.jsonl",
            },
        )

    def _build_report_download_spec(
        self,
        *,
        request: SpecBuildRequest,
        paths: RunPaths,
        report_date: str,
        product_models: list[str],
        warnings: list[str],
    ) -> TaskSpec:
        question = request.user_goal.strip()
        report_type = _infer_report_type(question)
        parsed_date = date.fromisoformat(report_date)
        batch_start = (parsed_date - timedelta(days=90)).isoformat()
        month_count = _infer_month_count(question) if report_type == "daily_yield" else None
        start_date = batch_start if report_type == "batch_yield" else None
        report_alias = f"source_{report_type}"
        reports = [
            {
                "alias": report_alias,
                "report_type": report_type,
                "required": True,
                "filters": {
                    "product_models": list(product_models),
                    "start_date": start_date,
                    "end_date": report_date,
                    "month_count": month_count,
                },
            }
        ]
        return TaskSpec(
            run_id=paths.run_id,
            status="needs_confirmation" if warnings else "ready",
            user_goal=question,
            constraints={
                "codex_is_agent_core": True,
                "prefer_existing_tools": True,
                "require_user_confirmation_for_pending_memory": True,
            },
            inputs={
                "report_date": report_date,
                "product_models": list(product_models),
                "date_range": {"start": start_date, "end": report_date},
                "reports": reports,
                "local_files": [
                    {"alias": alias, "path": path}
                    for alias, path in self._local_source_files.items()
                ],
            },
            workflow=[
                SkillCall(
                    id=f"download_{report_type}",
                    skill="report_download",
                    input={
                        "user_query": question,
                        "report_type": report_type,
                        "start_date": start_date,
                        "end_date": report_date,
                        "product_models": product_models,
                        "month_count": month_count,
                    },
                    save_as="source_report_file",
                )
            ],
            outputs={
                "source_report": {"required": True, "format": "xlsx"},
                "trace": {"required": True, "format": "jsonl"},
            },
            memory={
                "reuse_policy": "confirmed_only",
                "candidate_policy": "record_pending",
                "allowed_record_ids": [],
            },
            trace={
                "level": "step",
                "include_inputs": True,
                "include_outputs": True,
                "include_errors": True,
                "path": "trace.jsonl",
            },
        )

    def _resolve_report_date(self, request: SpecBuildRequest) -> str:
        if request.report_date:
            return _parse_goal_date(request.report_date, self.today)
        return _parse_goal_date(request.user_goal, self.today)

    def _resolve_product_models(self, request: SpecBuildRequest) -> list[str]:
        explicit = request.product_models or []
        models = explicit or PRODUCT_MODEL_PATTERN.findall(request.user_goal)
        normalized = [item.upper() for item in models if item and item.strip()]
        return sorted(dict.fromkeys(normalized))

    def _build_inputs(self, report_date: str, product_models: list[str]) -> dict[str, Any]:
        parsed_date = date.fromisoformat(report_date)
        trend_start = (parsed_date - timedelta(days=6)).isoformat()
        batch_start = (parsed_date - timedelta(days=90)).isoformat()
        product_filter = list(product_models)
        return {
            "report_date": report_date,
            "product_models": product_filter,
            "date_range": {"start": trend_start, "end": report_date},
            "reports": [
                {
                    "alias": "daily_yield",
                    "report_type": "daily_yield",
                    "required": True,
                    "filters": {"product_models": product_filter, "end_date": report_date},
                },
                {
                    "alias": "batch_yield",
                    "report_type": "batch_yield",
                    "required": False,
                    "filters": {
                        "product_models": product_filter,
                        "start_date": batch_start,
                        "end_date": report_date,
                    },
                },
                {
                    "alias": "ct_exception",
                    "report_type": "ct_exception",
                    "required": False,
                    "filters": {},
                },
                {
                    "alias": "target_decomposition",
                    "report_type": "target_decomposition",
                    "required": False,
                    "filters": {},
                },
                {
                    "alias": "gap_template",
                    "report_type": "gap_template",
                    "required": False,
                    "filters": {},
                },
            ],
            "local_files": [
                {"alias": alias, "path": path}
                for alias, path in self._local_source_files.items()
            ],
        }

    @staticmethod
    def _build_workflow(report_date: str) -> list[SkillCall]:
        return [
            SkillCall(
                id="generate_daily_report",
                skill="daily_report",
                input={"report_date": report_date},
                save_as="daily_report_file",
            ),
        ]

    def _configured_source_paths(self, aliases: tuple[str, ...]) -> dict[str, str]:
        return {alias: self._source_path(alias) for alias in aliases}

    def _source_path(self, alias: str) -> str:
        source = self._source_files.get(alias)
        if source is None or not source.default_path.strip():
            raise ValueError(f"source_files.{alias}.default_path is not configured")
        return source.default_path


def _parse_goal_date(text: str, today: date) -> str:
    value = str(text or "").strip()
    if not value:
        return today.isoformat()
    normalized = value.replace("/", "-").replace(".", "-")

    match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", normalized)
    if match:
        return _date_from_match(match).isoformat()

    match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", value)
    if match:
        return _date_from_match(match).isoformat()

    if "昨天" in value or "昨日" in value:
        return (today - timedelta(days=1)).isoformat()
    if "明天" in value or "明日" in value:
        return (today + timedelta(days=1)).isoformat()
    return today.isoformat()


def _date_from_parts(parts: tuple[str, str, str]) -> date:
    year, month, day = (int(item) for item in parts)
    return date(year, month, day)


def _date_from_match(match: re.Match[str]) -> date:
    return _date_from_parts((match.group(1), match.group(2), match.group(3)))


def _build_outputs() -> dict[str, Any]:
    return {
        "daily_report": {
            "required": True,
            "format": "xlsx",
            "directory": "outputs",
            "filename_template": "良率日报_{report_date}_{product_models}.xlsx",
        },
        "analysis_summary": {"required": True, "format": "markdown"},
        "trace": {"required": True, "format": "jsonl"},
    }


def _is_analysis_goal(goal: str) -> bool:
    text = goal.strip()
    if not text:
        return False
    has_analysis = any(keyword in text for keyword in ["分析", "趋势", "变化", "波动", "原因"])
    has_report_generation = any(keyword in text for keyword in ["日报", "生成日报", "填报"])
    return has_analysis and not has_report_generation


def _is_report_download_goal(goal: str) -> bool:
    text = goal.strip()
    if not text:
        return False
    if any(keyword in text for keyword in ["生成日报", "填报"]):
        return False
    has_action = any(keyword in text for keyword in ["下载", "查询", "获取", "导出"])
    has_source_report = any(
        keyword in text
        for keyword in [
            "批次",
            "月周天",
            "源表",
            "报表",
            "良率",
            "CT异常",
            "异常管理表",
            "目标表",
            "目标拆解",
            "Gap模板",
        ]
    )
    return has_action and has_source_report


def _infer_report_type(goal: str) -> str:
    text = goal.strip()
    upper_text = text.upper()
    if "批次" in text or "BATCH" in upper_text:
        return "batch_yield"
    if "CT异常" in text or "异常管理表" in text:
        return "ct_exception"
    if "目标拆解" in text or "目标表" in text or "良率目标" in text:
        return "target_decomposition"
    if "GAP模板" in upper_text or "GAP分析模板" in upper_text:
        return "gap_template"
    return "daily_yield"


def _infer_month_count(goal: str) -> int | None:
    text = goal.strip()
    digits = {
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }
    match = re.search(r"(?:最近|近|过去)?(\d+)个?月", text)
    if match:
        return int(match.group(1))
    match = re.search(r"(?:最近|近|过去)?([一二两三四五六七八九十])个?月", text)
    if match:
        return digits.get(match.group(1))
    return None


def _is_anomaly_monitor_goal(goal: str) -> bool:
    text = goal.strip()
    if not text:
        return False
    lowered = text.lower()
    return any(keyword in text for keyword in ["异常监控", "真实异常", "HL通报", "异常识别"]) or (
        "anomaly" in lowered and ("monitor" in lowered or "hl" in lowered)
    )


def _infer_metrics(goal: str, time_grain: str = "daily") -> list[str]:
    metrics: list[str] = []
    if "CT" in goal.upper():
        metrics.append("CT良率")
    if "MVI" in goal.upper():
        metrics.append("MVI产出占比")
    if any(keyword in goal for keyword in ["良率", "yield", "Yield"]):
        metrics.append(metric_for_time_grain(time_grain))
    return list(dict.fromkeys(metrics)) or [metric_for_time_grain(time_grain)]

