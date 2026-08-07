from __future__ import annotations

from contextlib import nullcontext
from datetime import date, time
from pathlib import Path

import app.daily_report_app as daily_report_app
from app.daily_report_app import (
    REPO_ROOT,
    default_generator_root,
    download_key,
    format_size,
    generator_now_for_time,
)
from app.daily_report_service import DailyReportRunView, DownloadableReport


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


def test_pinned_runtime_uses_generation_day_not_selected_report_day() -> None:
    assert generator_now_for_time(
        time(17, 30),
        generation_day=date(2026, 8, 7),
    ) == "2026-08-07T17:30:00"


def test_download_key_is_unique_across_page_sections(tmp_path: Path) -> None:
    report = DownloadableReport(path=tmp_path / "daily.xlsx", label="daily.xlsx")

    assert download_key(report, prefix="result", index=0) != download_key(
        report,
        prefix="recent",
        index=0,
    )


def test_result_renders_only_latest_download_without_inline_warnings(
    monkeypatch,
    tmp_path: Path,
) -> None:
    latest = DownloadableReport(path=tmp_path / "latest.xlsx", label="latest.xlsx")
    older = DownloadableReport(path=tmp_path / "older.xlsx", label="older.xlsx")
    rendered_downloads: list[list[DownloadableReport]] = []
    written: list[str] = []

    monkeypatch.setattr(daily_report_app.st, "success", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(daily_report_app.st, "write", lambda value: written.append(value))
    monkeypatch.setattr(
        daily_report_app.st,
        "warning",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("warnings must not render in the result column")
        ),
    )
    monkeypatch.setattr(
        daily_report_app,
        "_render_downloads",
        lambda reports, **_kwargs: rendered_downloads.append(reports),
    )

    daily_report_app._render_result(
        DailyReportRunView(
            success=True,
            summary="完成",
            output_file=latest.path,
            downloads=[latest, older],
            warnings=["warning one"],
            workflow=["mod0", "mod1"],
        )
    )

    assert rendered_downloads == [[latest]]
    assert written == [f"输出文件：`{latest.path}`"]


def test_footer_sections_are_collapsed_with_history_above_warnings(
    monkeypatch,
    tmp_path: Path,
) -> None:
    report = DownloadableReport(path=tmp_path / "daily.xlsx", label="daily.xlsx")
    expanders: list[tuple[str, bool]] = []
    rendered_downloads: list[list[DownloadableReport]] = []
    rendered_warnings: list[str] = []
    rendered_errors: list[str] = []

    def fake_expander(label: str, *, expanded: bool):
        expanders.append((label, expanded))
        return nullcontext()

    monkeypatch.setattr(daily_report_app.st, "expander", fake_expander)
    monkeypatch.setattr(daily_report_app.st, "warning", rendered_warnings.append)
    monkeypatch.setattr(daily_report_app.st, "error", rendered_errors.append)
    monkeypatch.setattr(
        daily_report_app,
        "_render_downloads",
        lambda reports, **_kwargs: rendered_downloads.append(reports),
    )

    daily_report_app._render_footer_sections(
        reports=[report],
        warnings=["warning one", "warning two"],
        errors=["error one"],
    )

    assert expanders == [
        ("历史文件（1）", False),
        ("Warning / Error（3）", False),
    ]
    assert rendered_downloads == [[report]]
    assert rendered_errors == ["error one"]
    assert rendered_warnings == ["warning one", "warning two"]


def test_result_renders_only_a_status_hint_for_errors(monkeypatch) -> None:
    rendered: list[tuple[str, str]] = []

    monkeypatch.setattr(
        daily_report_app.st,
        "warning",
        lambda message: rendered.append(("warning", message)),
    )
    monkeypatch.setattr(
        daily_report_app.st,
        "code",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("raw errors must not render in the status area")
        ),
    )
    monkeypatch.setattr(daily_report_app, "_render_downloads", lambda *_args, **_kwargs: None)

    daily_report_app._render_result(
        DailyReportRunView(
            success=False,
            summary="日报生成失败",
            error_message="raw downstream traceback",
        )
    )

    assert rendered == [("warning", "日报生成失败，请展开下方 Warning / Error 查看详细信息")]
