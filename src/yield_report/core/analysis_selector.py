"""analysis_selector.py - 数据分析策略选择器 (Core 层)

本模块实现了基于 LLM 的数据分析策略判定机制。

核心逻辑:
    用户提交自然语言分析需求 → LLM 评估查询的"结构清晰度"
    → 若查询可明确翻译为 pandas/数据操作 → 走代码执行路径
    → 若查询模糊、需要推理/判断/总结 → 走 LLM 直接分析路径

判定维度:
    1. 可操作性: 是否能用数据操作语言(pandas/SQL)清晰表达
    2. 确定性: 输出是否有明确的量化定义(而非需要主观判断)
    3. 复杂度: 是否需要多步推理、上下文理解或领域知识

使用方式:
    selector = AnalysisStrategySelector()
    decision = selector.decide(user_query="分析M678近一个月日度良率趋势", schema=...)
    # decision.strategy == AnalysisStrategy.CODE
    # decision.reasoning == "查询清晰:筛选M678+按日聚合+计算趋势"
"""

from __future__ import annotations

import json
import logging
from enum import StrEnum

from pydantic import BaseModel, Field

from shared_kernel.infrastructure.llm_handler import llm_manager

logger = logging.getLogger(__name__)


class AnalysisStrategy(StrEnum):
    """分析策略枚举"""

    CODE = "code"
    """使用代码执行路径: 查询明确、可翻译为 pandas 操作"""

    LLM_DIRECT = "llm_direct"
    """使用 LLM 直接分析路径: 查询模糊、需要推理判断"""


class StrategyDecision(BaseModel):
    """策略判定结果"""

    strategy: AnalysisStrategy = Field(
        description="推荐的分析策略: code(代码执行) 或 llm_direct(LLM直接分析)"
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="判定置信度 (0.0-1.0)",
    )
    reasoning: str = Field(
        default="",
        description="判定理由简述",
    )
    suggested_code_approach: str | None = Field(
        default=None,
        description="如果策略为 code，给出建议的代码实现思路",
    )
    suggested_llm_approach: str | None = Field(
        default=None,
        description="如果策略为 llm_direct，给出建议的分析角度",
    )


SELECTOR_SYSTEM_PROMPT = """你是一个数据分析策略判定专家。你的任务是分析用户的数据查询需求，判断应该使用哪种方式来完成分析。

## 两种分析策略

### strategy: "code" - 代码执行路径
适用于: 查询目标明确、可用数据操作语言(pandas/SQL)精确表达的场景。
特征:
- 筛选条件清晰 (如 "产品M678"、"近一个月"、"良率>90%")
- 计算逻辑确定 (如 "按日聚合"、"计算趋势"、"求平均值")
- 输出格式明确 (如 "趋势图"、"汇总表")
- 不涉及主观判断、模糊定义或需要领域知识的复杂推理

### strategy: "llm_direct" - LLM 直接分析路径
适用于: 查询模糊、需要推理/判断/总结的场景。
特征:
- 需要"分析原因"、"判断异常"、"给出建议"等主观推理
- 查询目标不明确 (如 "看看数据有什么问题")
- 需要多维度交叉推理或领域知识
- 无法用简单的筛选+聚合+计算表达

## 判定规则

1. 如果查询包含"变化趋势"、"对比"、"筛选"、"排序"、"统计"等可操作的明确指令 → code
2. 如果查询包含"为什么"、"原因分析"、"异常判断"、"建议" → llm_direct
3. 如果同时包含两者，优先选择更能保证准确性的策略:
   - 数据计算部分 → code
   - 推理判断部分 → llm_direct
   - 此时 strategy 设为 "code" (先代码计算，再 LLM 解读)
4. 置信度: code 路径通常置信度更高(0.7-0.95)，llm_direct 适中(0.5-0.8)

## 输出格式

必须只输出一个合法的 JSON 对象:
{
    "strategy": "code",
    "confidence": 0.9,
    "reasoning": "查询清晰，可通过 pandas 筛选+聚合实现",
    "suggested_code_approach": "筛选 M678 产品 → 按日期分组 → 计算日均良率 → 绘制趋势",
    "suggested_llm_approach": null
}
"""


class AnalysisStrategySelector:
    """数据分析策略选择器。

    通过 LLM 评估用户查询的"结构清晰度"，决定使用代码执行
    还是 LLM 直接分析。

    判断标准:
        - 可操作性: 是否能用数据操作语言清晰表达
        - 确定性: 输出是否有明确量化定义
        - 复杂度: 是否需要多步推理或领域知识
    """

    def __init__(self, provider: str | None = None) -> None:
        self._provider = provider or "deepseek"

    def decide(
        self,
        user_query: str,
        schema: str = "",
        provider: str | None = None,
    ) -> StrategyDecision:
        """判定用户查询应使用的分析策略。

        Args:
            user_query: 用户的自然语言分析需求
            schema: 数据表的 Schema 信息 (可选，增强判定准确性)
            provider: LLM 供应商

        Returns:
            StrategyDecision: 策略判定结果

        Raises:
            RuntimeError: LLM 调用失败或返回无效数据
        """
        effective_provider = provider or self._provider

        # 构建用户消息
        user_message = f"用户查询: {user_query}"
        if schema:
            # 截断过长的 schema
            schema_short = schema[:3000] if len(schema) > 3000 else schema
            user_message += f"\n\n数据表 Schema:\n{schema_short}"

        try:
            response_text = llm_manager.chat(
                provider=effective_provider,
                messages=[{"role": "user", "content": user_message}],
                system_prompt=SELECTOR_SYSTEM_PROMPT,
                temperature=0.1,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
        except Exception as e:
            raise RuntimeError(f"策略判定 LLM 调用失败: {e}") from e

        if not response_text or not response_text.strip():
            raise RuntimeError("策略判定 LLM 返回了空响应")

        # 清理并解析
        cleaned = self._clean_response(response_text)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"策略判定返回非法 JSON: {e}\n原始响应: {response_text[:200]}"
            ) from e

        try:
            decision = StrategyDecision(**data)
        except Exception as e:
            raise RuntimeError(f"策略判定结果校验失败: {e}") from e

        logger.info(
            "分析策略判定: strategy=%s, confidence=%.2f, reasoning=%s",
            decision.strategy,
            decision.confidence,
            decision.reasoning,
        )
        return decision

    @staticmethod
    def _clean_response(text: str) -> str:
        """清理 LLM 响应中的代码块标记。"""
        text = text.strip()
        if text.startswith("```"):
            first_nl = text.find("\n")
            if first_nl != -1:
                text = text[first_nl + 1:]
            if text.endswith("```"):
                text = text[:-3].strip()
        if text.startswith("json"):
            text = text[4:].strip()
        return text.strip()
