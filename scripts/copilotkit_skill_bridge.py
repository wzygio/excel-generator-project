"""JSON bridge from the CopilotKit UI to project Skill tools."""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from dotenv import load_dotenv

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "src"))
sys.path.insert(0, str(WORKSPACE))
load_dotenv(WORKSPACE / ".env")

from yield_report.agent.spec_model import RunContext, SkillResult  # noqa: E402
from yield_report.skills.anomaly_monitor import tool as anomaly_monitor_tool  # noqa: E402
from yield_report.skills.anomaly_monitor.models import (  # noqa: E402
    AnomalyMonitorMode,
    AnomalyMonitorRequest,
)
from yield_report.skills.daily_report import tool as daily_report_tool  # noqa: E402
from yield_report.skills.daily_report.models import DailyReportRequest  # noqa: E402
from yield_report.skills.data_analysis import tool as data_analysis_tool  # noqa: E402
from yield_report.skills.data_analysis.models import DataAnalysisRequest  # noqa: E402
from yield_report.skills.report_download import tool as report_download_tool  # noqa: E402
from yield_report.skills.report_download.models import ReportDownloadRequest  # noqa: E402

DEFAULT_REPORT_OUTPUT_NAME = "daily_report_output.xlsx"


def main() -> None:
    payload = _read_payload()
    captured_stdout = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured_stdout):
            response = dispatch(payload)
        extra_stdout = captured_stdout.getvalue().strip()
        if extra_stdout:
            response.setdefault("diagnostics", {})["stdout"] = extra_stdout
    except Exception as exc:
        response = {
            "success": False,
            "skill_name": payload.get("module", "unknown"),
            "summary": f"CopilotKit bridge failed: {exc}",
            "artifacts": [],
            "data": {},
            "warnings": [],
            "error": {
                "code": "copilotkit_bridge.execution.failed",
                "message": str(exc),
                "recoverable": True,
                "details": {"traceback": traceback.format_exc()},
            },
            "memory_updates": [],
        }
    json.dump(response, sys.stdout, ensure_ascii=False, default=str)


def dispatch(payload: dict[str, Any]) -> dict[str, Any]:
    module = str(payload.get("module") or "").strip()
    action = str(payload.get("action") or "run").strip()

    if module == "data_analysis" and action in {"confirm_memory", "reject_memory", "correct_memory"}:
        record_id = str(payload.get("record_id") or "").strip()
        if not record_id:
            raise ValueError("record_id is required for memory feedback")
        if action == "confirm_memory":
            result = data_analysis_tool.confirm_memory(record_id)
            summary = f"已确认记忆: {record_id}"
        elif action == "correct_memory":
            correction = str(payload.get("correction") or payload.get("correction_text") or "").strip()
            if not correction:
                raise ValueError("correction is required for memory correction")
            result = data_analysis_tool.correct_memory(record_id, correction)
            summary = f"已记录修正: {record_id}"
        else:
            result = data_analysis_tool.reject_memory(record_id)
            summary = f"已拒绝记忆: {record_id}"
        return {
            "success": True,
            "skill_name": "data_analysis",
            "summary": summary,
            "artifacts": [],
            "data": {"record_id": record_id, "result": _jsonable(result)},
            "warnings": [],
            "error": None,
            "memory_updates": [],
        }

    context = _new_run_context()
    raw_options = payload.get("options")
    options: dict[str, Any] = raw_options if isinstance(raw_options, dict) else {}
    query = str(payload.get("query") or "").strip()

    if module == "report_download":
        raw_filters = options.get("filters")
        filters: dict[str, Any] = raw_filters if isinstance(raw_filters, dict) else {}
        result = report_download_tool.run(
            ReportDownloadRequest(
                user_query=query,
                report_type=options.get("report_type"),
                start_date=options.get("start_date"),
                end_date=options.get("end_date"),
                product_models=_string_list(options.get("product_models")),
                month_count=_optional_int(options.get("month_count"))
                or _optional_int(filters.get("month_count")),
                filters=filters,
                prefer_decrypted=bool(options.get("prefer_decrypted", False)),
            ),
            context,
        )
    elif module == "data_analysis":
        result = data_analysis_tool.run(
            DataAnalysisRequest(
                question=query,
                file_path=_optional_path(options.get("file_path")),
                file_name=_optional_string(options.get("file_name")),
                product_models=_string_list(options.get("product_models")),
                metrics=_string_list(options.get("metrics")) or [],
                analysis_intent=_optional_string(options.get("analysis_intent")) or "",
                confirmed_memory_ids=_string_list(options.get("confirmed_memory_ids")) or [],
            ),
            context,
        )
    elif module == "daily_report":
        result = daily_report_tool.run(
            DailyReportRequest(
                report_date=_optional_string(options.get("report_date")),
                product_models=_string_list(options.get("product_models")),
                sections=_string_list(options.get("sections")) or [],
                output_name=_optional_string(options.get("output_name"))
                or DEFAULT_REPORT_OUTPUT_NAME,
                output_dir=Path(options.get("output_dir") or context.output_dir),
                emit_intermediate_artifacts=bool(options.get("emit_intermediate_artifacts", True)),
                use_llm_polishing=bool(options.get("use_llm_polishing", False)),
            ),
            context,
        )
    elif module == "anomaly_monitor":
        result = anomaly_monitor_tool.run(
            AnomalyMonitorRequest(
                report_date=_optional_string(options.get("report_date")),
                product_models=_string_list(options.get("product_models")),
                source_files=_path_map(options.get("source_files")),
                mode=_anomaly_mode(options.get("mode")),
                write_ledgers=bool(options.get("write_ledgers", False)),
                push_notifications=bool(options.get("push_notifications", False)),
                rules_profile=_optional_string(options.get("rules_profile")) or "default",
                emit_intermediate_artifacts=bool(
                    options.get("emit_intermediate_artifacts", True)
                ),
            ),
            context,
        )
    else:
        raise ValueError(f"Unsupported module: {module}")

    return _serialize_result(result)


def _read_payload() -> dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Bridge payload must be a JSON object")
    return data


def _new_run_context() -> RunContext:
    run_id = datetime.now().strftime("copilotkit-%Y%m%d-%H%M%S")
    output_dir = Path(os.environ.get("YIELD_REPORT_OUTPUT_DIR", WORKSPACE / "output"))
    return RunContext(
        run_id=run_id,
        workspace=WORKSPACE,
        output_dir=output_dir,
    )


def _serialize_result(result: SkillResult) -> dict[str, Any]:
    return result.model_dump(mode="json")


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False, default=str)
        return value
    except TypeError:
        return str(value)


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _optional_path(value: Any) -> Path | None:
    text = _optional_string(value)
    return Path(text) if text else None


def _path_map(value: Any) -> dict[str, Path]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, Path] = {}
    for key, raw_path in value.items():
        path = _optional_path(raw_path)
        if path is not None:
            result[str(key)] = path
    return result


def _anomaly_mode(value: Any) -> AnomalyMonitorMode:
    mode = _optional_string(value) or "detect"
    if mode not in {"detect", "draft_notice", "record", "full"}:
        raise ValueError(f"Unsupported anomaly_monitor mode: {mode}")
    return cast(AnomalyMonitorMode, mode)


def _string_list(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        items = [item.strip() for item in value.replace("，", ",").split(",")]
    elif isinstance(value, list):
        items = [str(item).strip() for item in value]
    else:
        items = [str(value).strip()]
    cleaned = [item for item in items if item]
    return cleaned or None


if __name__ == "__main__":
    main()
