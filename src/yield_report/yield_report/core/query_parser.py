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
from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from yield_report.shared_kernel.infrastructure.llm_handler import llm_manager

logger = logging.getLogger(__name__)


class ReportType(StrEnum):
    """报表类型枚举"""

    DAILY_YIELD = "daily_yield"
    """V3良率及不良率By月周天汇总报表 - 用于 Gap 计算"""

    BATCH_YIELD = "batch_yield"
    """V3良率及不良率By批次汇总报表 - 用于批次恶化判断"""

    CT_EXCEPTION = "ct_exception"
    """CT异常管理表 - 用于异常搜索"""

    TARGET_DECOMPOSITION = "target_decomposition"
    """良率目标拆解表 - 用于获取良率目标"""

    GAP_TEMPLATE = "gap_template"
    """日良率Gap分析模板 - 提供规则与模板"""


# 报表类型元数据映射
REPORT_TYPE_META: dict[ReportType, dict[str, str]] = {
    ReportType.DAILY_YIELD: {
        "name": "V3良率及不良率By月周天汇总报表",
        "description": "按日月周维度汇总的良率及不良率数据，用于Gap计算",
        "source": "FineReport",
    },
    ReportType.BATCH_YIELD: {
        "name": "V3良率及不良率By批次汇总报表",
        "description": "按批次汇总的良率及不良率数据，用于判断最新批次是否恶化",
        "source": "FineReport",
    },
    ReportType.CT_EXCEPTION: {
        "name": "CT良率异常波动管理表",
        "description": "CT工程不良率异常波动的管理记录表",
        "source": "网络共享路径",
    },
    ReportType.TARGET_DECOMPOSITION: {
        "name": "良率目标拆解表",
        "description": "各产品型号的良率目标值拆解",
        "source": "本地文件",
    },
    ReportType.GAP_TEMPLATE: {
        "name": "日良率Gap分析模板",
        "description": "Gap分析的标准模板",
        "source": "本地文件",
    },
}


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


SYSTEM_PROMPT = """你是一个智能的报表查询解析助手。你的任务是将用户的自然语言查询转换为结构化的 JSON 参数。

## 可用的报表类型

以下是用户可能请求下载的报表类型：

1. **daily_yield** - "V3良率及不良率By月周天汇总报表": 按日月周维度汇总的良率及不良率数据，用于 Gap 计算。数据来源：FineReport。
   - 用户可能说：良率日报、月周天、daily yield、良率报表、V3良率、良率数据
   - 筛选条件: 结束日期(必选)、产品型号(可选)

2. **batch_yield** - "V3良率及不良率By批次汇总报表": 按批次汇总的良率及不良率数据，用于判断最新批次是否恶化。数据来源：FineReport。
   - 用户可能说：批次报表、batch yield、批次良率、按批次
   - 筛选条件: 开始日期(默认三月前月初)、结束日期(默认今天)、产品型号(可选)

3. **ct_exception** - "CT良率异常波动管理表": CT工程不良率异常波动的管理记录。数据来源：网络共享文件。
   - 用户可能说：CT异常、异常管理表、CT良率异常、异常波动

4. **target_decomposition** - "良率目标拆解表": 各产品型号的良率目标值。数据来源：本地文件。
   - 用户可能说：目标拆解、良率目标、target、目标表

5. **gap_template** - "日良率Gap分析模板": Gap分析标准模板。数据来源：本地文件。
   - 用户可能说：Gap模板、分析模板、Gap分析模板

## 参数提取规则

- **report_type**: 根据用户描述推断最可能的报表类型。如果用户说"所有报表"或模糊表述，尝试推断核心需求。
- **start_date**: 从文本中提取具体日期。支持"今天"、"昨天"、"前天"、"上周一"等中文日期表达，以及"2026年5月18日"、"2026-05-18"等格式。一律转换为 YYYY-MM-DD 格式。
- **end_date**: 同上。如果用户只说"今天的报表"，则 end_date 设为今天日期。
- **product_models**: 提取用户明确提到的产品型号。如果用户说"所有型号"、"全部产品"等，设为空列表 []。如果未提及，设为 null。
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

    def __init__(self, provider: str | None = None) -> None:
        """
        Args:
            provider: LLM 供应商 ("deepseek" 或 "gemini")，默认从 config 读取
        """
        self._provider = provider

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
        prompt = SYSTEM_PROMPT.format(today_date=today.isoformat())

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
