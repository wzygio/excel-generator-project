"""Rule-based TaskSpec builder for daily yield-report runs."""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from yield_report.agent.run_store import RunPaths, RunStore
from yield_report.agent.spec_model import SkillCall, TaskSpec

DEFAULT_SECTIONS = ["gap", "trend", "known_exception", "new_exception"]
DEFAULT_TEMPLATE_REF = "docs/project_files/V3良率日报每日异常填报表.xlsx"
PRODUCT_MODEL_PATTERN = re.compile(r"\b[A-Z]\d{3,4}\b", re.IGNORECASE)
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


class SpecBuildResult(BaseModel):
    """Result of a SpecBuilder run."""

    spec: TaskSpec
    paths: RunPaths
    spec_path: Path
    warnings: list[str] = Field(default_factory=list)


class SpecBuilder:
    """Build a minimal executable daily-report TaskSpec without LLM calls."""

    def __init__(self, store: RunStore | None = None, today: date | None = None) -> None:
        self.store = store or RunStore()
        self.today = today or date.today()

    def build(self, request: SpecBuildRequest) -> SpecBuildResult:
        """Create a run directory, write ``spec.yaml``, and return the TaskSpec."""
        paths = self.store.create_run(request.run_id)
        report_date = self._resolve_report_date(request)
        product_models = self._resolve_product_models(request)
        sections = _normalize_sections(request.sections) or DEFAULT_SECTIONS
        warnings: list[str] = []
        if not product_models and not request.allow_all_products:
            warnings.append("缺少产品型号，需要用户确认。")

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
        self.store.save_spec(spec, paths.spec_path)
        return SpecBuildResult(spec=spec, paths=paths, spec_path=paths.spec_path, warnings=warnings)

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
        return _date_from_parts(match.groups()).isoformat()

    match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", value)
    if match:
        return _date_from_parts(match.groups()).isoformat()

    if "昨天" in value or "昨日" in value:
        return (today - timedelta(days=1)).isoformat()
    if "明天" in value or "明日" in value:
        return (today + timedelta(days=1)).isoformat()
    return today.isoformat()


def _date_from_parts(parts: tuple[str, str, str]) -> date:
    year, month, day = (int(item) for item in parts)
    return date(year, month, day)


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
