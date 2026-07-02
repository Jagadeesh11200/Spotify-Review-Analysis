from src.models import FeedbackRecord
from src.source_utils import (
    candidate_limit_for,
    effective_usable_target,
    materially_under_target,
    overfetch_candidate_limit,
    target_tolerance_floor,
    trim_to_target_usable,
)


def make_record(record_id: str, weight: float, passed: bool = True) -> FeedbackRecord:
    return FeedbackRecord(
        source="reddit",
        source_query="spotify",
        external_id=record_id,
        text="Spotify recommendations keep repeating songs and I want new discovery.",
        quality_passed=passed,
        signal_weight=weight,
        word_count=25,
    )


def test_trim_to_target_usable_keeps_highest_signal_records():
    records = [make_record("low", 1.0), make_record("high", 2.5), make_record("mid", 1.5)]

    trimmed = trim_to_target_usable(records, target_usable=2)

    assert [record.external_id for record in trimmed if record.quality_passed] == ["high", "mid"]


def test_trim_keeps_candidate_audit_records_up_to_candidate_limit():
    records = [
        make_record("usable-1", 2.5, True),
        make_record("usable-2", 2.0, True),
        make_record("filtered-1", 1.0, False),
        make_record("filtered-2", 1.0, False),
        make_record("filtered-3", 1.0, False),
    ]

    trimmed = trim_to_target_usable(records, target_usable=1, max_records=3)

    assert [record.external_id for record in trimmed] == ["usable-1", "filtered-1", "filtered-2"]


def test_candidate_limit_is_the_true_requested_maximum():
    assert candidate_limit_for(requested_candidates=5) == 5
    assert candidate_limit_for(requested_candidates=100) == 100
    assert candidate_limit_for(requested_candidates=None) == 100


def test_usable_target_is_capped_by_candidate_maximum():
    assert effective_usable_target(target_usable=50, candidate_limit=100) == 50
    assert effective_usable_target(target_usable=500, candidate_limit=100) == 100
    assert effective_usable_target(target_usable=50, candidate_limit=5) == 5


def test_ui_overfetch_candidate_limit_buffers_meaningful_target():
    assert overfetch_candidate_limit(target_usable=500, multiplier=2, maximum=2000) == 1000
    assert overfetch_candidate_limit(target_usable=5, multiplier=2, maximum=2000) == 10
    assert overfetch_candidate_limit(target_usable=1500, multiplier=2, maximum=2000) == 2000


def test_material_undercollection_allows_five_percent_variation():
    assert target_tolerance_floor(500) == 475
    assert not materially_under_target(actual_usable=480, target_usable=500)
    assert materially_under_target(actual_usable=474, target_usable=500)
