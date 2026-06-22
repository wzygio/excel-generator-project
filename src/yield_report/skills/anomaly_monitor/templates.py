"""HL notice draft rendering for anomaly-monitor results."""

from __future__ import annotations

from yield_report.skills.anomaly_monitor.models import AnomalyVerdict, NoticeDraft


def build_notice_draft(verdict: AnomalyVerdict) -> NoticeDraft:
    """Render a workbook-compatible HL notice draft."""
    row = verdict.row
    batch_date_short = _short_date(row.batch_date)
    batch_gap_text = _percent(row.batch_gap)
    analysis_text = verdict.concentration.text
    if (
        not verdict.concentration.detected
        and verdict.spec_result.available
        and _is_no_concentration_text(analysis_text)
    ):
        analysis_text = verdict.spec_result.reason
    station = row.station
    lines = [
        f"【产品型号】{row.product_model}",
        f"【不良名称】{row.defect_desc}",
        f"【发生站点】{station}",
        f"【是否再发】{'是' if verdict.already_hl.matched else '否'}",
        f"【首次通报】{row.interface_time or '/'}",
        f"【基础分析】{analysis_text}",
        (
            f"【异常良损】当日良损{_percent(row.daily_loss)}，"
            f"当月良损{_percent(row.month_loss)}，"
            f"批次良损{_percent(row.batch_loss)}，"
            f"{batch_date_short}批次较上批次恶化{batch_gap_text}"
        ),
        "【异常原因】***",
        "【Inline监控】若已监控到：明确监控到的站点/RS Code/恶化比例；若没监控到，给出后续 Inline监控如何优化的方案",
        "【是否止血】***",
        f"【影响范围】影响数量 {row.ng_qty} pcs",
        "【改善措施】要求有工艺改善的落地措施，无措施时需要当天上良率会进行汇报",
        f"【整合对接】{row.owner or '***'}",
        "【责任部门】***",
        "【责任科室】***",
    ]
    return NoticeDraft(
        row_id=row.row_id,
        product_model=row.product_model,
        defect_desc=row.defect_desc,
        text="\n".join(lines),
    )


def _percent(value: float | None) -> str:
    if value is None:
        return "0.00%"
    return f"{value * 100:.2f}%"


def _short_date(value: str) -> str:
    parts = str(value or "").replace("/", "-").split("-")
    if len(parts) >= 3:
        return f"{parts[1]}/{parts[2][:2]}"
    return str(value or "")


def _is_no_concentration_text(value: str) -> bool:
    return "\u65e0\u660e\u663e" in str(value)
