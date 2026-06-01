"""YieldDownloadService 单元测试。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from yield_report.infrastructure.yield_download_service import (
    BATCH_YIELD_FILENAME,
    BATCH_YIELD_REPORT_NAME,
    DAILY_YIELD_FILENAME,
    DAILY_YIELD_REPORT_NAME,
    YIELD_REPORT_DIRECTORY,
    YieldDownloadService,
)


def _build_service_stub() -> YieldDownloadService:
    """构造不启动真实浏览器的服务实例。"""
    service = YieldDownloadService.__new__(YieldDownloadService)
    service._ensure_browser_ready = MagicMock()  # type: ignore[method-assign]
    service._navigate_to_report = MagicMock()  # type: ignore[method-assign]
    service._handle_product_models = MagicMock()  # type: ignore[method-assign]
    service._query_and_export = MagicMock()  # type: ignore[method-assign]
    service._get_adapter = MagicMock()  # type: ignore[method-assign]
    return service


def test_download_daily_yield_passes_product_models(tmp_path: Path) -> None:
    """月周天报表下载应将产品型号传给下拉筛选逻辑。"""
    service = _build_service_stub()

    result = service.download_daily_yield(
        end_date="2026-05-31",
        product_models=["M678"],
        save_dir=tmp_path,
    )

    assert result == tmp_path / DAILY_YIELD_FILENAME
    service._navigate_to_report.assert_called_once_with(
        DAILY_YIELD_REPORT_NAME,
        report_path=YIELD_REPORT_DIRECTORY,
    )
    service._handle_product_models.assert_called_once_with(["M678"])
    service._query_and_export.assert_called_once_with(
        file_name=DAILY_YIELD_FILENAME,
        save_path=tmp_path / DAILY_YIELD_FILENAME,
    )


def test_download_batch_yield_passes_product_models(tmp_path: Path) -> None:
    """批次报表下载应将产品型号传给下拉筛选逻辑。"""
    service = _build_service_stub()

    result = service.download_batch_yield(
        start_date="2026-04-01",
        end_date="2026-05-31",
        product_models=["M678"],
        save_dir=tmp_path,
    )

    assert result == tmp_path / BATCH_YIELD_FILENAME
    service._navigate_to_report.assert_called_once_with(
        BATCH_YIELD_REPORT_NAME,
        report_path=YIELD_REPORT_DIRECTORY,
    )
    service._handle_product_models.assert_called_once_with(["M678"])
    service._query_and_export.assert_called_once_with(
        file_name=BATCH_YIELD_FILENAME,
        save_path=tmp_path / BATCH_YIELD_FILENAME,
    )
