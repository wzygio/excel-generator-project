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
    ) -> Path:
        self.daily_calls.append(
            {
                "end_date": end_date,
                "product_models": product_models,
                "save_dir": save_dir,
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
    client._resources_dir = tmp_path  # type: ignore[attr-defined]
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
    assert result == tmp_path / "decrypted_files" / expected_name
    assert result.exists()
    assert (tmp_path / expected_name).exists()
    assert not (tmp_path / "V3良率及不良率By月周天汇总报表.xlsx").exists()
    assert service.daily_calls == [
        {
            "end_date": "2026-05-01",
            "product_models": ["M678"],
            "save_dir": tmp_path,
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
    assert result == tmp_path / "decrypted_files" / expected_name
    assert result.exists()
    assert (tmp_path / expected_name).exists()
    assert not (tmp_path / "V3良率及不良率By批次汇总报表.xlsx").exists()
    assert service.batch_calls == [
        {
            "start_date": "2026-03-01",
            "end_date": "2026-05-01",
            "product_models": ["M626", "M673"],
            "save_dir": tmp_path,
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
        / "decrypted_files"
        / "V3良率及不良率By月周天汇总报表_结束日期2026-05-01_产品型号全部.xlsx"
    )


def test_client_delegates_unknown_report_search_to_rpa_service(tmp_path: Path) -> None:
    service = FakeYieldDownloadService()
    client = _build_client(tmp_path, service)

    assert client.search_reports("批次") == ["批次-candidate"]
