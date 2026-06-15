"""TaskSpec builder for yield-report Agent Workbench runs."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from yield_report.agent.run_store import RunPaths, RunStore
from yield_report.agent.spec_model import SkillCall, TaskSpec
from yield_report.agent.spec_validation import (
    SpecValidationIssue,
    validate_task_spec,
)

DEFAULT_SECTIONS = ["gap", "trend", "known_exception", "new_exception"]
DEFAULT_TEMPLATE_REF = "docs/project_files/V3良率日报每日异常填报表.xlsx"
DEFAULT_DAILY_YIELD_FILE_NAME = "V3良率及不良率By月周天汇总报表"
PRODUCT_MODEL_PATTERN = re.compile(r"(?<![A-Z0-9])[A-Z]\d{3,4}(?![A-Z0-9])", re.IGNORECASE)
LOCAL_SOURCE_FILES = {
    "spotfire": "resources/project_files/spotfire.xlsx",
    "daily_yield": "resources/V3良率及不良率By月周天汇总报表.xlsx",
    "target_decomposition": "resources/2026年良率目标拆解-1017版V05 - 无公式版.xlsx",
    "ct_exception": "resources/CT良率异常波动管理表.xlsx",
    "code_mapping": "resources/大数据值班当日新增不良HL模板.xlsx",
}


class SpecBuildRequest(BaseModel):
    """Request for turning a natural-language daily-report goal into a TaskSpec."""

    user_goal: str
    run_id: str | None = None
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
    """Build executable TaskSpecs with LLM conversion and code validation fallback."""

    def __init__(
        self,
        store: RunStore | None = None,
        today: date | None = None,
        llm_converter: LlmConverter | None = None,
    ) -> None:
        self.store = store or RunStore()
        self.today = today or date.today()
        self._llm_converter = llm_converter

    def build(self, request: SpecBuildRequest) -> SpecBuildResult:
        """Create a run directory, write ``spec.yaml``, and return the TaskSpec."""
        paths = self.store.create_run(request.run_id)
        warnings: list[str] = []
        validation_issues: list[SpecValidationIssue] = []
        spec = self._try_build_with_llm(request, paths, warnings)
        if spec is None:
            spec = self._build_rule_based(request, paths, warnings)

        validation = validate_task_spec(
            spec,
            registered_skills={"report_download", "data_analysis", "daily_report"},
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

    def _try_build_with_llm(
        self,
        request: SpecBuildRequest,
        paths: RunPaths,
        warnings: list[str],
    ) -> TaskSpec | None:
        mode = request.builder_mode.lower().strip()
        if mode not in {"llm", "auto_llm"}:
            return None

        try:
            raw = self._convert_with_llm(request)
            spec = _parse_llm_spec(raw)
        except Exception as exc:
            warnings.append(f"LLM Spec 转换失败，已回退到规则构建: {exc}")
            return None

        spec.run_id = paths.run_id
        if spec.status in {"draft", ""}:
            spec.status = "ready"
        return spec

    def _convert_with_llm(self, request: SpecBuildRequest) -> dict[str, Any] | str:
        if self._llm_converter is not None:
            return self._llm_converter(request)

        from shared_kernel.infrastructure.llm_handler import llm_manager

        system_prompt = (
            "你是良率日报 Agent Workbench 的 Spec Builder。"
            "请把用户自然语言需求转换为 TaskSpec JSON。"
            "只输出 JSON，不输出解释。"
            "Skill 只能使用 report_download、data_analysis、daily_report。"
            "memory.reuse_policy 必须为 confirmed_only。"
        )
        return llm_manager.chat(
            messages=[{"role": "user", "content": request.user_goal}],
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
        sections = _normalize_sections(request.sections) or DEFAULT_SECTIONS
        if not product_models and not request.allow_all_products:
            warnings.append("缺少产品型号，需要用户确认。")

        if _is_analysis_goal(request.user_goal):
            return self._build_analysis_spec(
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
                "codex_is_agent_core": True,
                "prefer_existing_tools": True,
                "require_user_confirmation_for_pending_memory": True,
            },
            inputs=self._build_inputs(report_date, product_models),
            workflow=self._build_workflow(report_date, product_models, sections),
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
        date_range = {
            "start": (parsed_date - timedelta(days=6)).isoformat(),
            "end": report_date,
        }
        question = request.user_goal.strip()
        metrics = _infer_metrics(question)
        return TaskSpec(
            run_id=paths.run_id,
            status="needs_confirmation" if warnings else "ready",
            user_goal=question,
            constraints={
                "codex_is_agent_core": True,
                "prefer_existing_tools": True,
                "runtime": "python_with_pi_fallback",
                "pi_runtime_allowed": True,
                "require_user_confirmation_for_pending_memory": True,
            },
            inputs={
                "report_date": report_date,
                "product_models": list(product_models),
                "date_range": date_range,
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
                    {"alias": "daily_yield", "path": LOCAL_SOURCE_FILES["daily_yield"]},
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
                for alias, path in LOCAL_SOURCE_FILES.items()
            ],
        }

    @staticmethod
    def _build_workflow(
        report_date: str,
        product_models: list[str],
        sections: list[str],
    ) -> list[SkillCall]:
        return [
            SkillCall(
                id="prepare_daily_report_facts",
                skill="data_analysis",
                input={
                    "analysis_kind": "daily_report",
                    "report_date": report_date,
                    "sections": sections,
                    "source_files": {
                        alias: path
                        for alias, path in LOCAL_SOURCE_FILES.items()
                        if alias != "spotfire"
                    },
                    "product_models": product_models,
                    "question": "生成良率日报所需的结构化分析事实",
                    "analysis_intent": "daily_report",
                },
                save_as="daily_report_facts",
            ),
            SkillCall(
                id="generate_daily_report",
                skill="daily_report",
                depends_on=["prepare_daily_report_facts"],
                input={
                    "report_date": report_date,
                    "template_ref": DEFAULT_TEMPLATE_REF,
                    "product_models": product_models,
                    "source_files": LOCAL_SOURCE_FILES,
                    "sections": sections,
                    "analysis_results": ["daily_report_facts"],
                    "output_name": "daily_report_output.xlsx",
                    "emit_intermediate_artifacts": True,
                },
                save_as="daily_report_file",
            ),
        ]


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


def _normalize_sections(sections: list[str]) -> list[str]:
    normalized = [item.strip() for item in sections if item and item.strip()]
    return list(dict.fromkeys(normalized))


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


def _infer_metrics(goal: str) -> list[str]:
    metrics: list[str] = []
    if "CT" in goal.upper():
        metrics.append("CT良率")
    if "MVI" in goal.upper():
        metrics.append("MVI产出占比")
    if any(keyword in goal for keyword in ["良率", "yield", "Yield"]):
        metrics.append("日度良率")
    return list(dict.fromkeys(metrics)) or ["日度良率"]


def _parse_llm_spec(raw: dict[str, Any] | str) -> TaskSpec:
    if isinstance(raw, dict):
        return TaskSpec(**raw)
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json|yaml)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return TaskSpec(**json.loads(text))
    except json.JSONDecodeError as exc:
        raise ValueError("LLM Spec output is not valid JSON") from exc
