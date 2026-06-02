"""Shared business-date rules for report acquisition."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

BUSINESS_TZ = ZoneInfo("Asia/Shanghai")
DAILY_REPORT_CUTOFF_HOUR = 10
BATCH_LOOKBACK_DAYS = 90


Clock = Callable[[], datetime]


def business_now(clock: Clock | None = None) -> datetime:
    """Return the current business datetime in Asia/Shanghai."""
    current = clock() if clock else datetime.now(BUSINESS_TZ)
    if current.tzinfo is None:
        return current.replace(tzinfo=BUSINESS_TZ)
    return current.astimezone(BUSINESS_TZ)


def business_today(clock: Clock | None = None) -> date:
    """Return today's date in the business timezone."""
    return business_now(clock).date()


def effective_report_end_date(clock: Clock | None = None) -> date:
    """Return the effective report end date.

    Daily FineReport data is considered complete only after 10:00. Before then,
    the effective end date remains yesterday.
    """
    current = business_now(clock)
    end_date = current.date()
    if current.time() < time(DAILY_REPORT_CUTOFF_HOUR, 0):
        end_date -= timedelta(days=1)
    return end_date


def default_batch_start_date(clock: Clock | None = None) -> date:
    """Return the default batch-yield start date: wall-clock today minus 90 days."""
    return business_today(clock) - timedelta(days=BATCH_LOOKBACK_DAYS)


def effective_daily_yield_end_date(
    requested_report_date: str | date | None = None,
    clock: Clock | None = None,
) -> date:
    """Resolve the daily-yield end date for a daily-report run.

    Historical requested dates are honored. If the requested date is today while
    the business cutoff has not passed, use yesterday because today's daily data
    is not complete yet.
    """
    if requested_report_date is None:
        return effective_report_end_date(clock)

    if isinstance(requested_report_date, date):
        requested = requested_report_date
    else:
        requested = date.fromisoformat(str(requested_report_date))

    today = business_today(clock)
    effective = effective_report_end_date(clock)
    if requested >= today and effective < today:
        return effective
    return requested
