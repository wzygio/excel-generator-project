"""V-Agent webhook delivery for yield-report notifications."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from yield_report.agent.spec_model import RunContext

DEFAULT_TIMEOUT_SECONDS = 10.0
LATEST_MESSAGE_FILENAME = "latest_hl_anomaly_message.txt"
LATEST_PAYLOAD_FILENAME = "latest_hl_anomaly_payload.json"


@dataclass(frozen=True)
class VAgentConfig:
    """Runtime configuration for a V-Agent webhook endpoint."""

    endpoint_url: str
    token: str = ""
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    extra_headers: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> VAgentConfig | None:
        endpoint_url = os.getenv("YIELD_REPORT_V_AGENT_WEBHOOK_URL", "").strip()
        if not endpoint_url:
            return None
        return cls(
            endpoint_url=endpoint_url,
            token=os.getenv("YIELD_REPORT_V_AGENT_TOKEN", "").strip(),
            timeout_seconds=_env_float(
                "YIELD_REPORT_V_AGENT_TIMEOUT_SECONDS",
                DEFAULT_TIMEOUT_SECONDS,
            ),
            extra_headers=_env_headers(),
        )

    @property
    def endpoint_host(self) -> str:
        return urlparse(self.endpoint_url).netloc or "configured-endpoint"

    def request_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            **self.extra_headers,
        }
        if self.token and not any(key.lower() == "authorization" for key in headers):
            headers["Authorization"] = f"Bearer {self.token}"
        return headers


@dataclass(frozen=True)
class VAgentDeliveryResult:
    """Sanitized delivery status safe to expose in SkillResult.data."""

    requested: bool
    status: str
    success: bool = False
    endpoint_host: str = ""
    status_code: int | None = None
    response_text: str = ""
    error: str = ""
    skipped_reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "requested": self.requested,
            "status": self.status,
            "success": self.success,
            "endpoint_host": self.endpoint_host,
            "status_code": self.status_code,
            "response_text": self.response_text,
            "error": self.error,
            "skipped_reason": self.skipped_reason,
        }


def send_hl_anomaly_notification(
    skill_payload: dict[str, Any],
    *,
    context: RunContext,
    config: VAgentConfig | None = None,
) -> VAgentDeliveryResult:
    """Post formatted HL anomalies to V-Agent when configured."""

    config = config or VAgentConfig.from_env()
    if config is None:
        return VAgentDeliveryResult(
            requested=True,
            status="skipped",
            skipped_reason="YIELD_REPORT_V_AGENT_WEBHOOK_URL is not configured",
        )

    notice_drafts = _list_of_dicts(skill_payload.get("notice_drafts"))
    if not notice_drafts:
        return VAgentDeliveryResult(
            requested=True,
            status="skipped",
            endpoint_host=config.endpoint_host,
            skipped_reason="no HL notice drafts",
        )

    outbound_payload = build_v_agent_payload(
        skill_payload,
        context=context,
        notice_drafts=notice_drafts,
    )
    try:
        response = requests.post(
            config.endpoint_url,
            json=outbound_payload,
            headers=config.request_headers(),
            timeout=config.timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        return VAgentDeliveryResult(
            requested=True,
            status="failed",
            endpoint_host=config.endpoint_host,
            status_code=status_code,
            error=str(exc),
        )

    return VAgentDeliveryResult(
        requested=True,
        status="sent",
        success=True,
        endpoint_host=config.endpoint_host,
        status_code=response.status_code,
        response_text=_short_text(response.text),
    )


def build_v_agent_payload(
    skill_payload: dict[str, Any],
    *,
    context: RunContext,
    notice_drafts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the JSON body expected by the V-Agent HTTP trigger."""

    notice_drafts = notice_drafts or _list_of_dicts(skill_payload.get("notice_drafts"))
    return {
        "schema_version": 1,
        "event_type": "yield_report.hl_anomaly",
        "run_id": context.run_id,
        "report_date": skill_payload.get("report_date"),
        "message": render_hl_message(skill_payload, notice_drafts=notice_drafts),
        "summary_counts": skill_payload.get("summary_counts") or {},
        "notice_drafts": notice_drafts,
        "hl_anomalies": skill_payload.get("hl_anomalies") or [],
        "real_anomalies": skill_payload.get("real_anomalies") or [],
        "source_evidence": skill_payload.get("source_evidence") or {},
        "source_files": skill_payload.get("source_files") or {},
        "artifact_hint": _artifact_hint(context),
    }


def write_latest_hl_message_cache(
    skill_payload: dict[str, Any],
    *,
    context: RunContext,
) -> dict[str, str]:
    """Write the latest HL text for V-Agent pull-mode HTTP requests."""

    message = render_hl_message(skill_payload)
    message_path = _latest_path(
        env_name="YIELD_REPORT_V_AGENT_LATEST_MESSAGE_PATH",
        context=context,
        filename=LATEST_MESSAGE_FILENAME,
    )
    payload_path = _latest_path(
        env_name="YIELD_REPORT_V_AGENT_LATEST_PAYLOAD_PATH",
        context=context,
        filename=LATEST_PAYLOAD_FILENAME,
    )
    message_path.parent.mkdir(parents=True, exist_ok=True)
    message_path.write_text(message, encoding="utf-8")
    payload_path.write_text(
        json.dumps(skill_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "message_path": str(message_path),
        "payload_path": str(payload_path),
    }


def render_hl_message(
    skill_payload: dict[str, Any],
    *,
    notice_drafts: list[dict[str, Any]] | None = None,
) -> str:
    """Render a compact text message that V-Agent can forward to a group."""

    counts = skill_payload.get("summary_counts") or {}
    notice_drafts = notice_drafts or _list_of_dicts(skill_payload.get("notice_drafts"))
    if not notice_drafts:
        return "\n".join(
            [
                "本次异常监控未识别到需要推送的 HL 异常。",
                f"报告日期: {skill_payload.get('report_date') or '-'}",
                (
                    "统计: "
                    f"total={counts.get('total', 0)}, "
                    f"HL={counts.get('hl', 0)}, "
                    f"skipped={counts.get('skipped', 0)}, "
                    f"blocked={counts.get('blocked', 0)}"
                ),
            ]
        )
    lines = [
        "HL 异常通报",
        f"报告日期: {skill_payload.get('report_date') or '-'}",
        (
            "统计: "
            f"total={counts.get('total', 0)}, "
            f"HL={counts.get('hl', 0)}, "
            f"true_anomaly={counts.get('true_anomaly', 0)}, "
            f"station_over_spec={counts.get('station_over_spec', 0)}"
        ),
    ]
    for index, draft in enumerate(notice_drafts, start=1):
        title_parts = [
            str(draft.get("product_model") or "").strip(),
            str(draft.get("defect_desc") or "").strip(),
        ]
        title = " / ".join(part for part in title_parts if part) or f"draft-{index}"
        lines.extend(["", f"--- HL {index}: {title} ---", str(draft.get("text") or "").strip()])
    return "\n".join(lines).strip()


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_headers() -> dict[str, str]:
    raw = os.getenv("YIELD_REPORT_V_AGENT_HEADERS_JSON", "").strip()
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items() if item is not None}


def _short_text(value: str, limit: int = 500) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _artifact_hint(context: RunContext) -> dict[str, str]:
    output_dir = Path(context.output_dir)
    return {
        "output_dir": str(output_dir),
        "markdown": str(output_dir / "anomaly_monitor_summary.md"),
        "json": str(output_dir / "anomaly_monitor_result.json"),
    }


def _latest_path(*, env_name: str, context: RunContext, filename: str) -> Path:
    configured = os.getenv(env_name, "").strip()
    if configured:
        return Path(configured)
    return Path(context.workspace) / "output" / filename
