from __future__ import annotations

from math import ceil

from src.defaults import DEFAULT_RAW_OVERFETCH_MULTIPLIER
from src.models import FeedbackRecord


def usable_count(records: list[FeedbackRecord]) -> int:
    return sum(1 for record in records if record.quality_passed)


def raw_limit_for(target_usable: int, multiplier: int = DEFAULT_RAW_OVERFETCH_MULTIPLIER) -> int:
    return max(target_usable, target_usable * multiplier)


def candidate_limit_for(requested_candidates: int | None = None, default: int | None = None) -> int:
    if requested_candidates is None:
        requested_candidates = default if default is not None else 100
    return max(1, int(requested_candidates))


def overfetch_candidate_limit(target_usable: int, multiplier: float = 2.0, maximum: int = 2000) -> int:
    target = max(1, int(target_usable))
    cap = max(target, int(maximum))
    return max(target, min(cap, ceil(target * max(1.0, float(multiplier)))))


def effective_usable_target(target_usable: int, candidate_limit: int) -> int:
    return max(1, min(int(target_usable), int(candidate_limit)))


def target_tolerance_floor(target_usable: int, tolerance: float = 0.95) -> int:
    target = max(1, int(target_usable))
    return max(1, ceil(target * min(1.0, max(0.0, float(tolerance)))))


def materially_under_target(actual_usable: int, target_usable: int, tolerance: float = 0.95) -> bool:
    return int(actual_usable) < target_tolerance_floor(target_usable, tolerance)


def should_continue(records: list[FeedbackRecord], target_usable: int, max_raw: int | None = None) -> bool:
    if usable_count(records) >= target_usable:
        return False
    if max_raw is not None and len(records) >= max_raw:
        return False
    return True


def should_collect_candidates(records: list[FeedbackRecord], candidate_limit: int) -> bool:
    return len(records) < candidate_limit


def trim_to_target_usable(
    records: list[FeedbackRecord],
    target_usable: int,
    max_records: int | None = None,
) -> list[FeedbackRecord]:
    usable = [record for record in records if record.quality_passed]
    filtered = [record for record in records if not record.quality_passed]
    usable.sort(key=lambda record: (record.signal_weight, record.word_count), reverse=True)
    selected_usable = usable[:target_usable]
    record_limit = max_records or target_usable * 2
    return selected_usable + filtered[: max(0, min(len(filtered), record_limit - len(selected_usable)))]
