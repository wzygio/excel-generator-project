"""test_analysis_selector.py - AnalysisStrategySelector 单元测试"""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest

from yield_report.core.analysis_selector import (
    AnalysisStrategy,
    AnalysisStrategySelector,
    StrategyDecision,
)


class TestStrategyDecisionModel:
    """测试 StrategyDecision Pydantic 模型。"""

    def test_valid_code_decision(self):
        decision = StrategyDecision(
            strategy=AnalysisStrategy.CODE,
            confidence=0.9,
            reasoning="查询清晰",
            suggested_code_approach="筛选+聚合",
        )
        assert decision.strategy == AnalysisStrategy.CODE
        assert decision.confidence == 0.9

    def test_valid_llm_direct_decision(self):
        decision = StrategyDecision(
            strategy=AnalysisStrategy.LLM_DIRECT,
            confidence=0.6,
            reasoning="需要主观判断",
            suggested_llm_approach="分析异常原因",
        )
        assert decision.strategy == AnalysisStrategy.LLM_DIRECT

    def test_confidence_bounds(self):
        with pytest.raises(Exception):
            StrategyDecision(strategy=AnalysisStrategy.CODE, confidence=1.5)
        with pytest.raises(Exception):
            StrategyDecision(strategy=AnalysisStrategy.CODE, confidence=-0.1)

    def test_default_values(self):
        decision = StrategyDecision(strategy=AnalysisStrategy.CODE)
        assert decision.confidence == 0.5
        assert decision.reasoning == ""
        assert decision.suggested_code_approach is None
        assert decision.suggested_llm_approach is None


class TestAnalysisStrategySelector:
    """测试分析策略选择器。"""

    def test_decide_code_strategy_for_clear_query(self, monkeypatch):
        """清晰的查询应判定为 code 策略。"""
        mock_response = json.dumps({
            "strategy": "code",
            "confidence": 0.9,
            "reasoning": "查询清晰，可翻译为 pandas 筛选+聚合",
            "suggested_code_approach": "筛选 M678 → 按日期分组 → 计算日均良率",
            "suggested_llm_approach": None,
        })

        def mock_chat(**kwargs):
            return mock_response

        monkeypatch.setattr(
            "yield_report.core.analysis_selector.llm_manager",
            MagicMock(chat=mock_chat),
        )

        selector = AnalysisStrategySelector()
        decision = selector.decide(
            user_query="分析M678近一个月日度良率变化趋势",
            schema="列: 日期, 产品, 良率",
        )

        assert decision.strategy == AnalysisStrategy.CODE
        assert decision.confidence == 0.9
        assert "清晰" in decision.reasoning

    def test_decide_llm_direct_for_fuzzy_query(self, monkeypatch):
        """模糊的分析需求应判定为 llm_direct 策略。"""
        mock_response = json.dumps({
            "strategy": "llm_direct",
            "confidence": 0.65,
            "reasoning": "需要分析异常原因，涉及主观判断",
            "suggested_code_approach": None,
            "suggested_llm_approach": "逐一排查异常批次的原因",
        })

        def mock_chat(**kwargs):
            return mock_response

        monkeypatch.setattr(
            "yield_report.core.analysis_selector.llm_manager",
            MagicMock(chat=mock_chat),
        )

        selector = AnalysisStrategySelector()
        decision = selector.decide(
            user_query="为什么最近良率下降了？帮我分析原因",
        )

        assert decision.strategy == AnalysisStrategy.LLM_DIRECT
        assert decision.confidence == 0.65

    def test_decide_handles_invalid_json(self, monkeypatch):
        """LLM 返回非法 JSON 时应抛出异常。"""
        def mock_chat(**kwargs):
            return "这不是 JSON"

        monkeypatch.setattr(
            "yield_report.core.analysis_selector.llm_manager",
            MagicMock(chat=mock_chat),
        )

        selector = AnalysisStrategySelector()
        with pytest.raises(RuntimeError, match="非法 JSON"):
            selector.decide(user_query="测试查询")

    def test_decide_handles_empty_response(self, monkeypatch):
        """LLM 返回空响应时应抛出异常。"""
        def mock_chat(**kwargs):
            return ""

        monkeypatch.setattr(
            "yield_report.core.analysis_selector.llm_manager",
            MagicMock(chat=mock_chat),
        )

        selector = AnalysisStrategySelector()
        with pytest.raises(RuntimeError, match="空响应"):
            selector.decide(user_query="测试查询")

    def test_decide_with_schema_context(self, monkeypatch):
        """带 Schema 的查询应有更准确判定。"""
        mock_response = json.dumps({
            "strategy": "code",
            "confidence": 0.95,
            "reasoning": "Schema显示日期/产品/良率列，可直接操作",
            "suggested_code_approach": "groupby+mean",
            "suggested_llm_approach": None,
        })

        def mock_chat(**kwargs):
            # 验证 schema 被传入
            user_msg = kwargs.get("messages", [{}])[0].get("content", "")
            assert "日期" in user_msg or "Schema" in user_msg
            return mock_response

        monkeypatch.setattr(
            "yield_report.core.analysis_selector.llm_manager",
            MagicMock(chat=mock_chat),
        )

        selector = AnalysisStrategySelector()
        decision = selector.decide(
            user_query="计算日均良率",
            schema="| 日期 | 产品 | 良率 |",
        )
        assert decision.strategy == AnalysisStrategy.CODE

    def test_clean_response_removes_markdown(self):
        """测试响应清理功能。"""
        selector = AnalysisStrategySelector()
        result = selector._clean_response('```json\n{"strategy": "code"}\n```')
        assert result == '{"strategy": "code"}'

    def test_clean_response_strips_whitespace(self):
        selector = AnalysisStrategySelector()
        result = selector._clean_response('  {"a": 1}  ')
        assert result == '{"a": 1}'
