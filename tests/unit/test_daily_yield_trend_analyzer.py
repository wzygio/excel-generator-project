from __future__ import annotations

import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from openpyxl import Workbook

from yield_report.infrastructure.daily_yield_trend_analyzer import DailyYieldTrendAnalyzer


def _write_daily_yield_workbook(file_path: Path) -> Path:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "屏体综合良率"
    worksheet.append(["", "屏体综合良率报表V1.0"])
    worksheet.append(["", "", "报表说明"])
    worksheet.append(
        [
            None,
            "ProductCode\n产品型号",
            "Type\n类别",
            None,
            "M06",
            "W23",
            "5/26",
            "5/27",
            "5/28",
            "5/29",
            "5/30",
            "5/31",
            "6/1",
        ]
    )
    worksheet.append(
        [
            None,
            "M626",
            "屏体",
            "屏体综合良率",
            0.90,
            0.91,
            0.92,
            0.93,
            0.94,
            0.95,
            0.96,
            0.97,
            0.98,
        ]
    )
    workbook.save(file_path)
    workbook.close()
    return file_path


def _force_stale_dimension(path: Path, dimension: str = "A1:A1") -> None:
    temp_path = path.with_suffix(".tmp.xlsx")
    with ZipFile(path, "r") as source, ZipFile(temp_path, "w", ZIP_DEFLATED) as target:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                data = re.sub(
                    rb'<dimension ref="[^"]+"',
                    f'<dimension ref="{dimension}"'.encode(),
                    data,
                    count=1,
                )
            target.writestr(item, data)
    temp_path.replace(path)


def test_daily_yield_trend_analyzer_reads_generic_daily_yield(tmp_path: Path) -> None:
    file_path = _write_daily_yield_workbook(tmp_path / "daily_yield.xlsx")

    result = DailyYieldTrendAnalyzer().analyze(file_path, product_model="M626", days=7)

    assert result.product_model == "M626"
    assert result.sheet_name == "屏体综合良率"
    assert result.metric_name == "屏体综合良率"
    assert len(result.points) == 7
    assert "92.00%" in result.result_text
    assert "98.00%" in result.result_text
    assert "+6.00 pct" in result.result_text


def test_daily_yield_trend_analyzer_resets_stale_dimension(tmp_path: Path) -> None:
    file_path = _write_daily_yield_workbook(tmp_path / "daily_yield.xlsx")
    _force_stale_dimension(file_path)

    result = DailyYieldTrendAnalyzer().analyze(file_path, product_model="M626", days=7)

    assert len(result.points) == 7
    assert "最近一周日度良率变化趋势" in result.result_text
