"""
query_parser.py: 自然语言查询解析器 (Core 层)

本模块实现了基于 LLM 的结构化参数提取功能。
用户在 UI 中输入自然语言查询（如 "帮我下载今天的V3良率报表"），
本模块将其转化为结构化的 ReportQueryRequest。

关键技术选型:
- 不使用 LangChain，直接使用 LLMManager + Pydantic 模型
- 采用 JSON Mode (response_format) 确保 LLM 输出合法 JSON
- 输出通过 Pydantic V2 模型进行强类型校验

使用方式:
    parser = QueryParser()
    request = parser.parse("帮我下载今天的V3良率报表")
    # request.report_type == ReportType.DAILY_YIELD
    # request.end_date == "2026-05-18"
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator, Mapping
from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from yield_report.shared_kernel.config import ConfigLoader
from yield_report.shared_kernel.config_model import SourceFileConfig
from yield_report.shared_kernel.infrastructure.llm_handler import llm_manager

logger = logging.getLogger(__name__)


class ReportType(StrEnum):
    """报表类型枚举"""

    DAILY_YIELD = "daily_yield"
    """Daily/weekly/monthly yield source used for Gap analysis."""

    BATCH_YIELD = "batch_yield"
    """Batch-level yield source used for degradation analysis."""

    CT_EXCEPTION = "ct_exception"
    """CT异常管理表 - 用于异常搜索"""

    TARGET_DECOMPOSITION = "target_decomposition"
    """良率目标拆解表 - 用于获取良率目标"""

    GAP_TEMPLATE = "gap_template"
    """日良率Gap分析模板 - 提供规则与模板"""


def build_report_type_meta(
    source_files: Mapping[str, SourceFileConfig] | None = None,
) -> dict[ReportType, dict[str, str]]:
    """Build the legacy report metadata view from validated source settings."""
    catalog = source_files if source_files is not None else ConfigLoader().get().source_files
    metadata: dict[ReportType, dict[str, str]] = {}
    for report_type in ReportType:
        source = catalog.get(report_type.value)
        if source is None or not source.description.strip():
            raise ValueError(f"source_files.{report_type.value}.description is not configured")
        metadata[report_type] = {
            "name": source.description,
            "description": source.purpose,
            "source": source.source,
        }
    return metadata


class _ConfiguredReportTypeMeta(Mapping[ReportType, dict[str, str]]):
    """Lazy compatibility mapping backed by the current validated config."""

    def _data(self) -> dict[ReportType, dict[str, str]]:
        return build_report_type_meta()

    def __getitem__(self, key: ReportType) -> dict[str, str]:
        return self._data()[key]

    def __iter__(self) -> Iterator[ReportType]:
        return iter(self._data())

    def __len__(self) -> int:
        return len(self._data())


REPORT_TYPE_META: Mapping[ReportType, dict[str, str]] = _ConfiguredReportTypeMeta()


def _format_report_types(source_files: Mapping[str, SourceFileConfig]) -> str:
    lines: list[str] = []
    for index, report_type in enumerate(ReportType, start=1):
        source = source_files.get(report_type.value)
        if source is None or not source.description.strip():
            raise ValueError(f"source_files.{report_type.value}.description is not configured")
        lines.append(
            f'{index}. **{report_type.value}** - "{source.description}": '
            f"{source.purpose}。数据来源：{source.source}。"
        )
        if source.aliases:
            lines.append(f"   - 用户可能说：{'、'.join(source.aliases)}")
        if source.filters:
            lines.append(f"   - 筛选条件：{'、'.join(source.filters)}")
        lines.extend(f"   - {guidance}" for guidance in source.query_guidance)
    return "\n".join(lines)


class ReportQueryRequest(BaseModel):
    """
    报告查询请求 - LLM 结构化输出的目标模型。

    所有字段均为 Optional，LLM 可从自然语言中提取其中部分或全部。
    """

    report_type: ReportType | None = Field(
        default=None,
        description="用户要下载的报表类型。如果用户未指定，设为 null 并标记为不确定。",
    )
    start_date: str | None = Field(
        default=None,
        description="开始日期 (YYYY-MM-DD 格式)。适用于批次报表等需要时间范围的查询。",
    )
    end_date: str | None = Field(
        default=None,
        description="结束日期 (YYYY-MM-DD 格式)。默认为今天。",
    )
    product_models: list[str] | None = Field(
        default=None,
        description="产品型号列表，如 ['3TED01', '3TED02']。如果用户说'所有型号'则传空列表。",
    )
    month_count: int | None = Field(
        default=None,
        description="月周天汇总报表的月数筛选，例如最近三个月时为 3。",
    )
    user_intent: str = Field(
        default="",
        description="用户意图的简短描述，用于确认和展示。",
    )
    uncertainty_notes: str | None = Field(
        default=None,
        description="如果对某些参数不确定，在此说明。",
    )

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date_format(cls, v: str | None) -> str | None:
        """验证日期格式是否为 YYYY-MM-DD。"""
        if v is None:
            return None
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError(f"日期格式无效: '{v}'，应为 YYYY-MM-DD")


class QueryParserError(Exception):
    """查询解析失败"""


SYSTEM_PROMPT_TEMPLATE = """你是一个智能的报表查询解析助手。你的任务是将用户的自然语言查询转换为结构化的 JSON 参数。

## 可用的报表类型

以下是用户可能请求下载的报表类型：

{report_types}

## 参数提取规则

- **report_type**: 根据用户描述推断最可能的报表类型。如果用户说"所有报表"或模糊表述，尝试推断核心需求。
- **start_date**: 从文本中提取具体日期。支持"今天"、"昨天"、"前天"、"上周一"等中文日期表达，以及"2026年5月18日"、"2026-05-18"等格式。一律转换为 YYYY-MM-DD 格式。
- **end_date**: 同上。如果用户只说"今天的报表"，10点后设为今天日期；上午10点前设为昨日日期。
- **product_models**: 提取用户明确提到的产品型号。如果用户说"所有型号"、"全部产品"等，设为空列表 []。如果未提及，设为 null。
- **month_count**: 当用户要求"最近三个月/近3个月/月数3"等月周天汇总跨度时，提取为整数 3；否则设为 null。
- **user_intent**: 用一句话概括用户想做什么。
- **uncertainty_notes**: 如果对任何字段不确定（如无法确定 report_type），在此说明。

## 当前日期

今天的日期是: {today_date}

## 输出格式

你必须只输出一个合法的 JSON 对象（不要包含 ```json 代码块标记），格式如下：
{{
    "report_type": "daily_yield",
    "start_date": null,
    "end_date": "2026-05-18",
    "product_models": null,
    "month_count": null,
    "user_intent": "用户意图的简短描述",
    "uncertainty_notes": null
}}
"""


class QueryParser:
    """
    自然语言查询解析器。

    将用户的自然语言输入通过 LLM 转换为结构化的 ReportQueryRequest。
    使用 LLMManager 进行 LLM 调用。
    """

    def __init__(
        self,
        provider: str | None = None,
        source_files: Mapping[str, SourceFileConfig] | None = None,
    ) -> None:
        """
        Args:
            provider: LLM 供应商 ("deepseek" 或 "gemini")，默认从 config 读取
        """
        self._provider = provider
        self._source_files = dict(
            source_files if source_files is not None else ConfigLoader().get().source_files
        )

    def parse(
        self,
        user_input: str,
        provider: str | None = None,
    ) -> ReportQueryRequest:
        """
        解析用户的自然语言查询。

        Args:
            user_input: 用户的自然语言输入，如 "帮我下载今天的V3良率报表"
            provider: 可覆盖 LLM 供应商

        Returns:
            ReportQueryRequest: 结构化查询请求

        Raises:
            QueryParserError: 解析失败
        """
        effective_provider = provider or self._provider or "deepseek"

        # 构建带有日期上下文的 prompt
        today = date.today()
        prompt = SYSTEM_PROMPT_TEMPLATE.format(
            report_types=_format_report_types(self._source_files),
            today_date=today.isoformat(),
        )

        try:
            response_text = llm_manager.chat(
                provider=effective_provider,
                messages=[{"role": "user", "content": user_input}],
                system_prompt=prompt,
                temperature=0.1,  # 低温度以提高确定性
                max_tokens=1024,
                # DeepSeek 支持 JSON 模式
                response_format={"type": "json_object"},
            )
        except Exception as e:
            raise QueryParserError(f"LLM 调用失败: {e}") from e

        if not response_text or not response_text.strip():
            raise QueryParserError("LLM 返回了空响应")

        # 清理响应文本（移除可能的代码块标记）
        cleaned = self._clean_response(response_text)

        # 解析 JSON
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise QueryParserError(
                f"LLM 返回了非法的 JSON: {e}\n原始响应: {response_text[:200]}"
            ) from e

        # 校验并构造 Pydantic 模型
        try:
            request = ReportQueryRequest(**data)
        except Exception as e:
            raise QueryParserError(f"参数校验失败: {e}\n解析数据: {data}") from e

        logger.info(
            "查询解析完成: report_type=%s, end_date=%s, models=%s",
            request.report_type,
            request.end_date,
            request.product_models,
        )
        return request

    # ================================================================
    # 辅助方法
    # ================================================================

    @staticmethod
    def _clean_response(text: str) -> str:
        """清理 LLM 响应文本，移除代码块标记等。"""
        text = text.strip()

        # 移除 ```json ... ``` 代码块
        if text.startswith("```"):
            # 找到第一个换行后的内容和最后一个 ```
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1 :]
            # 移除末尾的 ```
            if text.endswith("```"):
                text = text[:-3].strip()

        # 移除可能的语言标记行
        if text.startswith("json"):
            text = text[4:].strip()

        return text.strip()
