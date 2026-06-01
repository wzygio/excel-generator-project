"""DataAcquisitionOrchestrator 报表下载入口测试。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from yield_report.application.orchestrator import DataAcquisitionOrchestrator
from yield_report.core.query_parser import ReportType


class FakeFinereportClient:
    """拦截报表下载调用，避免启动真实 FineReport RPA。"""

    def __init__(self) -> None:
        self.daily_calls: list[dict[str, Any]] = []
        self.batch_calls: list[dict[str, Any]] = []

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
