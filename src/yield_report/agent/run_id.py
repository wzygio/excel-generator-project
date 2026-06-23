"""Run id generation for Agent-owned Spec runs."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime

ALLOWED_RUN_ID_SOURCES = {"agent", "api", "smoke", "test", "ui"}
ALLOWED_CAPABILITIES = {
    "anomaly-monitor",
    "daily-report",
    "data-analysis",
    "report-download",
    "yield-trend",
}

_RUN_ID_PATTERN = re.compile(
    r"^(?P<source>[a-z0-9]+)-(?P<capability>[a-z0-9]+(?:-[a-z0-9]+)*)-"
    r"(?P<timestamp>\d{8}-\d{6})$"
)


class RunIdFactory:
    """Create and validate business-readable run ids."""

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or datetime.now

    def create(self, *, source: str, capability: str) -> str:
        normalized_source = normalize_source(source)
        normalized_capability = normalize_capability(capability)
        timestamp = self._clock().strftime("%Y%m%d-%H%M%S")
        return f"{normalized_source}-{normalized_capability}-{timestamp}"

    @staticmethod
    def validate(run_id: str) -> None:
        if run_id.startswith("run-"):
            raise ValueError("legacy run-* ids are not allowed")
        match = _RUN_ID_PATTERN.match(run_id)
        if match is None:
            raise ValueError(
                "run_id must follow <source>-<capability>-<YYYYMMDD-HHMMSS>"
            )
        normalize_source(match.group("source"))
        normalize_capability(match.group("capability"))


def normalize_source(source: str) -> str:
    normalized = _normalize_segment(source)
    if normalized not in ALLOWED_RUN_ID_SOURCES:
        raise ValueError(f"Unsupported run source: {source}")
    return normalized


def normalize_capability(capability: str) -> str:
    normalized = _normalize_segment(capability)
    if normalized not in ALLOWED_CAPABILITIES:
        raise ValueError(f"Unsupported capability: {capability}")
    return normalized


def _normalize_segment(value: str) -> str:
    normalized = str(value or "").strip().lower().replace("_", "-")
    normalized = re.sub(r"[^a-z0-9-]+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    if not normalized:
        raise ValueError("run_id segment cannot be empty")
    return normalized
