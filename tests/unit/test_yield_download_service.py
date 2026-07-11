"""YieldDownloadService 单元测试。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from shared_kernel.config_model import (
    FineReportDownloadConfig,
    FineReportParameterLabelsConfig,
    SourceFileConfig,
)
from yield_report.infrastructure.yield_download_service import YieldDownloadService
from yield_report.infrastructure.yield_portal_adapter import YieldPortalAdapter


def _build_service_stub() -> YieldDownloadService:
    """构造不启动真实浏览器的服务实例。"""
    service = YieldDownloadService.__new__(YieldDownloadService)
    service._ensure_browser_ready = MagicMock()  # type: ignore[method-assign]
    service._navigate_to_report = MagicMock()  # type: ignore[method-assign]
    service._handle_product_models = MagicMock()  # type: ignore[method-assign]
    service._query_and_export = MagicMock()  # type: ignore[method-assign]
    service._get_adapter = MagicMock()  # type: ignore[method-assign]
    service._settings = FineReportDownloadConfig(
        report_directory="configured/report/directory",
        labels=FineReportParameterLabelsConfig(
            end_date="configured-end-date",
            start_date="configured-start-date",
            product_model="configured-product-model",
            month_count="configured-month-count",
        ),
    )
    service._source_files = {
        "daily_yield": SourceFileConfig(
            description="Configured Daily Report",
            filename="configured-daily.xlsx",
        ),
        "batch_yield": SourceFileConfig(
            description="Configured Batch Report",
            filename="configured-batch.xlsx",
        ),
    }
    return service


def test_download_daily_yield_passes_product_models(tmp_path: Path) -> None:
    """月周天报表下载应将产品型号传给下拉筛选逻辑。"""
    service = _build_service_stub()

    result = service.download_daily_yield(
        end_date="2026-05-31",
        product_models=["M678"],
        save_dir=tmp_path,
    )

    assert result == tmp_path / "configured-daily.xlsx"
    service._navigate_to_report.assert_called_once_with(
        "Configured Daily Report",
        report_path="configured/report/directory",
    )
    service._handle_product_models.assert_called_once_with(["M678"])
    service._query_and_export.assert_called_once_with(
        file_name="configured-daily.xlsx",
        save_path=tmp_path / "configured-daily.xlsx",
    )


def test_download_daily_yield_sets_requested_month_count(tmp_path: Path) -> None:
    """月周天报表应允许 Agent 将默认月数从 2 修正为 3。"""
    service = _build_service_stub()
    adapter = MagicMock()
    service._get_adapter.return_value = adapter

    service.download_daily_yield(
        end_date="2026-06-15",
        product_models=["M588"],
        month_count=3,
        save_dir=tmp_path,
    )

    adapter.set_date.assert_called_once_with("2026-06-15", "configured-end-date")
    adapter.set_text_parameter.assert_called_once_with("3", "configured-month-count")


def test_download_batch_yield_passes_product_models(tmp_path: Path) -> None:
    """批次报表下载应将产品型号传给下拉筛选逻辑。"""
    service = _build_service_stub()
    events: list[tuple[str, object, object | None]] = []
    adapter = MagicMock()
    adapter.set_date.side_effect = lambda date, label: events.append(
        ("set_date", label, date)
    )
    service._get_adapter.return_value = adapter
    service._handle_product_models.side_effect = lambda models: events.append(
        ("product_models", models, None)
    )
    service._query_and_export.side_effect = lambda **kwargs: events.append(
        ("query", kwargs["file_name"], None)
    )

    result = service.download_batch_yield(
        start_date="2026-04-01",
        end_date="2026-05-31",
        product_models=["M678"],
        save_dir=tmp_path,
    )

    assert result == tmp_path / "configured-batch.xlsx"
    service._navigate_to_report.assert_called_once_with(
        "Configured Batch Report",
        report_path="configured/report/directory",
    )
    assert events == [
        ("set_date", "configured-start-date", "2026-04-01"),
        ("set_date", "configured-end-date", "2026-05-31"),
        ("product_models", ["M678"], None),
        ("query", "configured-batch.xlsx", None),
    ]
    service._handle_product_models.assert_called_once_with(["M678"])
    service._query_and_export.assert_called_once_with(
        file_name="configured-batch.xlsx",
        save_path=tmp_path / "configured-batch.xlsx",
    )


class _FakeDateInput:
    def __init__(self) -> None:
        self.actions: list[tuple[str, object]] = []

    def wait_for(self, *, state: str, timeout: int) -> None:
        self.actions.append(("wait_for", state, timeout))

    def click(self) -> None:
        self.actions.append(("click",))

    def fill(self, value: str) -> None:
        self.actions.append(("fill", value))

    def press(self, key: str) -> None:
        self.actions.append(("press", key))


class _FakeLocator:
    def __init__(self, date_input: _FakeDateInput) -> None:
        self.first = date_input


class _FakeFrame:
    def __init__(self, date_input: _FakeDateInput) -> None:
        self.date_input = date_input
        self.xpath = ""

    def locator(self, xpath: str) -> _FakeLocator:
        self.xpath = xpath
        return _FakeLocator(self.date_input)


class _FakePage:
    def __init__(self) -> None:
        self.waits: list[int] = []
        self.url = "https://finereport.local/report"
        self.frames: list[object] = []

    def wait_for_timeout(self, timeout: int) -> None:
        self.waits.append(timeout)

    def screenshot(self, *, path: str, full_page: bool) -> None:
        Path(path).write_bytes(b"png")


def test_yield_portal_adapter_submits_date_with_tab_not_enter() -> None:
    """批次报表填开始日期时 Enter 会提前查询；日期提交必须用 Tab。"""
    date_input = _FakeDateInput()
    frame = _FakeFrame(date_input)
    page = _FakePage()
    adapter = YieldPortalAdapter(page)  # type: ignore[arg-type]
    adapter.get_active_frame = lambda: frame  # type: ignore[method-assign]

    adapter.set_date("2026-03-04", "开始日期：")

    assert ("press", "Tab") in date_input.actions
    assert ("press", "Enter") not in date_input.actions
    assert "开始日期：" in frame.xpath


def test_capture_debug_artifacts_uses_output_diagnostics_layout(tmp_path: Path) -> None:
    service = YieldDownloadService.__new__(YieldDownloadService)
    service.download_dir = tmp_path / "output" / "downloads" / "raw" / "finereport"
    service.download_dir.mkdir(parents=True)
    adapter = MagicMock()
    adapter.page = _FakePage()
    service._get_adapter = MagicMock(return_value=adapter)  # type: ignore[method-assign]

    service._capture_debug_artifacts("daily_yield_failed")

    assert list((tmp_path / "output" / "diagnostics" / "rpa" / "screenshots").glob("*.png"))
    assert list((tmp_path / "output" / "diagnostics" / "rpa" / "console").glob("*.txt"))
    assert not (tmp_path / "output" / "downloads" / "raw" / "rpa_debug").exists()
