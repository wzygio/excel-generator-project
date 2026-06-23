from __future__ import annotations

from datetime import datetime

import pytest

from yield_report.agent.run_id import RunIdFactory, normalize_capability


def test_run_id_factory_generates_source_capability_timestamp() -> None:
    factory = RunIdFactory(clock=lambda: datetime(2026, 6, 23, 14, 30, 15))

    run_id = factory.create(source="agent", capability="daily_report")

    assert run_id == "agent-daily-report-20260623-143015"


def test_run_id_factory_rejects_legacy_run_prefix() -> None:
    with pytest.raises(ValueError, match="legacy"):
        RunIdFactory.validate("run-20260623-143015")


def test_run_id_factory_rejects_unknown_capability() -> None:
    factory = RunIdFactory(clock=lambda: datetime(2026, 6, 23, 14, 30, 15))

    with pytest.raises(ValueError, match="Unsupported capability"):
        factory.create(source="agent", capability="freeform")


def test_normalize_capability_accepts_skill_style_names() -> None:
    assert normalize_capability("anomaly_monitor") == "anomaly-monitor"
    assert normalize_capability("daily_report") == "daily-report"
