"""FinereportClient 文件命名测试。"""

from __future__ import annotations

from pathlib import Path

from yield_report.infrastructure.finereport_client import FinereportClient


class FakeYieldDownloadService:
    """模拟 RPA 服务，只创建原始下载文件。"""

    def __init__(self) -> None:
        self.daily_calls: list[dict[str, object]] = []
        self.batch_calls: list[dict[str, object]] = []

    def download_daily_yield(
        self,
        end_date: str,
        product_models: list[str] | None,
        save_dir: Path,
        month_count: int | None = None,
    ) -> Path:
        self.daily_calls.append(
            {
                "end_date": end_date,
                "product_models": product_models,
                "save_dir": save_dir,
                "month_count": month_count,
            }
        )
        path = save_dir / "V3良率及不良率By月周天汇总报表.xlsx"
        path.write_bytes(b"PK\x03\x04daily")
        return path

    def download_batch_yield(
        self,
        start_date: str,
        end_date: str,
        product_models: list[str] | None,
        save_dir: Path,
    ) -> Path:
        self.batch_calls.append(
            {
                "start_date": start_date,
                "end_date": end_date,
                "product_models": product_models,
                "save_dir": save_dir,
            }
        )
        path = save_dir / "V3良率及不良率By批次汇总报表.xlsx"
        path.write_bytes(b"PK\x03\x04batch")
        return path

    def search_reports(self, keyword: str, limit: int = 10) -> list[str]:
        return [f"{keyword}-candidate"]


def _build_client(tmp_path: Path, service: FakeYieldDownloadService) -> FinereportClient:
    """绕过真实 FineReport 初始化，注入假的下载服务。"""
    client = FinereportClient.__new__(FinereportClient)
    client._resources_dir = tmp_path / "resources"  # type: ignore[attr-defined]
    client._output_dir = tmp_path / "output"  # type: ignore[attr-defined]
    client._get_rpa_service = lambda: service  # type: ignore[method-assign]
    return client


def test_daily_report_filename_appends_filter_conditions(tmp_path: Path) -> None:
    service = FakeYieldDownloadService()
    client = _build_client(tmp_path, service)

    result = client.download_daily_yield_report(
        end_date="2026-05-01",
        product_models=["M678"],
    )

    expected_name = "V3良率及不良率By月周天汇总报表_结束日期2026-05-01_产品型号M678.xlsx"
    download_dir = tmp_path / "output" / "downloads"
    assert result == tmp_path / "output" / "decrypted_files" / expected_name
    assert result.exists()
    assert (download_dir / expected_name).exists()
    assert not (download_dir / "V3良率及不良率By月周天汇总报表.xlsx").exists()
    assert service.daily_calls == [
        {
            "end_date": "2026-05-01",
            "product_models": ["M678"],
            "save_dir": download_dir,
            "month_count": None,
        }
    ]


def test_daily_report_download_accepts_month_count_filter(tmp_path: Path) -> None:
    service = FakeYieldDownloadService()
    client = _build_client(tmp_path, service)

    result = client.download_daily_yield_report(
        end_date="2026-06-15",
        product_models=["M588"],
        month_count=3,
    )

    expected_name = "V3良率及不良率By月周天汇总报表_结束日期2026-06-15_产品型号M588_月数3.xlsx"
    assert result == tmp_path / "output" / "decrypted_files" / expected_name
    assert service.daily_calls == [
        {
            "end_date": "2026-06-15",
            "product_models": ["M588"],
            "save_dir": tmp_path / "output" / "downloads",
            "month_count": 3,
        }
    ]


def test_batch_report_filename_appends_multiple_filter_conditions(tmp_path: Path) -> None:
    service = FakeYieldDownloadService()
    client = _build_client(tmp_path, service)

    result = client.download_batch_yield_report(
        start_date="2026-03-01",
        end_date="2026-05-01",
        product_models=["M626", "M673"],
    )

    expected_name = (
        "V3良率及不良率By批次汇总报表_开始日期2026-03-01_"
        "结束日期2026-05-01_产品型号M626+M673.xlsx"
    )
    download_dir = tmp_path / "output" / "downloads"
    assert result == tmp_path / "output" / "decrypted_files" / expected_name
    assert result.exists()
    assert (download_dir / expected_name).exists()
    assert not (download_dir / "V3良率及不良率By批次汇总报表.xlsx").exists()
    assert service.batch_calls == [
        {
            "start_date": "2026-03-01",
            "end_date": "2026-05-01",
            "product_models": ["M626", "M673"],
            "save_dir": download_dir,
        }
    ]


def test_filter_filename_uses_all_when_product_models_are_unspecified(
    tmp_path: Path,
) -> None:
    service = FakeYieldDownloadService()
    client = _build_client(tmp_path, service)

    result = client.download_daily_yield_report(
        end_date="2026-05-01",
        product_models=None,
    )

    assert result == (
        tmp_path
        / "output"
        / "decrypted_files"
        / "V3良率及不良率By月周天汇总报表_结束日期2026-05-01_产品型号全部.xlsx"
    )


def test_client_delegates_unknown_report_search_to_rpa_service(tmp_path: Path) -> None:
    service = FakeYieldDownloadService()
    client = _build_client(tmp_path, service)

    assert client.search_reports("批次") == ["批次-candidate"]
