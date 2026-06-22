"""Implementation for the anomaly_monitor skill."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from yield_report.agent.spec_model import ArtifactRef, RunContext, SkillError, SkillResult
from yield_report.infrastructure.v_agent_client import (
    send_hl_anomaly_notification,
    write_latest_hl_message_cache,
)
from yield_report.skills.anomaly_monitor.analyzers import (
    ConcentrationAnalyzer,
    build_history_index,
    evaluate_row,
    normalize_anomaly_row,
)
from yield_report.skills.anomaly_monitor.models import AnomalyMonitorRequest, AnomalyVerdict
from yield_report.skills.anomaly_monitor.sources import load_anomaly_sources
from yield_report.skills.anomaly_monitor.templates import build_notice_draft

TOOL_NAME = "anomaly_monitor"
PRODUCT_MODEL_PATTERN = re.compile(r"(?<![A-Z0-9])[A-Z]\d{3,4}(?![A-Z0-9])", re.IGNORECASE)


def execute_anomaly_monitor(
    request: AnomalyMonitorRequest,
    *,
    context: RunContext,
) -> SkillResult:
    """Run the deterministic anomaly-monitor workflow."""
    sources, warnings = load_anomaly_sources(request, workspace=context.workspace)
    initial_rows = sources.get("daily_anomaly_initial", [])
    if not initial_rows:
        return SkillResult(
            skill_name=TOOL_NAME,
            success=False,
            summary="异常监控缺少当日异常初筛表数据。",
            warnings=warnings,
            error=SkillError(
                code="anomaly_monitor.input.missing_initial_rows",
                message="缺少 daily_anomaly_initial/initial_rows，无法执行异常识别。",
                recoverable=True,
                details={"source_alias": "daily_anomaly_initial"},
            ),
        )

    if request.write_ledgers:
        warnings.append("台账写入尚未启用")

    product_filter = set(request.product_models or [])
    normalized_rows = [
        normalize_anomaly_row(raw, index)
        for index, raw in enumerate(initial_rows)
    ]
    if product_filter:
        normalized_rows = [
            row for row in normalized_rows if _matches_product_filter(row.product_model, product_filter)
        ]
    _mark_selected_hl_source_rows(normalized_rows)

    concentrator = ConcentrationAnalyzer(sources.get("ct_concentration", []))
    history_index = build_history_index(sources.get("batch_history", []))
    verdicts: list[AnomalyVerdict] = []
    for row in normalized_rows:
        concentration = concentrator.analyze(row)
        verdict = evaluate_row(
            row,
            concentration=concentration,
            ct_exception_rows=sources.get("ct_exception", []),
            batch_history_rows=sources.get("batch_history", []),
            history_index=history_index,
        )
        warnings.extend(verdict.warnings)
        verdicts.append(verdict)

    drafts = [
        build_notice_draft(verdict)
        for verdict in verdicts
        if verdict.decision == "HL"
    ]
    payload = _payload(
        request=request,
        sources=sources,
        verdicts=verdicts,
        drafts=drafts,
        warnings=warnings,
        source_files={key: str(value) for key, value in request.source_files.items()},
    )
    if request.push_notifications:
        delivery = send_hl_anomaly_notification(payload, context=context)
        payload["notification_delivery"] = delivery.as_dict()
        if delivery.status == "skipped":
            warnings.append(f"V-Agent push skipped: {delivery.skipped_reason}")
        elif delivery.status == "failed":
            warnings.append(f"V-Agent push failed: {delivery.error}")
    else:
        payload["notification_delivery"] = {
            "requested": False,
            "status": "disabled",
            "success": False,
        }
    payload["latest_message_cache"] = write_latest_hl_message_cache(payload, context=context)
    payload["warnings"] = list(dict.fromkeys(warnings))
    artifacts = _write_artifacts(payload, context.output_dir)
    return SkillResult(
        skill_name=TOOL_NAME,
        success=True,
        summary=(
            f"异常监控完成: HL {payload['summary_counts']['hl']} 条, "
            f"跳过 {payload['summary_counts']['skipped']} 条, "
            f"阻断 {payload['summary_counts']['blocked']} 条"
        ),
        artifacts=artifacts,
        data=payload,
        warnings=list(dict.fromkeys(warnings)),
    )


def _mark_selected_hl_source_rows(rows: list[Any]) -> None:
    grouped: dict[str, list[Any]] = {}
    for row in rows:
        row.raw.pop("_source_hl_selected", None)
        if row.raw.get("source_table") != "hl_data" or row.station != "CT":
            continue
        grouped.setdefault(row.product_model, []).append(row)

    for candidates in grouped.values():
        selected = max(
            candidates,
            key=lambda row: (
                row.daily_loss,
                row.batch_loss,
                row.batch_gap,
                row.ng_qty,
            ),
        )
        selected.raw["_source_hl_selected"] = True


def _matches_product_filter(product_model: str, product_filter: set[str]) -> bool:
    product = str(product_model or "").strip().upper()
    if product in product_filter:
        return True
    product_parts = set(PRODUCT_MODEL_PATTERN.findall(product))
    return bool(product_parts & product_filter)


def _payload(
    *,
    request: AnomalyMonitorRequest,
    sources: dict[str, list[dict[str, Any]]],
    verdicts: list[AnomalyVerdict],
    drafts: list[Any],
    warnings: list[str],
    source_files: dict[str, str],
) -> dict[str, Any]:
    verdict_payload = []
    for verdict in verdicts:
        item = verdict.model_dump(mode="json")
        item["anomaly_type"] = _anomaly_type(verdict)
        verdict_payload.append(item)
    hl_anomalies = [
        verdict.row.model_dump(mode="json")
        for verdict in verdicts
        if verdict.decision == "HL"
    ]
    real_anomalies = [
        verdict.row.model_dump(mode="json")
        for verdict in verdicts
        if verdict.decision == "HL"
    ]
    blocked_items = [
        verdict.model_dump(mode="json")
        for verdict in verdicts
        if verdict.decision == "blocked"
    ]
    summary_counts = {
        "total": len(verdicts),
        "hl": sum(1 for verdict in verdicts if verdict.decision == "HL"),
        "skipped": sum(1 for verdict in verdicts if verdict.decision == "skipped"),
        "blocked": sum(1 for verdict in verdicts if verdict.decision == "blocked"),
        "true_anomaly": sum(
            1
            for verdict in verdicts
            if verdict.decision == "HL" and _anomaly_type(verdict) == "真实异常"
        ),
        "station_over_spec": sum(
            1
            for verdict in verdicts
            if verdict.decision == "HL" and _anomaly_type(verdict) == "当站超规"
        ),
    }
    return {
        "report_date": request.report_date,
        "mode": request.mode,
        "rules_profile": request.rules_profile,
        "summary_counts": summary_counts,
        "verdicts": verdict_payload,
        "hl_anomalies": hl_anomalies,
        "real_anomalies": real_anomalies,
        "notice_drafts": [draft.model_dump(mode="json") for draft in drafts],
        "blocked_items": blocked_items,
        "source_files": source_files,
        "source_summary": _source_summary(sources),
        "source_evidence": _source_evidence(verdicts),
        "warnings": list(dict.fromkeys(warnings)),
    }


def _anomaly_type(verdict: AnomalyVerdict) -> str:
    if verdict.decision != "HL":
        return "阻断" if verdict.decision == "blocked" else "非异常"
    return "真实异常" if verdict.row.station == "CT" else "当站超规"


def _source_summary(sources: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for alias in sorted(sources):
        rows = sources.get(alias, [])
        source_tables = sorted(
            {
                str(row.get("source_table"))
                for row in rows
                if row.get("source_table")
            }
        )
        dates = sorted(
            {
                date_value
                for row in rows
                if (date_value := _first_text(row, "batch_date", "date_value", "interface_time", "通报日期"))
            }
        )
        normalized_dates = sorted(
            {
                date_value[:10]
                for date_value in dates
                if len(date_value) >= 10
            }
        )
        summary[alias] = {
            "row_count": len(rows),
            "dates": normalized_dates[-10:],
            "date_range": {
                "start": normalized_dates[0] if normalized_dates else "",
                "end": normalized_dates[-1] if normalized_dates else "",
            },
            "source_tables": source_tables,
        }
    return summary


def _source_evidence(verdicts: list[AnomalyVerdict]) -> dict[str, list[dict[str, Any]]]:
    return {
        "real_anomaly_rows": [
            _verdict_source_evidence(verdict)
            for verdict in verdicts
            if verdict.decision == "HL"
        ],
    }


def _verdict_source_evidence(verdict: AnomalyVerdict) -> dict[str, Any]:
    row = verdict.row
    raw = row.raw
    raw_ct = raw.get("raw_ct_exception")
    raw_ct = raw_ct if isinstance(raw_ct, dict) else {}
    return {
        "row_id": row.row_id,
        "source_table": _first_text(raw, "source_table"),
        "product_model": row.product_model,
        "defect_desc": row.defect_desc,
        "station": row.station,
        "batch_date": row.batch_date,
        "interface_time": row.interface_time,
        "daily_loss": _stable_ratio(row.daily_loss),
        "batch_loss": _stable_ratio(row.batch_loss),
        "decision_reason": verdict.decision_reason,
        "notice_text": _first_text(raw, "notice_text", "异常通报") or _first_text(raw_ct, "异常通报"),
        "reply_text": _first_text(raw, "reply_text", "回复")
        or _first_text(raw_ct, "工艺整合&工艺 回复的改善及挽救进展"),
        "status": _first_text(raw, "status", "状态") or _first_text(raw_ct, "状态"),
        "owner": row.owner,
    }


def _first_text(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is None or value == "":
            continue
        if isinstance(value, float) and value.is_integer():
            return str(int(value)).strip()
        return str(value).strip()
    return ""


def _stable_ratio(value: float) -> float:
    return round(value, 10)


def _write_artifacts(payload: dict[str, Any], output_dir: Path) -> list[ArtifactRef]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "anomaly_monitor_result.json"
    markdown_path = output_dir / "anomaly_monitor_summary.md"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown_path.write_text(_render_markdown(payload), encoding="utf-8")
    return [
        ArtifactRef(
            kind="json",
            path=json_path,
            description="anomaly_monitor structured result",
            metadata={"skill": TOOL_NAME},
        ),
        ArtifactRef(
            kind="markdown",
            path=markdown_path,
            description="anomaly_monitor summary",
            metadata={"skill": TOOL_NAME},
        ),
    ]


def _render_markdown(payload: dict[str, Any]) -> str:
    counts = payload["summary_counts"]
    lines = [
        "# 异常监控识别结果",
        "",
        f"- 总数: {counts['total']}",
        f"- HL: {counts['hl']}",
        f"- 跳过: {counts['skipped']}",
        f"- 阻断: {counts['blocked']}",
        "",
        "## 源数据",
        "",
    ]
    for alias, summary in payload.get("source_summary", {}).items():
        dates = ", ".join(summary.get("dates", [])[-3:])
        suffix = f" ({dates})" if dates else ""
        lines.append(f"- {alias}: {summary.get('row_count', 0)} 行{suffix}")
    lines.extend([
        "",
        "## HL 通报草稿",
        "",
    ])
    drafts = payload.get("notice_drafts", [])
    if not drafts:
        lines.append("无")
    for draft in drafts:
        lines.extend([
            f"### {draft['product_model']} - {draft['defect_desc']}",
            "",
            draft["text"],
            "",
        ])
    warnings = payload.get("warnings") or []
    if warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    return "\n".join(lines)
