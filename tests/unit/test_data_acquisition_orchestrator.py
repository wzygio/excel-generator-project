"""DataAcquisitionOrchestrator 报表下载入口测试。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch
from zoneinfo import ZoneInfo

from yield_report.application.orchestrator import DataAcquisitionOrchestrator
from yield_report.core.query_parser import ReportQueryRequest, ReportType

TZ = ZoneInfo("Asia/Shanghai")


class FakeFinereportClient:
    """拦截报表下载调用，避免启动真实 FineReport RPA。"""

    def __init__(self) -> None:
        self.daily_calls: list[dict[str, Any]] = []
        self.batch_calls: list[dict[str, Any]] = []
        self.search_calls: list[dict[str, Any]] = []

    def download_daily_yield_report(
        self,
        end_date: str,
        product_models: list[str] | None,
    ) -> Path:
        self.daily_calls.append(
            {
                "end_date": end_date,
                "product_models": product_models,
            }
        )
        return Path("resources/V3良率及不良率By月周天汇总报表.xlsx")

    def download_batch_yield_report(
        self,
        start_date: str,
        end_date: str,
        product_models: list[str] | None,
    ) -> Path:
        self.batch_calls.append(
            {
                "start_date": start_date,
                "end_date": end_date,
                "product_models": product_models,
            }
        )
        return Path("resources/V3良率及不良率By批次汇总报表.xlsx")

    def search_reports(self, keyword: str, limit: int = 10) -> list[str]:
        self.search_calls.append({"keyword": keyword, "limit": limit})
        return ["V3良率及不良率By批次汇总报表"]


def test_task2_query_injected_into_report_download_interface() -> None:
    """Task2 原句应经项目入口解析后路由到月周天良率报表下载。"""
    user_query = "我想要查询M678这款产品近两个月的良率"
    llm_response = json.dumps(
        {
            "report_type": "daily_yield",
            "start_date": "2026-04-01",
            "end_date": "2026-06-01",
            "product_models": ["M678"],
            "user_intent": "查询 M678 产品近两个月的良率数据",
            "uncertainty_notes": None,
        },
        ensure_ascii=False,
    )

    orchestrator = DataAcquisitionOrchestrator()
    fake_client = FakeFinereportClient()
    orchestrator._finereport_client = fake_client  # type: ignore[assignment]

    with patch(
        "yield_report.core.query_parser.llm_manager.chat",
        return_value=llm_response,
    ):
        result = orchestrator.process_user_query(user_query)

    assert result.success is True
    assert result.parsed_request.report_type == ReportType.DAILY_YIELD
    assert result.parsed_request.start_date == "2026-04-01"
    assert result.parsed_request.end_date == "2026-06-01"
    assert result.parsed_request.product_models == ["M678"]
    assert result.summary == "✅ 成功获取 1/1 份文件"
    assert len(result.results) == 1
    assert result.results[0].file_description == "V3良率及不良率By月周天汇总报表"
    assert fake_client.daily_calls == [
        {
            "end_date": "2026-06-01",
            "product_models": ["M678"],
        }
    ]
    assert fake_client.batch_calls == []


def test_daily_yield_defaults_to_yesterday_before_ten() -> None:
    orchestrator = DataAcquisitionOrchestrator(
        clock=lambda: datetime(2026, 6, 2, 9, 0, tzinfo=TZ)
    )
    fake_client = FakeFinereportClient()
    orchestrator._finereport_client = fake_client  # type: ignore[assignment]

    with patch(
        "yield_report.application.orchestrator.extract_product_models",
        side_effect=RuntimeError("spotfire unavailable"),
    ):
        result = orchestrator.process_request(
            ReportQueryRequest(report_type=ReportType.DAILY_YIELD, user_intent="下载日度良率")
        )

    assert result.success is True
    assert fake_client.daily_calls == [
        {
            "end_date": "2026-06-01",
            "product_models": None,
        }
    ]


def test_batch_yield_defaults_to_90_day_window_and_yesterday_before_ten() -> None:
    orchestrator = DataAcquisitionOrchestrator(
        clock=lambda: datetime(2026, 6, 2, 9, 0, tzinfo=TZ)
    )
    fake_client = FakeFinereportClient()
    orchestrator._finereport_client = fake_client  # type: ignore[assignment]

    with patch(
        "yield_report.application.orchestrator.extract_product_models",
        side_effect=RuntimeError("spotfire unavailable"),
    ):
        result = orchestrator.process_request(
            ReportQueryRequest(report_type=ReportType.BATCH_YIELD, user_intent="查询批次良率")
        )

    assert result.success is True
    assert fake_client.batch_calls == [
        {
            "start_date": "2026-03-04",
            "end_date": "2026-06-01",
            "product_models": None,
        }
    ]


def test_recent_batch_yield_query_routes_to_batch_report_with_product_model() -> None:
    """用户原句应路由到批次良率，并在下载调用中带上产品型号。"""
    user_query = "请查询M626的最近的批次良率"
    llm_response = json.dumps(
        {
            "report_type": "batch_yield",
            "start_date": None,
            "end_date": None,
            "product_models": ["M626"],
            "user_intent": "查询 M626 最近的批次良率",
            "uncertainty_notes": None,
        },
        ensure_ascii=False,
    )
    orchestrator = DataAcquisitionOrchestrator(
        clock=lambda: datetime(2026, 6, 2, 9, 0, tzinfo=TZ)
    )
    fake_client = FakeFinereportClient()
    orchestrator._finereport_client = fake_client  # type: ignore[assignment]

    with patch(
        "yield_report.core.query_parser.llm_manager.chat",
        return_value=llm_response,
    ):
        result = orchestrator.process_user_query(user_query)

    assert result.success is True
    assert result.parsed_request.report_type == ReportType.BATCH_YIELD
    assert result.parsed_request.product_models == ["M626"]
    assert fake_client.batch_calls == [
        {
            "start_date": "2026-03-04",
            "end_date": "2026-06-01",
            "product_models": ["M626"],
        }
    ]
    assert fake_client.daily_calls == []


def test_unknown_report_type_searches_finereport_by_one_keyword() -> None:
    orchestrator = DataAcquisitionOrchestrator()
    fake_client = FakeFinereportClient()
    orchestrator._finereport_client = fake_client  # type: ignore[assignment]

    result = orchestrator.process_request(
        ReportQueryRequest(
            report_type=None,
            user_intent="查询某个批次相关报表，但具体报表名称不确定",
            uncertainty_notes="无法判断具体报表类型",
        )
    )

    assert result.success is False
    assert fake_client.search_calls == [{"keyword": "批次", "limit": 10}]
    assert result.results[0].file_description == "FineReport 报表搜索"
    assert "候选结果" in result.results[0].error_message
