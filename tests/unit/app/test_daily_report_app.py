from __future__ import annotations

from pathlib import Path

from app.daily_report_app import REPO_ROOT, default_generator_root, download_key, format_size
from app.daily_report_service import DownloadableReport


def test_repo_root_points_to_project_root() -> None:
    assert REPO_ROOT.name == "excel-generator-project"
    assert (REPO_ROOT / "src" / "yield_report").is_dir()


def test_default_generator_root_can_be_configured(monkeypatch, tmp_path: Path) -> None:
    configured = tmp_path / "daily-report-generator"
    monkeypatch.setenv("YIELD_REPORT_DAILY_REPORT_GENERATOR_ROOT", str(configured))

    assert default_generator_root() == configured


def test_format_size_uses_readable_units() -> None:
    assert format_size(12) == "12 B"
    assert format_size(2048) == "2.0 KB"
    assert format_size(3 * 1024 * 1024) == "3.0 MB"


def test_download_key_is_unique_across_page_sections(tmp_path: Path) -> None:
    report = DownloadableReport(path=tmp_path / "daily.xlsx", label="daily.xlsx")

    assert download_key(report, prefix="result", index=0) != download_key(
        report,
        prefix="recent",
        index=0,
    )
