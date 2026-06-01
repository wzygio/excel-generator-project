from __future__ import annotations

import json
from unittest.mock import patch

from yield_report.core.analysis_query_parser import AnalysisQueryParser
from yield_report.core.query_parser import ReportType


def test_analysis_query_parser_extracts_task2_style_query() -> None:
    response = json.dumps(
        {
            "source_file_type": "daily_yield",
            "file_keywords": ["月周天", "良率"],
            "product_models": ["M678"],
            "start_date": "2026-05-25",
            "end_date": "2026-06-01",
            "target_metrics": ["CT良率", "日度良率"],
            "filter_conditions": {"product_model": "M678"},
            "analysis_logic": "趋势分析",
            "user_intent": "分析 M678 近一周的日度 CT 良率变化趋势",
            "uncertainty_notes": None,
        },
        ensure_ascii=False,
    )

    with patch(
        "yield_report.core.analysis_query_parser.llm_manager.chat",
        return_value=response,
    ):
        result = AnalysisQueryParser(provider="deepseek").parse(
            "请分析M678近一周的日度CT良率变化趋势"
        )

    assert result.source_file_type == ReportType.DAILY_YIELD
    assert result.product_models == ["M678"]
    assert result.start_date == "2026-05-25"
    assert result.end_date == "2026-06-01"
    assert "CT良率" in result.target_metrics
    assert result.analysis_logic == "趋势分析"


def test_analysis_query_parser_cleans_markdown_code_block() -> None:
    text = '```json\n{"source_file_type": "daily_yield"}\n```'
    assert AnalysisQueryParser._clean_response(text) == '{"source_file_type": "daily_yield"}'


def test_analysis_query_request_accepts_report_type_alias() -> None:
    response = json.dumps(
        {
            "report_type": "daily_yield",
            "target_metrics": ["CT良率"],
            "analysis_logic": "趋势分析",
            "user_intent": "analyse",
        },
        ensure_ascii=False,
    )

    with patch(
        "yield_report.core.analysis_query_parser.llm_manager.chat",
        return_value=response,
    ):
        result = AnalysisQueryParser(provider="deepseek").parse("query")

    assert result.source_file_type == ReportType.DAILY_YIELD
