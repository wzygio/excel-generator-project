from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from yield_report.core.business_time import (
    default_batch_start_date,
    effective_daily_yield_end_date,
    effective_report_end_date,
)

TZ = ZoneInfo("Asia/Shanghai")


def test_effective_report_end_date_uses_yesterday_before_cutoff() -> None:
    def clock() -> datetime:
        return datetime(2026, 6, 2, 9, 59, tzinfo=TZ)

    assert effective_report_end_date(clock) == date(2026, 6, 1)


def test_effective_report_end_date_uses_today_after_cutoff() -> None:
    def clock() -> datetime:
        return datetime(2026, 6, 2, 10, 0, tzinfo=TZ)

    assert effective_report_end_date(clock) == date(2026, 6, 2)


def test_default_batch_start_date_is_wall_clock_today_minus_90_days() -> None:
    def clock() -> datetime:
        return datetime(2026, 6, 2, 9, 0, tzinfo=TZ)

    assert default_batch_start_date(clock) == date(2026, 3, 4)


def test_daily_yield_end_date_honors_historical_report_date() -> None:
    def clock() -> datetime:
        return datetime(2026, 6, 2, 9, 0, tzinfo=TZ)

    assert effective_daily_yield_end_date("2026-05-30", clock) == date(2026, 5, 30)
    assert effective_daily_yield_end_date("2026-06-02", clock) == date(2026, 6, 1)
