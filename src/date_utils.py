from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any

from dateutil import parser


def parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime.combine(value, time.min)
    elif isinstance(value, (int, float)):
        timestamp = value / 1000 if value > 10_000_000_000 else value
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    else:
        try:
            dt = parser.parse(str(value))
        except (TypeError, ValueError, OverflowError):
            return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_iso(value: Any) -> str | None:
    dt = parse_datetime(value)
    return dt.isoformat() if dt else None


def is_within_date_range(value: Any, from_date: date, to_date: date, include_missing: bool = False) -> bool:
    dt = parse_datetime(value)
    if dt is None:
        return include_missing
    start = datetime.combine(from_date, time.min, tzinfo=timezone.utc)
    end = datetime.combine(to_date, time.max, tzinfo=timezone.utc)
    return start <= dt <= end
