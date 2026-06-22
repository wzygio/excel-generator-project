from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from yield_report.agent.spec_model import RunContext
from yield_report.infrastructure import v_agent_client
from yield_report.skills.anomaly_monitor import tool
from yield_report.skills.anomaly_monitor.analyzers import (
    ConcentrationAnalyzer,
    normalize_anomaly_row,
    parse_ratio,
)
from yield_report.skills.anomaly_monitor.models import AnomalyMonitorRequest


def _context(tmp_path: Path) -> RunContext:
    return RunContext(run_id="anomaly-run", workspace=tmp_path, output_dir=tmp_path / "outputs")


class _FakeVAgentResponse:
    status_code = 202
    text = "accepted"

    def raise_for_status(self) -> None:
        return None


def test_parse_ratio_accepts_percent_strings_and_numbers() -> None:
    assert parse_ratio("12.5%") == 0.125
    assert parse_ratio(0.31) == 0.31
    assert parse_ratio("0.31") == 0.31
    assert parse_ratio("") == 0.0


def test_concentration_uses_dynamic_top_unit_ratio_to_avoid_small_unit_top5_false_positive() -> None:
    row = normalize_anomaly_row(
        {
            "prod_code": "M678",
            "defect_desc": "DARK",
            "defect_code": "D001",
            "oper_group": "CT",
            "batch": "B20260601",
        },
        0,
    )
    detail_rows = [
        {
            "prod_code": "M678",
            "defect_desc": "DARK",
            "defect_code": "D001",
            "batch": "B20260601",
            "membrane_pos": f"MAP-{unit}",
        }
        for unit in range(5)
        for _ in range(5)
    ]

    evidence = ConcentrationAnalyzer(detail_rows).analyze(row)

    assert evidence.detected is False


def test_concentration_detects_top_twenty_percent_units_when_cumulative_ratio_is_high() -> None:
    row = normalize_anomaly_row(
        {
            "prod_code": "M678",
            "defect_desc": "DARK",
            "defect_code": "D001",
            "oper_group": "CT",
            "batch": "B20260601",
        },
        0,
    )
    detail_rows = []
    for unit in range(5):
        detail_rows.extend(
            {
                "prod_code": "M678",
                "defect_desc": "DARK",
                "defect_code": "D001",
                "batch": "B20260601",
                "membrane_pos": f"MAP-HIGH-{unit}",
            }
            for _ in range(16)
        )
    for unit in range(20):
        detail_rows.append(
            {
                "prod_code": "M678",
                "defect_desc": "DARK",
                "defect_code": "D001",
                "batch": "B20260601",
                "membrane_pos": f"MAP-LOW-{unit}",
            }
        )

    evidence = ConcentrationAnalyzer(detail_rows).analyze(row)

    assert evidence.detected is True
    assert "MAP-HIGH" in evidence.signature


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    import csv

    with path.open("w", encoding="gbk", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_spotfire_products(path: Path, products: list[str]) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    assert worksheet is not None
    worksheet.title = "Sheet1"
    worksheet["A1"] = "产品型号"
    for row_index, product in enumerate(products, start=2):
        worksheet.cell(row=row_index, column=1, value=product)
    workbook.save(path)


def test_anomaly_monitor_builds_candidates_from_shared_source_csvs_and_spotfire_products(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "shared"
    source_dir.mkdir()
    spotfire = tmp_path / "spotfire.xlsx"
    _write_spotfire_products(spotfire, ["M626"])

    _write_csv(
        source_dir / "hl_data.csv",
        [
            {
                "hl_type": "当日超规-批次",
                "prod_code": "M626",
                "date_value": "20260615",
                "oper_group": "CT",
                "defect_desc": "常亮白斑",
                "defect_code": "DMSM6",
                "ratio": "0.0052",
                "ng_qty": "25",
                "input_qty": "4800",
                "bijiao_type": "",
                "bijiao_ratio": "0",
                "month_value": "2026M06",
                "month_ratio": "0.0014",
                "week_value": "2026W25",
                "week_ratio": "0.0047",
                "ct_batch": "0.0030",
                "batch": "26/06/05蒸镀批",
                "lag_batch": "26/05/25蒸镀批",
                "lag2_batch": "",
                "batch_ratio": "0.0030",
                "lag_ratio": "0.0007",
                "lag2_ratio": "0",
                "batch_gap": "0.0023",
                "interface_time": "2026-06-15 16:43:00",
            },
            {
                "hl_type": "当日超规-批次",
                "prod_code": "M678",
                "date_value": "20260615",
                "oper_group": "CT",
                "defect_desc": "不应进入",
                "defect_code": "D000",
                "ratio": "0.0500",
                "ng_qty": "99",
                "input_qty": "1000",
                "bijiao_type": "",
                "bijiao_ratio": "0",
                "month_value": "2026M06",
                "month_ratio": "0.0010",
                "week_value": "2026W25",
                "week_ratio": "0.0010",
                "ct_batch": "0.0200",
                "batch": "26/06/05蒸镀批",
                "lag_batch": "",
                "lag2_batch": "",
                "batch_ratio": "0.0200",
                "lag_ratio": "0",
                "lag2_ratio": "0",
                "batch_gap": "0.0200",
                "interface_time": "2026-06-15 16:43:00",
            },
        ],
    )
    _write_csv(
        source_dir / "batch_yield_data.csv",
        [
            {
                "prod_code": "M626",
                "type_batch": "",
                "sub_prod_id": "26/06/05蒸镀批",
                "ct_yld_ratio": "0.9",
                "lot_input_ratio": "0.55",
                "ct_pnl_qty": "1000",
                "now_ct_qty": "900",
                "interface_time": "2026-06-15 16:43:00",
            },
            {
                "prod_code": "M678",
                "type_batch": "",
                "sub_prod_id": "26/06/05蒸镀批",
                "ct_yld_ratio": "0.9",
                "lot_input_ratio": "0.55",
                "ct_pnl_qty": "1000",
                "now_ct_qty": "900",
                "interface_time": "2026-06-15 16:43:00",
            },
        ],
    )
    _write_csv(
        source_dir / "mwdl_data.csv",
        [
            {
                "prod_code": "M626",
                "date_type": "BATCH",
                "date_value": "26/05/25蒸镀批",
                "oper_group": "CT",
                "defect_desc": "常亮白斑",
                "defect_code": "DMSM6",
                "ng_qty": "5",
                "input_qty": "5000",
                "ratio": "0.0010",
                "interface_time": "2026-06-15 16:43:02",
            }
        ],
    )
    _write_csv(
        source_dir / "ct_yield_data.csv",
        [
            {
                "date_type": "DAY",
                "date_timekey": "20260615",
                "event_timekey": "20260615103000",
                "prod_code": "M626",
                "sub_prod_id": "",
                "sub_prod_type": "",
                "lot_id": "L3MY65010261",
                "sheet_id": "L3MY65010261",
                "panel_id": "L3MY650102611A10",
                "glass_id": "L3MY65010261",
                "oper_group": "CT",
                "oper_code": "35000",
                "defect_code": "DMSM6",
                "crp_flag": "N",
                "ng_qty": "1",
                "output_qty": "1",
                "ng_panel_id": "",
                "output_panel_id": "L3MY650102611A10",
                "lot": "26/06/05蒸镀批",
                "interface_time": "2026-06-15 16:40:07+08:00",
            }
        ],
    )
    _write_csv(
        source_dir / "imp_ct_dft_group.csv",
        [
            {
                "defect_group": "OLED_Mura",
                "defect_code": "DMSM6",
                "defect_desc": "常亮白斑",
                "defect_step": "",
                "defect_spec_down": "",
                "defect_spec_up": "",
                "factory": "OLED",
                "oper_code": "",
                "interface_time": "2026-06-15 16:43:00",
                "special_item": "",
                "responsibility": "",
                "department": "",
            }
        ],
    )

    result = tool.run(
        AnomalyMonitorRequest(
            report_date="2026-06-15",
            source_files={
                "data_source_dir": source_dir,
                "spotfire": spotfire,
            },
        ),
        _context(tmp_path),
    )

    assert result.success is True
    assert result.data["summary_counts"]["total"] == 1
    assert result.data["summary_counts"]["hl"] == 1
    assert result.data["verdicts"][0]["anomaly_type"] == "真实异常"
    assert result.data["real_anomalies"][0]["product_model"] == "M626"
    assert result.data["real_anomalies"][0]["defect_desc"] == "常亮白斑"
    assert result.data["source_summary"]["daily_anomaly_initial"]["source_tables"] == ["hl_data"]
    assert not any("CT良率异常波动管理表作为当日异常初筛候选源" in warning for warning in result.warnings)


def test_anomaly_monitor_derives_missing_candidates_from_mwdl_lot_rows(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "shared"
    source_dir.mkdir()

    _write_csv(
        source_dir / "hl_data.csv",
        [
            {
                "hl_type": "当日超规-批次",
                "prod_code": "M626",
                "date_value": "20260615",
                "oper_group": "CT",
                "defect_desc": "常亮白斑",
                "defect_code": "DMSM6",
                "ratio": "0.0052",
                "ng_qty": "25",
                "input_qty": "4800",
                "bijiao_type": "",
                "bijiao_ratio": "0",
                "month_value": "2026M06",
                "month_ratio": "0.0014",
                "week_value": "2026W25",
                "week_ratio": "0.0047",
                "ct_batch": "0.0030",
                "batch": "26/06/05蒸镀批",
                "lag_batch": "",
                "lag2_batch": "",
                "batch_ratio": "0.0030",
                "lag_ratio": "0",
                "lag2_ratio": "0",
                "batch_gap": "0.0030",
                "interface_time": "2026-06-15 16:43:00",
            }
        ],
    )
    _write_csv(
        source_dir / "batch_yield_data.csv",
        [
            {
                "prod_code": "C550",
                "type_batch": "",
                "sub_prod_id": "26/05/28蒸镀批",
                "ct_yld_ratio": "0.9",
                "lot_input_ratio": "0.06557",
                "ct_pnl_qty": "1000",
                "now_ct_qty": "900",
                "interface_time": "2026-06-15 16:43:00",
            }
        ],
    )
    _write_csv(
        source_dir / "mwdl_data.csv",
        [
            {
                "prod_code": "C550",
                "date_type": "DAY",
                "date_value": "20260615",
                "oper_group": "CUT",
                "defect_desc": "来料外围OLED 异物",
                "defect_code": "T0UPT",
                "ng_qty": "3",
                "input_qty": "11193",
                "ratio": "0.00027",
                "interface_time": "2026-06-15 16:43:02",
            },
            {
                "prod_code": "C550",
                "date_type": "MONTH",
                "date_value": "2026M06",
                "oper_group": "CUT",
                "defect_desc": "来料外围OLED 异物",
                "defect_code": "T0UPT",
                "ng_qty": "156",
                "input_qty": "79134",
                "ratio": "0.00197",
                "interface_time": "2026-06-15 16:43:02",
            },
            {
                "prod_code": "C550",
                "date_type": "WEEK",
                "date_value": "2026W25",
                "oper_group": "CUT",
                "defect_desc": "来料外围OLED 异物",
                "defect_code": "T0UPT",
                "ng_qty": "53",
                "input_qty": "39556",
                "ratio": "0.00134",
                "interface_time": "2026-06-15 16:43:02",
            },
            {
                "prod_code": "C550",
                "date_type": "LOT",
                "date_value": "26/05/28蒸镀批",
                "oper_group": "CUT",
                "defect_desc": "来料外围OLED 异物",
                "defect_code": "T0UPT",
                "ng_qty": "136",
                "input_qty": "62415",
                "ratio": "0.00218",
                "interface_time": "2026-06-15 16:43:02",
            },
        ],
    )
    _write_csv(
        source_dir / "ct_yield_data.csv",
        [
            {
                "date_type": "DAY",
                "date_timekey": "20260615",
                "event_timekey": f"2026061510{index:04d}",
                "prod_code": "C550",
                "sub_prod_id": "",
                "sub_prod_type": "",
                "lot_id": f"L3CG6500{index % 4}",
                "sheet_id": f"L3CG6500{index % 4}",
                "panel_id": f"L3CG6500M041E{index % 3}",
                "glass_id": f"L3CG6500{index % 4}",
                "oper_group": "CT",
                "oper_code": "35000",
                "defect_code": "T0UPT",
                "crp_flag": "N",
                "ng_qty": "1",
                "output_qty": "1",
                "ng_panel_id": "",
                "output_panel_id": f"L3CG6500M041E{index % 3}",
                "lot": "26/05/28蒸镀批",
                "interface_time": "2026-06-15 16:40:07+08:00",
            }
            for index in range(24)
        ],
    )

    result = tool.run(
        AnomalyMonitorRequest(
            report_date="2026-06-15",
            product_models=["C550"],
            source_files={"data_source_dir": source_dir},
        ),
        _context(tmp_path),
    )

    assert result.success is True
    assert result.data["summary_counts"]["hl"] == 0
    verdict = result.data["verdicts"][0]
    assert verdict["row"]["product_model"] == "C550"
    assert verdict["row"]["defect_desc"] == "来料外围OLED 异物"
    assert verdict["row"]["station"] == "CUT"
    assert verdict["row"]["raw"]["source_table"] == "mwdl_data"
    assert verdict["decision"] == "skipped"
    assert verdict["decision_reason"] == "发生站点非CT"


def test_anomaly_monitor_mwdl_candidates_require_current_day_summary_and_are_deduped(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "shared"
    source_dir.mkdir()

    _write_csv(
        source_dir / "hl_data.csv",
        [
            {
                "hl_type": "batch",
                "prod_code": "M999",
                "date_value": "20260615",
                "oper_group": "CT",
                "defect_desc": "IGNORE",
                "defect_code": "D000",
                "ratio": "0",
                "ng_qty": "0",
                "batch": "IGNORED",
                "batch_ratio": "0",
                "month_ratio": "0",
            }
        ],
    )
    _write_csv(
        source_dir / "batch_yield_data.csv",
        [
            {"prod_code": "C550", "sub_prod_id": "BATCH-A", "lot_input_ratio": "0.55"},
            {"prod_code": "C550", "sub_prod_id": "BATCH-B", "lot_input_ratio": "0.55"},
        ],
    )
    _write_csv(
        source_dir / "mwdl_data.csv",
        [
            {
                "prod_code": "C550",
                "date_type": "DAY",
                "date_value": "20260615",
                "oper_group": "CUT",
                "defect_desc": "PARTICLE",
                "defect_code": "D100",
                "ng_qty": "33",
                "input_qty": "10000",
                "ratio": "0.0033",
            },
            {
                "prod_code": "C550",
                "date_type": "MONTH",
                "date_value": "2026M06",
                "oper_group": "CUT",
                "defect_desc": "PARTICLE",
                "defect_code": "D100",
                "ng_qty": "60",
                "input_qty": "100000",
                "ratio": "0.0006",
            },
            {
                "prod_code": "C550",
                "date_type": "LOT",
                "date_value": "BATCH-A",
                "oper_group": "CUT",
                "defect_desc": "PARTICLE",
                "defect_code": "D100",
                "ng_qty": "40",
                "input_qty": "10000",
                "ratio": "0.0040",
            },
            {
                "prod_code": "C550",
                "date_type": "LOT",
                "date_value": "BATCH-B",
                "oper_group": "CUT",
                "defect_desc": "PARTICLE",
                "defect_code": "D100",
                "ng_qty": "80",
                "input_qty": "10000",
                "ratio": "0.0080",
            },
            {
                "prod_code": "C550",
                "date_type": "LOT",
                "date_value": "BATCH-C",
                "oper_group": "CUT",
                "defect_desc": "HISTORICAL_ONLY",
                "defect_code": "D200",
                "ng_qty": "90",
                "input_qty": "10000",
                "ratio": "0.0090",
            },
        ],
    )

    result = tool.run(
        AnomalyMonitorRequest(
            report_date="2026-06-15",
            product_models=["C550"],
            source_files={"data_source_dir": source_dir},
        ),
        _context(tmp_path),
    )

    assert result.success is True
    assert result.data["summary_counts"]["total"] == 1
    verdict = result.data["verdicts"][0]
    assert verdict["row"]["defect_desc"] == "PARTICLE"
    assert verdict["row"]["batch"] == "BATCH-B"


def test_anomaly_monitor_keeps_combined_product_models_from_spotfire_filter(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "shared"
    source_dir.mkdir()
    spotfire = tmp_path / "spotfire.xlsx"
    _write_spotfire_products(spotfire, ["C546&C547"])

    _write_csv(
        source_dir / "hl_data.csv",
        [
            {
                "hl_type": "batch",
                "prod_code": "C546&C547",
                "date_value": "20260622",
                "oper_group": "CT",
                "defect_desc": "S_LINE",
                "defect_code": "D100",
                "ratio": "0.003",
                "ng_qty": "35",
                "month_ratio": "0.001",
                "week_ratio": "0.003",
                "batch": "BATCH-A",
                "batch_ratio": "0.002",
                "lag_ratio": "0.0005",
                "batch_gap": "0.0015",
                "interface_time": "2026-06-22 10:00:00",
            }
        ],
    )
    _write_csv(
        source_dir / "batch_yield_data.csv",
        [{"prod_code": "C546&C547", "sub_prod_id": "BATCH-A", "lot_input_ratio": "0.55"}],
    )

    result = tool.run(
        AnomalyMonitorRequest(
            report_date="2026-06-22",
            source_files={"data_source_dir": source_dir, "spotfire": spotfire},
        ),
        _context(tmp_path),
    )

    assert result.success is True
    assert result.data["summary_counts"]["total"] == 1
    assert result.data["verdicts"][0]["row"]["product_model"] == "C546&C547"


def test_anomaly_monitor_selects_one_ct_hl_source_candidate_per_product(
    tmp_path: Path,
) -> None:
    result = tool.run(
        AnomalyMonitorRequest(
            report_date="2026-06-22",
            initial_rows=[
                {
                    "source_table": "hl_data",
                    "prod_code": "M756",
                    "defect_desc": "LOW_SIGNAL",
                    "defect_code": "D101",
                    "oper_group": "CT",
                    "ratio": 0.002,
                    "month_ratio": 0.001,
                    "batch_ratio": 0.002,
                    "batch_gap": 0.001,
                    "batch": "BATCH-1",
                    "batch_date": "2026-06-22",
                    "lot_input_ratio": 0.55,
                    "ng_qty": 40,
                },
                {
                    "source_table": "hl_data",
                    "prod_code": "M756",
                    "defect_desc": "HIGH_SIGNAL",
                    "defect_code": "D102",
                    "oper_group": "CT",
                    "ratio": 0.006,
                    "month_ratio": 0.001,
                    "batch_ratio": 0.003,
                    "batch_gap": 0.0015,
                    "batch": "BATCH-1",
                    "batch_date": "2026-06-22",
                    "lot_input_ratio": 0.55,
                    "ng_qty": 60,
                },
            ],
        ),
        _context(tmp_path),
    )

    assert result.success is True
    assert result.data["summary_counts"]["hl"] == 1
    assert result.data["hl_anomalies"][0]["defect_desc"] == "HIGH_SIGNAL"


def test_anomaly_monitor_reports_mild_map_concentration_for_selected_source_candidate(
    tmp_path: Path,
) -> None:
    detail_rows = []
    for index in range(8):
        detail_rows.append(
            {
                "prod_code": "M756",
                "defect_code": "CCS02",
                "defect_desc": "FOREIGN",
                "batch": "BATCH-1",
                "membrane_pos": "1F-E0",
                "output_panel_id": f"P{index}",
            }
        )
    for index in range(6):
        detail_rows.append(
            {
                "prod_code": "M756",
                "defect_code": "CCS02",
                "defect_desc": "FOREIGN",
                "batch": "BATCH-1",
                "membrane_pos": "2F-E0",
                "output_panel_id": f"Q{index}",
            }
        )
    for index in range(15):
        detail_rows.append(
            {
                "prod_code": "M756",
                "defect_code": "CCS02",
                "defect_desc": "FOREIGN",
                "batch": "BATCH-1",
                "membrane_pos": f"{index:02d}-A0",
                "output_panel_id": f"R{index}",
            }
        )

    result = tool.run(
        AnomalyMonitorRequest(
            report_date="2026-06-22",
            initial_rows=[
                {
                    "source_table": "hl_data",
                    "prod_code": "M756",
                    "defect_desc": "FOREIGN",
                    "defect_code": "CCS02",
                    "oper_group": "CT",
                    "ratio": 0.0051,
                    "month_ratio": 0.0022,
                    "batch_ratio": 0.0028,
                    "batch_gap": 0.0013,
                    "batch": "BATCH-1",
                    "batch_date": "2026-06-22",
                    "lot_input_ratio": 0.55,
                    "ng_qty": 63,
                }
            ],
            detail_rows=detail_rows,
        ),
        _context(tmp_path),
    )

    assert result.success is True
    assert result.data["summary_counts"]["hl"] == 1
    notice_text = result.data["notice_drafts"][0]["text"]
    assert "MAP较集中" in notice_text
    assert "1FE0" in notice_text
    assert "2FE0" in notice_text


def test_anomaly_monitor_only_ct_occurrence_station_can_be_final_hl(tmp_path: Path) -> None:
    result = tool.run(
        AnomalyMonitorRequest(
            report_date="2026-06-15",
            product_models=["C550"],
            initial_rows=[
                {
                    "prod_code": "C550",
                    "defect_desc": "MVI_ONLY",
                    "defect_code": "D101",
                    "oper_group": "MVI",
                    "ratio": 0.01,
                    "month_ratio": 0.001,
                    "batch_ratio": 0.02,
                    "batch": "BATCH-1",
                    "batch_date": "2026-06-15",
                    "lot_input_ratio": 0.55,
                    "ng_qty": 60,
                },
                {
                    "prod_code": "C550",
                    "defect_desc": "CT_DEFECT",
                    "defect_code": "D102",
                    "oper_group": "CT",
                    "occurrence_station": "MVI",
                    "ratio": 0.01,
                    "month_ratio": 0.001,
                    "batch_ratio": 0.02,
                    "batch": "BATCH-1",
                    "batch_date": "2026-06-15",
                    "lot_input_ratio": 0.55,
                    "ng_qty": 60,
                },
            ],
            batch_history_rows=[
                {
                    "prod_code": "C550",
                    "defect_desc": "MVI_ONLY",
                    "oper_group": "CT",
                    "ratio": 0.001,
                },
                {
                    "prod_code": "C550",
                    "defect_desc": "CT_DEFECT",
                    "oper_group": "CT",
                    "ratio": 0.001,
                },
            ],
        ),
        _context(tmp_path),
    )

    assert result.success is True
    assert result.data["summary_counts"]["hl"] == 1
    verdicts_by_defect = {
        verdict["row"]["defect_desc"]: verdict for verdict in result.data["verdicts"]
    }
    assert verdicts_by_defect["MVI_ONLY"]["decision"] == "skipped"
    assert verdicts_by_defect["CT_DEFECT"]["decision"] == "HL"
    assert "MVI" not in result.data["notice_drafts"][0]["text"]
    assert "CT" in result.data["notice_drafts"][0]["text"]


def test_anomaly_monitor_detects_hl_candidates_and_writes_artifacts(tmp_path: Path) -> None:
    request = AnomalyMonitorRequest(
        report_date="2026-06-01",
        product_models=["M678"],
        initial_rows=[
            {
                "TYPE": "批次首发",
                "prod_code": "M678",
                "defect_desc": "暗点",
                "defect_code": "D001",
                "oper_group": "MVI",
                "ratio": 0.015,
                "month_ratio": 0.005,
                "week_ratio": 0.008,
                "batch_ratio": 0.02,
                "batch": "B20260601",
                "batch_date": "2026-06-01",
                "lot_input_ratio": 0.31,
                "batch_gap": 0.012,
                "ng_qty": 30,
                "interface_time": "2026-06-01 07:30",
                "owner": "张健",
            },
            {
                "TYPE": "批次首发",
                "prod_code": "M678",
                "defect_desc": "线不良",
                "defect_code": "D002",
                "oper_group": "CT",
                "ratio": 0.02,
                "month_ratio": 0.01,
                "week_ratio": 0.012,
                "batch_ratio": 0.04,
                "batch": "B20260601",
                "batch_date": "2026-06-01",
                "lot_input_ratio": 0.31,
                "batch_gap": 0.025,
                "ng_qty": 45,
                "interface_time": "2026-06-01 07:30",
                "owner": "王工",
            },
            {
                "prod_code": "M678",
                "defect_desc": "产出不足",
                "defect_code": "D003",
                "oper_group": "CT",
                "batch_ratio": 0.10,
                "batch": "B20260601",
                "batch_date": "2026-06-01",
                "lot_input_ratio": 0.20,
                "ng_qty": 99,
            },
            {
                "prod_code": "M678",
                "defect_desc": "已HL",
                "defect_code": "D004",
                "oper_group": "CT",
                "batch_ratio": 0.10,
                "batch": "B20260601",
                "batch_date": "2026-06-01",
                "lot_input_ratio": 0.31,
                "ng_qty": 99,
            },
        ],
        detail_rows=[
            {
                "prod_code": "M678",
                "defect_code": "D001",
                "defect_desc": "暗点",
                "batch": "B20260601",
                "lot_id": "LOT-A",
                "sheet_id": "S1",
                "membrane_pos": "R1-C1",
            }
            for _ in range(18)
        ]
        + [
            {
                "prod_code": "M678",
                "defect_code": "D001",
                "defect_desc": "暗点",
                "batch": "B20260601",
                "lot_id": f"LOT-{index}",
                "sheet_id": f"S{index}",
                "membrane_pos": f"R{index}-C{index}",
            }
            for index in range(2, 8)
        ],
        batch_history_rows=[
            {
                "prod_code": "M678",
                "defect_desc": "线不良",
                "oper_group": "CT",
                "date_value": "2026-05-28",
                "ratio": 0.010,
                "lot_input_ratio": 0.96,
            },
            {
                "prod_code": "M678",
                "defect_desc": "线不良",
                "oper_group": "CT",
                "date_value": "2026-05-29",
                "ratio": 0.012,
                "lot_input_ratio": 0.97,
            },
            {
                "prod_code": "M678",
                "defect_desc": "线不良",
                "oper_group": "CT",
                "date_value": "2026-05-30",
                "ratio": 0.011,
                "lot_input_ratio": 0.98,
            },
            {
                "prod_code": "M678",
                "defect_desc": "已HL",
                "oper_group": "CT",
                "date_value": "2026-05-30",
                "ratio": 0.010,
                "lot_input_ratio": 0.98,
            },
        ],
        ct_exception_rows=[
            {
                "prod_code": "M678",
                "defect_desc": "已HL",
                "batch": "B20260601",
                "batch_date": "2026-06-01",
                "hl_time": "2026-06-01 08:00",
                "concentration_signature": "",
            }
        ],
    )

    result = tool.run(request, _context(tmp_path))

    assert result.success is True
    assert result.data["summary_counts"] == {
        "total": 4,
        "hl": 1,
        "skipped": 3,
        "blocked": 0,
        "true_anomaly": 1,
        "station_over_spec": 0,
    }
    assert [item["defect_desc"] for item in result.data["hl_anomalies"]] == ["线不良"]
    assert result.data["verdicts"][0]["decision"] == "skipped"
    assert result.data["verdicts"][0]["decision_reason"] == "发生站点非CT"
    assert result.data["verdicts"][1]["spec_result"]["exceeds_spec"] is True
    assert result.data["verdicts"][2]["decision"] == "skipped"
    assert result.data["verdicts"][2]["decision_reason"] == "基础筛选未通过"
    assert result.data["verdicts"][3]["decision"] == "skipped"
    assert result.data["verdicts"][3]["decision_reason"] == "基础筛选未通过"
    assert "【产品型号】M678" in result.data["notice_drafts"][0]["text"]
    assert "线不良" in result.data["notice_drafts"][0]["text"]
    assert {artifact.kind for artifact in result.artifacts} == {"json", "markdown"}
    for artifact in result.artifacts:
        assert artifact.path.exists()


def test_anomaly_monitor_reports_missing_initial_rows(tmp_path: Path) -> None:
    result = tool.run(
        AnomalyMonitorRequest(source_files={"data_source_dir": tmp_path / "missing"}),
        _context(tmp_path),
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "anomaly_monitor.input.missing_initial_rows"
    assert result.error.recoverable is True


def test_anomaly_monitor_does_not_use_ct_exception_as_daily_candidate_source(tmp_path: Path) -> None:
    ct_source = tmp_path / "ct_exception.json"
    ct_source.write_text(
        json.dumps(
            [
                {
                    "\u901a\u62a5\u65e5\u671f": "2026-06-03 09:30:00",
                    "\u4ea7\u54c1": "M678",
                    "\u4e0d\u826f": "S\u5411\u4eae\u7ebf",
                    "\u4e0d\u826f\u7ad9\u70b9": "CT",
                    "\u65e5\u826f\u635f": "3.2%",
                    "\u5f53\u6708": "0.8%",
                    "\u5f53\u5468": "1.2%",
                    "\u672c\u6279\u6b21": "1.8%",
                    "\u5f02\u5e38\u901a\u62a5": "\u57fa\u7840\u5206\u6790-Map A1\u805a\u96c6",
                    "\u72b6\u6001": "Open",
                },
                {
                    "\u901a\u62a5\u65e5\u671f": "2026-06-03 10:30:00",
                    "\u4ea7\u54c1": "M678",
                    "\u4e0d\u826f": "\u5f69\u6591Mura",
                    "\u4e0d\u826f\u7ad9\u70b9": "MVI",
                    "\u65e5\u826f\u635f": "4.9%",
                    "\u5f53\u6708": "0.7%",
                    "\u5f53\u5468": "2.1%",
                    "\u672c\u6279\u6b21": "1.7%",
                    "\u5f02\u5e38\u901a\u62a5": "\u57fa\u7840\u5206\u6790-Lot L3\u96c6\u4e2d",
                    "\u72b6\u6001": "Open",
                },
                {
                    "\u901a\u62a5\u65e5\u671f": "2026-05-30 09:30:00",
                    "\u4ea7\u54c1": "M678",
                    "\u4e0d\u826f": "S\u5411\u4eae\u7ebf",
                    "\u4e0d\u826f\u7ad9\u70b9": "CT",
                    "\u65e5\u826f\u635f": "0.5%",
                    "\u5f53\u6708": "0.5%",
                    "\u5f53\u5468": "0.5%",
                    "\u672c\u6279\u6b21": "0.4%",
                    "\u72b6\u6001": "Close",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = tool.run(
        AnomalyMonitorRequest(
            report_date="2026-06-15",
            product_models=["M678"],
            source_files={
                "daily_anomaly_initial": tmp_path / "missing_initial.xlsx",
                "ct_exception": ct_source,
                "ct_map_ng": tmp_path / "missing_map_ng.xlsx",
            },
        ),
        _context(tmp_path),
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "anomaly_monitor.input.missing_initial_rows"
    assert not any("CT良率异常波动管理表作为当日异常初筛候选源" in warning for warning in result.warnings)


def test_anomaly_monitor_skips_v_agent_push_without_endpoint(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("YIELD_REPORT_V_AGENT_WEBHOOK_URL", raising=False)

    def fail_post(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("V-Agent POST should not run without endpoint")

    monkeypatch.setattr(v_agent_client.requests, "post", fail_post)

    result = tool.run(
        AnomalyMonitorRequest(
            write_ledgers=True,
            push_notifications=True,
            initial_rows=[
                {
                    "prod_code": "M678",
                    "defect_desc": "线不良",
                    "oper_group": "CT",
                    "batch_ratio": 0.04,
                    "batch": "B20260601",
                    "batch_date": "2026-06-01",
                    "lot_input_ratio": 0.31,
                }
            ],
        ),
        _context(tmp_path),
    )

    assert result.success is True
    assert "台账写入尚未启用" in result.warnings
    assert result.data["notification_delivery"]["status"] == "skipped"
    message_path = Path(result.data["latest_message_cache"]["message_path"])
    assert message_path.exists()
    assert "HL" in message_path.read_text(encoding="utf-8")
    assert any("YIELD_REPORT_V_AGENT_WEBHOOK_URL" in warning for warning in result.warnings)


def test_anomaly_monitor_posts_hl_notice_to_v_agent(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_post(
        url: str,
        *,
        json: dict[str, Any],
        headers: dict[str, str],
        timeout: float,
    ) -> _FakeVAgentResponse:
        calls.append(
            {
                "url": url,
                "json": json,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return _FakeVAgentResponse()

    monkeypatch.setenv("YIELD_REPORT_V_AGENT_WEBHOOK_URL", "https://v-agent.example/hooks/hl")
    monkeypatch.setenv("YIELD_REPORT_V_AGENT_TOKEN", "secret-token")
    monkeypatch.setenv("YIELD_REPORT_V_AGENT_TIMEOUT_SECONDS", "3")
    monkeypatch.setattr(v_agent_client.requests, "post", fake_post)

    result = tool.run(
        AnomalyMonitorRequest(
            report_date="2026-06-22",
            push_notifications=True,
            initial_rows=[
                {
                    "source_table": "hl_data",
                    "prod_code": "M678",
                    "defect_desc": "LINE_BAD",
                    "defect_code": "D002",
                    "oper_group": "CT",
                    "ratio": 0.02,
                    "month_ratio": 0.01,
                    "batch_ratio": 0.04,
                    "batch": "B20260622",
                    "batch_date": "2026-06-22",
                    "lot_input_ratio": 0.31,
                    "batch_gap": 0.025,
                    "ng_qty": 45,
                    "interface_time": "2026-06-22 07:30",
                    "owner": "owner-a",
                }
            ],
        ),
        _context(tmp_path),
    )

    assert result.success is True
    assert result.data["summary_counts"]["hl"] == 1
    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == "https://v-agent.example/hooks/hl"
    assert call["headers"]["Authorization"] == "Bearer secret-token"
    assert call["timeout"] == 3
    posted = call["json"]
    assert posted["event_type"] == "yield_report.hl_anomaly"
    assert posted["run_id"] == "anomaly-run"
    assert posted["summary_counts"]["hl"] == 1
    assert posted["notice_drafts"][0]["product_model"] == "M678"
    assert "LINE_BAD" in posted["message"]
    message_path = Path(result.data["latest_message_cache"]["message_path"])
    assert "LINE_BAD" in message_path.read_text(encoding="utf-8")
    assert result.data["notification_delivery"] == {
        "requested": True,
        "status": "sent",
        "success": True,
        "endpoint_host": "v-agent.example",
        "status_code": 202,
        "response_text": "accepted",
        "error": "",
        "skipped_reason": "",
    }
