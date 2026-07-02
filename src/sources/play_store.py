from __future__ import annotations

from datetime import date
from typing import Any

from google_play_scraper import Sort, reviews

from src.date_utils import is_within_date_range, to_iso
from src.defaults import SPOTIFY_PLAY_STORE_APP_ID
from src.models import FeedbackRecord
from src.quality import apply_quality, passes_prefilter
from src.source_utils import candidate_limit_for, effective_usable_target, should_collect_candidates, trim_to_target_usable


def collect_play_store(
    from_date: date,
    to_date: date,
    target_usable: int,
    min_words: int,
    candidate_limit: int | None = None,
    app_id: str = SPOTIFY_PLAY_STORE_APP_ID,
    reviews_func=reviews,
) -> tuple[list[FeedbackRecord], list[str]]:
    records: list[FeedbackRecord] = []
    errors: list[str] = []
    seen: set[str] = set()
    continuation_token = None
    max_candidates = candidate_limit_for(candidate_limit)
    usable_target = effective_usable_target(target_usable, max_candidates)

    while should_collect_candidates(records, max_candidates):
        try:
            batch, continuation_token = reviews_func(
                app_id,
                lang="en",
                country="us",
                sort=Sort.NEWEST,
                count=min(200, max_candidates - len(records)),
                continuation_token=continuation_token,
            )
        except Exception as exc:
            errors.append(f"play store reviews: {exc}")
            break

        if not batch:
            break

        for item in batch:
            if not should_collect_candidates(records, max_candidates):
                break
            record = normalize_review(item)
            if not is_within_date_range(record.created_at, from_date, to_date, include_missing=False):
                continue
            if not passes_prefilter(record, min_words):
                continue
            record = apply_quality(record, min_words)
            key = f"{record.source}:{record.external_id}"
            if key in seen:
                continue
            seen.add(key)
            records.append(record)

        if not continuation_token:
            break

    return trim_to_target_usable(records, usable_target, max_records=max_candidates), errors


def normalize_review(item: dict[str, Any]) -> FeedbackRecord:
    review_id = str(item.get("reviewId") or item.get("at") or item.get("content", "")[:80])
    score = item.get("score")
    rating = float(score) if isinstance(score, (int, float)) else None
    return FeedbackRecord(
        source="play_store",
        source_query="spotify_play_store_reviews",
        external_id=f"play_store:{review_id}",
        created_at=to_iso(item.get("at")),
        author=item.get("userName"),
        text=str(item.get("content") or ""),
        url=f"https://play.google.com/store/apps/details?id={SPOTIFY_PLAY_STORE_APP_ID}&reviewId={review_id}",
        rating=rating,
        language="en",
        metadata={
            "app_id": SPOTIFY_PLAY_STORE_APP_ID,
            "thumbs_up_count": item.get("thumbsUpCount"),
            "review_created_version": item.get("reviewCreatedVersion"),
        },
    )
