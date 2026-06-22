"""Deterministic anomaly-monitor rule engine."""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import date, datetime
from typing import Any

from yield_report.skills.anomaly_monitor.models import (
    AlreadyHlResult,
    AnomalyVerdict,
    ConcentrationEvidence,
    NormalizedAnomalyRow,
    SpecResult,
)

BATCH_LOSS_THRESHOLD = 0.001
LOT_OUTPUT_THRESHOLD = 0.20
MULTIPLIER_THRESHOLD = 0.30
NG_QTY_THRESHOLD = 20
TOP_1_CONCENTRATION_THRESHOLD = 0.50
TOP_UNIT_FRACTION = 0.20
TOP_UNIT_CUMULATIVE_THRESHOLD = 0.80
SMALL_SAMPLE_TOP_1_THRESHOLD = 0.80
MILD_MAP_TOP2_THRESHOLD = 0.45
MILD_MAP_MIN_TOTAL = 20
HistoryIndex = dict[tuple[str, str], list[dict[str, Any]]]


def parse_ratio(value: Any) -> float:
    """Parse ratios stored as numbers, decimal strings, or percent strings."""
    if value is None:
        return 0.0
    if isinstance(value, int | float):
        if isinstance(value, float) and math.isnan(value):
            return 0.0
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return 0.0
    is_percent = text.endswith("%")
    if is_percent:
        text = text[:-1].strip()
    try:
        number = float(text)
    except ValueError:
        return 0.0
    if is_percent or abs(number) > 1:
        return number / 100
    return number


def parse_number(value: Any) -> float:
    """Parse ordinary numeric values without percentage normalization."""
    if value is None:
        return 0.0
    if isinstance(value, int | float):
        if isinstance(value, float) and math.isnan(value):
            return 0.0
        return float(value)
    text = str(value).strip().replace(",", "").rstrip("%")
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def normalize_anomaly_row(raw: dict[str, Any], index: int) -> NormalizedAnomalyRow:
    product = _first_text(raw, "prod_code", "产品型号", "产品")
    defect_desc = _first_text(raw, "defect_desc", "不良名称", "不良")
    defect_code = _first_text(raw, "defect_code", "DefectCode", "不良代码")
    station = _first_text(raw, "oper_group", "发生站点", "不良站点", "站点").upper()
    batch = _first_text(raw, "batch", "批次", "date_value")
    batch_date = _first_text(raw, "batch_date", "批次日期") or _date_from_batch(batch)
    daily_loss = parse_ratio(_first_value(raw, "ratio", "日良损", "daily_loss"))
    month_loss = parse_ratio(_first_value(raw, "month_ratio", "CT月", "当月", "monthly_loss"))
    batch_loss = parse_ratio(_first_value(raw, "batch_ratio", "本批次", "batch_loss"))
    multiplier = parse_ratio(_first_value(raw, "multiplier", "倍数"))
    if multiplier == 0 and month_loss != 0:
        multiplier = batch_loss / month_loss
    return NormalizedAnomalyRow(
        row_id=str(raw.get("row_id") or f"row-{index + 1}"),
        product_model=product,
        defect_desc=defect_desc,
        defect_code=defect_code,
        station=station,
        batch=batch,
        batch_date=batch_date,
        interface_time=_first_text(raw, "interface_time", "first_notice_time", "首次通报", "通报日期"),
        daily_loss=daily_loss,
        month_loss=month_loss,
        week_loss=parse_ratio(_first_value(raw, "week_ratio", "CT周", "当周", "weekly_loss")),
        batch_loss=batch_loss,
        batch_gap=parse_ratio(_first_value(raw, "batch_gap", "本批次-上批次")),
        batch_output_ratio=parse_ratio(
            _first_value(raw, "lot_input_ratio", "批次产出率", "batch_output_ratio")
        ),
        multiplier=multiplier,
        ng_qty=int(parse_number(_first_value(raw, "ng_qty", "不良数量"))),
        owner=_first_text(raw, "owner", "整合对接", "hl_owner"),
        raw=raw,
    )


class ConcentrationAnalyzer:
    """Provisional deterministic concentration analyzer ported from the template."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self._by_code_key: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        self._by_desc_key: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        for item in rows:
            prod = _first_text(item, "prod_code", "产品")
            batch = _first_text(item, "batch", "lot", "批次")
            code = _first_text(item, "defect_code", "不良代码")
            desc = _first_text(item, "defect_desc", "不良")
            if prod and batch and code:
                self._by_code_key.setdefault((prod, code, batch), []).append(item)
            if prod and batch and desc:
                self._by_desc_key.setdefault((prod, desc, batch), []).append(item)

    def analyze(self, row: NormalizedAnomalyRow) -> ConcentrationEvidence:
        text_evidence = _text_concentration_evidence(row)
        if text_evidence is not None:
            return text_evidence

        subset = self._matching_detail_rows(row)
        if not subset:
            return ConcentrationEvidence(text="Map/Lot无明显集中性")

        total = len(subset)
        report_parts: list[str] = []
        signatures: list[str] = []
        targets = [
            ("Lot", ["lot_id", "lot"]),
            ("Map", ["membrane_pos", "map", "膜位"]),
            ("Map", ["row_code", "行"]),
            ("Sheet", ["sheet_id", "sheet"]),
            ("Glass", ["glass_id", "glass"]),
            ("工单", ["work_order", "工单"]),
        ]
        for label, keys in targets:
            values = [_first_text(item, *keys) for item in subset]
            values = [value for value in values if value]
            if not values:
                continue
            counts = Counter(values)
            top = counts.most_common()
            top_1_count = top[0][1]
            top_1_ratio = top_1_count / total
            top_unit_count = _dynamic_top_unit_count(len(top))
            top_unit_ratio = sum(count for _, count in top[:top_unit_count]) / total
            is_concentrated = (
                (
                    total >= 20
                    and (
                        top_1_ratio >= TOP_1_CONCENTRATION_THRESHOLD
                        or top_unit_ratio >= TOP_UNIT_CUMULATIVE_THRESHOLD
                    )
                )
                or (0 < total < 20 and top_1_ratio >= SMALL_SAMPLE_TOP_1_THRESHOLD)
            )
            if not is_concentrated:
                continue
            candidates: list[str] = []
            for name, count in top[:10]:
                if count < 4:
                    continue
                if count < top_1_count * 0.4:
                    break
                candidates.append(str(name))
            if candidates:
                report_parts.append(f"{label}集中: {'/'.join(candidates)}")
                signatures.extend(candidates)

        if not report_parts:
            mild_map_text = _mild_map_concentration_text(subset)
            if mild_map_text:
                return ConcentrationEvidence(text=mild_map_text, signature=mild_map_text)
            return ConcentrationEvidence(text="Map/Lot无明显集中性")
        return ConcentrationEvidence(
            detected=True,
            text="；".join(report_parts),
            signature="|".join(signatures),
        )

    def _matching_detail_rows(self, row: NormalizedAnomalyRow) -> list[dict[str, Any]]:
        if row.defect_code:
            subset = self._by_code_key.get((row.product_model, row.defect_code, row.batch), [])
            if subset:
                return subset
        subset = self._by_desc_key.get((row.product_model, row.defect_desc, row.batch), [])
        if subset:
            return subset
        return [item for item in self.rows if _matches_detail_row(item, row)]


def _dynamic_top_unit_count(distinct_unit_count: int) -> int:
    if distinct_unit_count <= 0:
        return 0
    return max(1, math.floor(distinct_unit_count * TOP_UNIT_FRACTION))


def _mild_map_concentration_text(rows: list[dict[str, Any]]) -> str:
    valid_rows = [row for row in rows if _has_valid_output_panel(row)]
    if len(valid_rows) < MILD_MAP_MIN_TOTAL:
        return ""
    values = [_first_text(row, "membrane_pos", "map", "鑶滀綅") for row in valid_rows]
    values = [value for value in values if value]
    if not values:
        return ""
    top = Counter(values).most_common(2)
    if len(top) < 2:
        return ""
    top2_count = sum(count for _, count in top)
    if top2_count / len(valid_rows) < MILD_MAP_TOP2_THRESHOLD:
        return ""
    if any(count < 4 for _, count in top):
        return ""
    names = [_format_map_position(name) for name, _ in top]
    return f"MAP较集中: {'/'.join(names)}"


def _has_valid_output_panel(row: dict[str, Any]) -> bool:
    output_panel = _first_text(row, "output_panel_id")
    if output_panel and output_panel.lower() not in {"nan", "none"}:
        return True
    return parse_number(_first_value(row, "output_qty")) > 0


def _format_map_position(value: str) -> str:
    return str(value).replace("-", "").strip()


def evaluate_row(
    row: NormalizedAnomalyRow,
    *,
    concentration: ConcentrationEvidence,
    ct_exception_rows: list[dict[str, Any]],
    batch_history_rows: list[dict[str, Any]],
    history_index: HistoryIndex | None = None,
) -> AnomalyVerdict:
    threshold = LOT_OUTPUT_THRESHOLD
    gate_checks = {
        "batch_loss": row.batch_loss > BATCH_LOSS_THRESHOLD,
        "lot_output": row.batch_output_ratio > LOT_OUTPUT_THRESHOLD,
        "multiplier": row.multiplier > MULTIPLIER_THRESHOLD,
        "ng_qty": row.ng_qty > NG_QTY_THRESHOLD,
    }
    gate_passed = all(gate_checks.values())
    concentration_gate_passed = (
        concentration.detected
        and (gate_checks["batch_loss"] or row.daily_loss > BATCH_LOSS_THRESHOLD)
        and gate_checks["multiplier"]
        and gate_checks["ng_qty"]
    )
    warnings: list[str] = []
    already_hl = detect_already_hl(row, ct_exception_rows, concentration)
    spec_result = calculate_spec_result(row, batch_history_rows, history_index=history_index)

    if row.station != "CT":
        decision = "skipped"
        reason = "发生站点非CT"
    elif row.raw.get("source_table") == "hl_data" and not row.raw.get("_source_hl_selected"):
        decision = "skipped"
        reason = "非优先HL候选"
    elif row.raw.get("_source_hl_selected") and gate_passed:
        decision = "HL"
        reason = "源表HL初筛命中"
    elif concentration_gate_passed:
        decision = "HL"
        reason = "集中性命中"
    elif not gate_passed:
        decision = "skipped"
        reason = "基础筛选未通过"
    elif spec_result.available and spec_result.exceeds_spec:
        decision = "HL"
        reason = "超过CT历史上限"
    elif not spec_result.available:
        decision = "skipped"
        reason = "未超过CT历史上限"
    else:
        decision = "skipped"
        reason = "未超过CT历史上限"

    return AnomalyVerdict(
        row=row,
        batch_gate_passed=gate_passed,
        batch_gate_threshold=threshold,
        concentration=concentration,
        already_hl=already_hl,
        spec_result=spec_result,
        decision=decision,
        decision_reason=reason,
        warnings=[warning for warning in warnings if warning],
    )


def detect_already_hl(
    row: NormalizedAnomalyRow,
    ct_exception_rows: list[dict[str, Any]],
    concentration: ConcentrationEvidence,
) -> AlreadyHlResult:
    current_date = _parse_date(row.batch_date)
    for record in ct_exception_rows:
        if _first_text(record, "row_id") == row.row_id:
            continue
        if _first_text(record, "prod_code", "产品") != row.product_model:
            continue
        if _first_text(record, "defect_desc", "不良") != row.defect_desc:
            continue
        record_batch = _first_text(record, "batch", "批次", "date_value")
        if record_batch and record_batch == row.batch:
            return AlreadyHlResult(matched=True, reason="same_batch", matched_record=record)
        if current_date is None:
            continue
        record_date = _parse_date(_first_text(record, "batch_date", "通报日期", "hl_time"))
        if record_date is None or abs((current_date - record_date).days) >= 10:
            continue
        signature = _first_text(record, "concentration_signature", "基础分析", "异常通报")
        if concentration.detected and signature and (
            signature == concentration.signature or signature in concentration.text
        ):
            return AlreadyHlResult(
                matched=True,
                reason="within_10_days_same_concentration",
                matched_record=record,
            )
    return AlreadyHlResult()


def calculate_spec_result(
    row: NormalizedAnomalyRow,
    batch_history_rows: list[dict[str, Any]],
    *,
    history_index: HistoryIndex | None = None,
) -> SpecResult:
    if history_index is not None:
        matching = history_index.get((row.product_model, row.defect_desc), [])
    else:
        matching = [
            item
            for item in batch_history_rows
            if _first_text(item, "prod_code", "产品") == row.product_model
            and _first_text(item, "defect_desc", "不良") == row.defect_desc
        ]
    ct_matching = [
        item
        for item in matching
        if _first_text(item, "oper_group", "发生站点", "不良站点", "站点").upper() == "CT"
    ]
    selected = ct_matching or matching
    ratios = [parse_ratio(_first_value(item, "ratio", "ratio_fanel", "不良率")) for item in selected]
    spec_ratio = max(ratios) if ratios else 0.0
    return SpecResult(
        available=True,
        spec_ratio=spec_ratio,
        sample_count=len(selected),
        exceeds_spec=row.batch_loss > spec_ratio,
        reason=f"CT历史上限 {spec_ratio:.2%}",
    )


def build_history_index(batch_history_rows: list[dict[str, Any]]) -> HistoryIndex:
    index: HistoryIndex = {}
    for item in batch_history_rows:
        prod = _first_text(item, "prod_code", "产品")
        defect = _first_text(item, "defect_desc", "不良")
        if prod and defect:
            index.setdefault((prod, defect), []).append(item)
    return index


def _matches_detail_row(item: dict[str, Any], row: NormalizedAnomalyRow) -> bool:
    if _first_text(item, "prod_code", "产品") != row.product_model:
        return False
    batch = _first_text(item, "batch", "lot", "批次")
    if batch and batch != row.batch:
        return False
    code = _first_text(item, "defect_code", "不良代码")
    desc = _first_text(item, "defect_desc", "不良")
    return bool((row.defect_code and code == row.defect_code) or desc == row.defect_desc)


def _text_concentration_evidence(row: NormalizedAnomalyRow) -> ConcentrationEvidence | None:
    text = _first_text(row.raw, "concentration_text", "notice_text", "\u5f02\u5e38\u901a\u62a5")
    if not text:
        return None
    if "\u96c6\u4e2d" not in text and "\u805a\u96c6" not in text:
        return None
    snippets = [
        part.strip()
        for part in re.split(r"[\n\uff1b;]", text)
        if "\u96c6\u4e2d" in part or "\u805a\u96c6" in part
    ]
    evidence_text = "\uff1b".join(snippets[:3]) if snippets else text[:120]
    return ConcentrationEvidence(
        detected=True,
        text=evidence_text,
        signature=evidence_text,
    )


def _first_value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] not in {None, ""}:
            return row[key]
    return None


def _first_text(row: dict[str, Any], *keys: str) -> str:
    value = _first_value(row, *keys)
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value)).strip()
    return str(value).strip()


def _date_from_batch(batch: str) -> str:
    match = re.search(r"(20\d{2})(\d{2})(\d{2})", batch)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    match = re.search(r"(\d{2})/(\d{2})/(\d{2})", batch)
    if match:
        return f"20{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return ""


def _parse_date(value: str) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = text.replace("/", "-")
    if text.endswith("+00:00"):
        text = text[:-6]
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        pass
    match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if match:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    compact = re.search(r"(20\d{2})(\d{2})(\d{2})", text)
    if compact:
        return date(int(compact.group(1)), int(compact.group(2)), int(compact.group(3)))
    return None
