"""Natural-language parser for data-analysis requests."""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from shared_kernel.infrastructure.llm_handler import llm_manager
from yield_report.core.business_time import effective_report_end_date
from yield_report.core.query_parser import REPORT_TYPE_META, ReportType

logger = logging.getLogger(__name__)


class AnalysisQueryRequest(BaseModel):
    """Structured representation of a user's data-analysis request."""

    model_config = ConfigDict(populate_by_name=True)

    source_file_type: ReportType | None = Field(
        default=None,
        validation_alias=AliasChoices("source_file_type", "report_type"),
        description="Source report/file type that should provide the analysis data.",
    )
    file_keywords: list[str] = Field(
        default_factory=list,
        description="Keywords that should appear in the local file name.",
    )
    product_models: list[str] | None = Field(
        default=None,
        description="Product model filters. Use [] when the user explicitly requests all models.",
    )
    start_date: str | None = Field(
        default=None,
        description="Start date in YYYY-MM-DD format.",
    )
    end_date: str | None = Field(
        default=None,
        description="End date in YYYY-MM-DD format.",
    )
    target_metrics: list[str] = Field(
        default_factory=list,
        description="Metrics the user wants to analyse, such as CT yield or daily yield.",
    )
    filter_conditions: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional filters extracted from the request.",
    )
    analysis_logic: str = Field(
        default="",
        description="The requested analysis method, such as trend, comparison, ranking, or summary.",
    )
    user_intent: str = Field(
        default="",
        description="Short natural-language summary of the user's intent.",
    )
    uncertainty_notes: str | None = Field(
        default=None,
        description="Notes about ambiguous or inferred fields.",
    )

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date_format(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            datetime.strptime(value, "%Y-%m-%d")
            return value
        except ValueError as exc:
            raise ValueError(f"Invalid date format: {value}; expected YYYY-MM-DD") from exc

    @field_validator("target_metrics", mode="before")
    @classmethod
    def normalize_target_metrics(cls, value: Any) -> list[str]:
        if value is None:
            return []
        return value

    @field_validator("analysis_logic", "user_intent", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> str:
        if value is None:
            return ""
        return value


class AnalysisQueryParserError(Exception):
    """Raised when analysis query parsing fails."""


def build_heuristic_analysis_request(
    user_input: str,
    today: date | None = None,
) -> AnalysisQueryRequest | None:
    """Build a conservative fallback request for common yield-analysis phrasing.

    The LLM parser remains the primary path. This fallback only covers narrow,
    high-confidence project phrases so local smoke tests and UI demos are not
    blocked by transient LLM connectivity.
    """
    text = user_input.strip()
    if not text:
        return None

    text_upper = text.upper()
    product_models = sorted(set(re.findall(r"(?<![A-Z0-9])[A-Z]\d{3,}[A-Z0-9]*", text_upper)))
    is_yield = "良率" in text
    is_ct_yield = "CT" in text_upper and is_yield
    is_trend = any(keyword in text for keyword in ["趋势", "变化", "波动"])
    is_recent_week = any(keyword in text for keyword in ["近一周", "最近一周", "过去一周", "一周"])

    if not (is_yield and is_trend):
        return None

    current_day = today or effective_report_end_date()
    start_date = current_day - timedelta(days=6) if is_recent_week else None
    target_metrics = ["日度良率"]
    file_keywords = ["月周天", "良率"]
    if is_ct_yield:
        target_metrics.insert(0, "CT良率")
        file_keywords.append("CT")

    return AnalysisQueryRequest(
        source_file_type=ReportType.DAILY_YIELD,
        file_keywords=file_keywords,
        product_models=product_models or None,
        start_date=start_date.isoformat() if start_date else None,
        end_date=current_day.isoformat() if is_recent_week else None,
        target_metrics=target_metrics,
        filter_conditions={"product_model": product_models[0]} if product_models else {},
        analysis_logic="趋势分析",
        user_intent=(
            f"分析{','.join(product_models) if product_models else ''}"
            f"{'日度CT良率' if is_ct_yield else '日度良率'}变化趋势"
        ),
        uncertainty_notes="LLM解析不可用时由项目内启发式规则生成，请在结果中核对。",
    )


ANALYSIS_QUERY_SYSTEM_PROMPT = """你是良率日报项目的数据分析需求解析助手。请把用户的自然语言分析需求转换为结构化 JSON。

## 可用源文件
{source_files}

## 解析规则
- source_file_type: 从可用源文件中选择最可能的数据来源；无法判断时填 null。
- 当用户要求“日度良率、月周天、良率变化趋势、CT良率趋势”时，通常优先选择 daily_yield。
- 当用户要求“批次良率、批次汇总、按批次”时，通常优先选择 batch_yield；默认开始日期为今天往前 90 天，默认结束日期为今天，上午 10 点前为昨日。
- ct_exception 只表示“CT良率异常波动管理表”，适合异常记录/闭环管理查询，不是通用的日度良率趋势数据源。
- file_keywords: 提取可用于本地文件名匹配的关键词，例如“月周天”“批次”“CT异常”“目标拆解”“Gap模板”。
- product_models: 提取产品型号，例如 ["M678"]；明确说全部型号时使用 []；未提及时填 null。
- start_date/end_date: 所有相对日期都按当前日期换算成 YYYY-MM-DD。
- 日度良率的默认结束日期遵循 10 点规则：上午 10 点前仍截止昨日，10 点后截止今天。
- target_metrics: 提取目标指标，例如 ["CT良率", "日度良率"]。
- filter_conditions: 放入产品、时间、站点、工序、厂别等筛选条件。
- analysis_logic: 提取分析方法，例如“趋势分析”“对比分析”“TopN”“异常归因”“汇总”。
- user_intent: 用一句中文概括用户要完成的分析。
- uncertainty_notes: 对任何不确定推断做简短说明；没有则为 null。

## 当前日期
{today_date}

## 输出格式
只输出合法 JSON，不要包含 Markdown 代码块:
{{
  "source_file_type": "daily_yield",
  "file_keywords": ["月周天", "良率"],
  "product_models": ["M678"],
  "start_date": "2026-05-25",
  "end_date": "2026-06-01",
  "target_metrics": ["CT良率"],
  "filter_conditions": {{"product_model": "M678"}},
  "analysis_logic": "趋势分析",
  "user_intent": "分析 M678 近一周日度 CT 良率变化趋势",
  "uncertainty_notes": null
}}
"""


class AnalysisQueryParser:
    """Parse data-analysis needs into an AnalysisQueryRequest."""

    def __init__(self, provider: str | None = None) -> None:
        self._provider = provider

    def parse(
        self,
        user_input: str,
        provider: str | None = None,
    ) -> AnalysisQueryRequest:
        effective_provider = provider or self._provider or "deepseek"
        prompt = ANALYSIS_QUERY_SYSTEM_PROMPT.format(
            source_files=self._format_source_files(),
            today_date=date.today().isoformat(),
        )

        try:
            response_text = llm_manager.chat(
                provider=effective_provider,
                messages=[{"role": "user", "content": user_input}],
                system_prompt=prompt,
                temperature=0.1,
                max_tokens=1536,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            raise AnalysisQueryParserError(f"LLM call failed: {exc}") from exc

        if not response_text or not response_text.strip():
            raise AnalysisQueryParserError("LLM returned an empty response")

        cleaned = self._clean_response(response_text)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise AnalysisQueryParserError(
                f"LLM returned invalid JSON: {exc}; raw={response_text[:200]}"
            ) from exc

        data = self._apply_heuristic_fallbacks(data, user_input)
        try:
            request = AnalysisQueryRequest(**data)
        except Exception as exc:
            raise AnalysisQueryParserError(f"Parsed data validation failed: {exc}") from exc

        logger.info(
            "Analysis query parsed: source=%s, models=%s, metrics=%s",
            request.source_file_type,
            request.product_models,
            request.target_metrics,
        )
        return request

    @staticmethod
    def _clean_response(text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1 :]
            if text.endswith("```"):
                text = text[:-3].strip()
        if text.startswith("json"):
            text = text[4:].strip()
        return text.strip()

    @staticmethod
    def _apply_heuristic_fallbacks(data: Any, user_input: str) -> dict[str, Any]:
        if not isinstance(data, dict):
            return data
        heuristic = build_heuristic_analysis_request(user_input)
        if heuristic is None:
            return data

        fallback = heuristic.model_dump(mode="json")
        merged = dict(data)
        for key, value in fallback.items():
            current = merged.get(key)
            if current is None or current == "" or current == [] or current == {}:
                merged[key] = value
        return merged

    @staticmethod
    def _format_source_files() -> str:
        lines: list[str] = []
        for report_type, meta in REPORT_TYPE_META.items():
            lines.append(
                f"- {report_type.value}: {meta['name']}；{meta['description']}；来源：{meta['source']}"
            )
        return "\n".join(lines)
