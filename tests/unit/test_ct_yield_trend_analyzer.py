from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from yield_report.infrastructure.ct_yield_trend_analyzer import CtYieldTrendAnalyzer


def test_ct_yield_trend_analyzer_reads_standard_workbook(tmp_path: Path) -> None:
    file_path = tmp_path / "daily_yield.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "CT"
    worksheet.append(["", "CT良率及不良率By月周天汇总报表V1.0"])
    worksheet.append(["", "", "", "", "", "", "报表说明"])
    worksheet.append([
        None,
        "ProductCode\n产品型号",
        "Operation\n站点",
        "Factory\n归属工厂",
        "DefectGroup\n不良分组",
        None,
        "M05",
        "W18",
        "4/25",
        "4/26",
        "4/27",
        "4/28",
        "4/29",
        "4/30",
        "5/1",
    ])
    worksheet.append([None, "M678", "CT", "CT产出数", None, None, 100, 100, 0, 352, 0, 53, 4, 0, 0])
    worksheet.append([None, None, None, "CT良率", None, None, 0.9, 0.9, 0, 0.832386, 0, 1.0, 1.0, 0, 0])
    workbook.save(file_path)

    result = CtYieldTrendAnalyzer().analyze(file_path, product_model="M678", days=7)

    assert result.product_model == "M678"
    assert len(result.points) == 7
    assert "有效生产日 3/7 天" in result.result_text
    assert "83.24%" in result.result_text
    assert "100.00%" in result.result_text
    assert "+16.76 pct" in result.result_text
