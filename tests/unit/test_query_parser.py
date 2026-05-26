"""
test_query_parser.py: QueryParser 单元测试

测试目标:
1. ReportQueryRequest Pydantic 模型校验
2. _clean_response 静态方法 (代码块移除)
3. parse() 正常流程 (mock LLM 响应)
4. parse() 异常处理 (LLM 调用失败、非法 JSON、字段校验失败)
5. ReportType 枚举与元数据完整性
"""

from __future__ import annotations

import json
import logging
from datetime import date
from unittest.mock import patch

import pytest

from yield_report.core.query_parser import (
    REPORT_TYPE_META,
    QueryParser,
    QueryParserError,
    ReportQueryRequest,
    ReportType,
)

logger = logging.getLogger(__name__)


# ============================================================
# Fixtures
# ============================================================

VALID_LLM_RESPONSE = json.dumps({
    "report_type": "daily_yield",
    "start_date": None,
    "end_date": "2026-05-25",
    "product_models": ["M678"],
    "user_intent": "下载今日V3良率报表",
    "uncertainty_notes": None,
}, ensure_ascii=False)


VALID_LLM_RESPONSE_WITH_CODEBLOCK = (
    "```json\n" + VALID_LLM_RESPONSE + "\n```"
)


@pytest.fixture
def parser() -> QueryParser:
    return QueryParser(provider="deepseek")


# ============================================================
# ReportQueryRequest 模型测试
# ============================================================

class TestReportQueryRequest:
    """测试 Pydantic 模型校验。"""

    def test_valid_request_all_fields(self):
        """所有字段有效的完整请求。"""
        req = ReportQueryRequest(
            report_type=ReportType.DAILY_YIELD,
            start_date="2026-05-20",
            end_date="2026-05-25",
            product_models=["3TED01"],
            user_intent="下载日报",
        )
        assert req.report_type == ReportType.DAILY_YIELD
        assert req.end_date == "2026-05-25"
        assert req.product_models == ["3TED01"]

    def test_valid_request_minimal(self):
        """最小请求: 仅 report_type。"""
        req = ReportQueryRequest(
            report_type=ReportType.BATCH_YIELD,
            end_date="2026-05-25",
            user_intent="test",
        )
        assert req.report_type == ReportType.BATCH_YIELD
        assert req.start_date is None
        assert req.product_models is None

    def test_valid_date_format(self):
        """标准 YYYY-MM-DD 格式通过。"""
        req = ReportQueryRequest(
            start_date="2026-01-01",
            end_date="2026-12-31",
            user_intent="test",
        )
        assert req.start_date == "2026-01-01"

    def test_invalid_date_format(self):
        """非标准日期格式触发 ValidationError。"""
        with pytest.raises(ValueError, match="日期格式无效"):
            ReportQueryRequest(
                end_date="2026/05/25",
                user_intent="test",
            )

    def test_invalid_date_value(self):
        """非法日期值触发 ValidationError。"""
        with pytest.raises(ValueError, match="日期格式无效"):
            ReportQueryRequest(
                end_date="2026-13-01",
                user_intent="test",
            )

    def test_report_type_from_string(self):
        """report_type 支持字符串赋值 (Pydantic StrEnum)。"""
        req = ReportQueryRequest(
            report_type="daily_yield",
            end_date="2026-05-25",
            user_intent="test",
        )
        assert req.report_type == ReportType.DAILY_YIELD

    def test_invalid_report_type(self):
        """非法 report_type 字符串触发 ValidationError。"""
        with pytest.raises(ValueError):
            ReportQueryRequest(
                report_type="invalid_type",
                end_date="2026-05-25",
                user_intent="test",
            )

    def test_model_dump(self):
        """model_dump 排除 None 值。"""
        req = ReportQueryRequest(
            report_type=ReportType.DAILY_YIELD,
            end_date="2026-05-25",
            user_intent="下载日报",
        )
        dumped = req.model_dump(exclude_none=True)
        assert "start_date" not in dumped
        assert "product_models" not in dumped
        assert dumped["report_type"] == "daily_yield"


# ============================================================
# _clean_response 测试
# ============================================================

class TestCleanResponse:
    """测试 LLM 响应清理。"""

    def test_clean_json_no_codeblock(self):
        """纯 JSON 原样返回。"""
        result = QueryParser._clean_response('{"key": "value"}')
        assert result == '{"key": "value"}'

    def test_clean_json_with_codeblock(self):
        """带 ```json ``` 代码块，移除包裹。"""
        result = QueryParser._clean_response('```json\n{"key": "value"}\n```')
        assert result == '{"key": "value"}'

    def test_clean_json_with_plain_codeblock(self):
        """带 ``` ``` 无语言标记，移除包裹。"""
        result = QueryParser._clean_response('```\n{"key": "value"}\n```')
        assert result == '{"key": "value"}'

    def test_clean_json_with_lang_prefix(self):
        """只有 json 前缀 + 内容，移除前缀。"""
        result = QueryParser._clean_response('json\n{"key": "value"}')
        assert result == '{"key": "value"}'

    def test_clean_whitespace_only(self):
        """仅空白字符，返回空字符串。"""
        result = QueryParser._clean_response("   \n\t  ")
        assert result == ""


# ============================================================
# parse() 正常流程测试 (mock LLM)
# ============================================================

class TestParseSuccess:
    """测试 parse() 正常流程。"""

    def test_parse_daily_yield_with_model(self, parser: QueryParser):
        """解析日报查询，正确提取产品型号和日期。"""
        with patch(
            "yield_report.core.query_parser.llm_manager.chat",
            return_value=VALID_LLM_RESPONSE,
        ):
            result = parser.parse(
                "请帮我下载今天的V3良率及不良率By月周天汇总报表，产品型号为M678"
            )
            assert result.report_type == ReportType.DAILY_YIELD
            assert result.product_models == ["M678"]

    def test_parse_all_models(self, parser: QueryParser):
        """用户说所有型号，product_models 为空列表。"""
        response = json.dumps({
            "report_type": "daily_yield",
            "end_date": "2026-05-25",
            "product_models": [],
            "user_intent": "下载所有型号的日报",
        }, ensure_ascii=False)

        with patch(
            "yield_report.core.query_parser.llm_manager.chat",
            return_value=response,
        ):
            result = parser.parse("帮我下载今天所有型号的良率报表")
            assert result.product_models == []

    def test_parse_batch_yield(self, parser: QueryParser):
        """解析批次报表查询。"""
        response = json.dumps({
            "report_type": "batch_yield",
            "end_date": "2026-05-25",
            "product_models": ["3TED01"],
            "user_intent": "下载批次良率报表",
        }, ensure_ascii=False)

        with patch(
            "yield_report.core.query_parser.llm_manager.chat",
            return_value=response,
        ):
            result = parser.parse("下载批次良率报表")
            assert result.report_type == ReportType.BATCH_YIELD

    def test_parse_response_with_codeblock(self, parser: QueryParser):
        """LLM 返回带代码块包裹的响应，自动清理后正确解析。"""
        with patch(
            "yield_report.core.query_parser.llm_manager.chat",
            return_value=VALID_LLM_RESPONSE_WITH_CODEBLOCK,
        ):
            result = parser.parse("良率日报 M678")
            assert result.report_type == ReportType.DAILY_YIELD

    def test_parse_passes_today_date(self, parser: QueryParser):
        """验证 SYSTEM_PROMPT 中的 {today_date} 被正确替换。"""
        captured_prompts = []

        def fake_chat(provider=None, messages=None, system_prompt=None, **kwargs):
            captured_prompts.append(system_prompt)
            return VALID_LLM_RESPONSE

        with patch(
            "yield_report.core.query_parser.llm_manager.chat",
            side_effect=fake_chat,
        ):
            parser.parse("良率日报")
            assert len(captured_prompts) == 1
            today = date.today().isoformat()
            assert today in captured_prompts[0]


# ============================================================
# parse() 异常处理测试
# ============================================================

class TestParseErrors:
    """测试 parse() 异常处理。"""

    def test_llm_call_failure(self, parser: QueryParser):
        """LLM 调用失败，QueryParserError。"""
        with patch(
            "yield_report.core.query_parser.llm_manager.chat",
            side_effect=RuntimeError("API 不可用"),
        ):
            with pytest.raises(QueryParserError, match="LLM 调用失败"):
                parser.parse("良率日报")

    def test_empty_response(self, parser: QueryParser):
        """LLM 返回空字符串，QueryParserError。"""
        with patch(
            "yield_report.core.query_parser.llm_manager.chat",
            return_value="",
        ):
            with pytest.raises(QueryParserError, match="空响应"):
                parser.parse("良率日报")

    def test_whitespace_only_response(self, parser: QueryParser):
        """LLM 返回仅空白，QueryParserError。"""
        with patch(
            "yield_report.core.query_parser.llm_manager.chat",
            return_value="   \n  ",
        ):
            with pytest.raises(QueryParserError, match="空响应"):
                parser.parse("良率日报")

    def test_invalid_json_response(self, parser: QueryParser):
        """LLM 返回非法 JSON，QueryParserError。"""
        with patch(
            "yield_report.core.query_parser.llm_manager.chat",
            return_value="not a valid json",
        ):
            with pytest.raises(QueryParserError, match="非法.*JSON"):
                parser.parse("良率日报")

    def test_invalid_field_type(self, parser: QueryParser):
        """JSON 字段类型错误 (report_type 为整数)，QueryParserError。"""
        with patch(
            "yield_report.core.query_parser.llm_manager.chat",
            return_value='{"report_type": 123, "user_intent": "test"}',
        ):
            with pytest.raises(QueryParserError, match="参数校验失败"):
                parser.parse("良率日报")


# ============================================================
# ReportType 枚举与元数据测试
# ============================================================

class TestReportType:
    """测试 ReportType 枚举元数据。"""

    def test_all_report_types_have_meta(self):
        """每个枚举值都有对应的元数据。"""
        for rt in ReportType:
            assert rt in REPORT_TYPE_META, f"缺少元数据: {rt}"
            meta = REPORT_TYPE_META[rt]
            assert "name" in meta
            assert "description" in meta
            assert "source" in meta

    def test_report_type_str(self):
        """StrEnum 可直接转字符串。"""
        assert str(ReportType.DAILY_YIELD) == "daily_yield"

    def test_report_type_values(self):
        """value 属性返回字符串值。"""
        assert ReportType.DAILY_YIELD.value == "daily_yield"