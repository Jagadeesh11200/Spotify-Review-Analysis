from __future__ import annotations

from datetime import date
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from src.config import AppSettings
from src.defaults import (
    DEFAULT_MIN_WORDS,
    DEFAULT_CANDIDATE_RECORDS_PER_SOURCE,
    DEFAULT_REDDIT_COMMENT_DEPTH,
    DEFAULT_REDDIT_COMMENTS_PER_POST,
    DEFAULT_TARGET_USABLE_PER_SOURCE,
    DEFAULT_YOUTUBE_VIDEOS_PER_QUERY,
)
from src.models import FeedbackRecord, IngestionResult, SourceResult
from src.sources.app_store import collect_app_store
from src.sources.apify_client import ApifyClient
from src.sources.play_store import collect_play_store
from src.sources.reddit import collect_reddit
from src.sources.spotify_community import collect_spotify_community
from src.sources.youtube import collect_youtube
from src.storage import create_session_dir, save_manifest, save_source_records
from src.source_utils import candidate_limit_for, effective_usable_target


Collector = Callable[[], tuple[list[FeedbackRecord], list[str]]]


def run_ingestion(
    settings: AppSettings,
    from_date: date,
    to_date: date,
    searches_by_source: dict[str, list[str]],
    enabled_sources: list[str],
    limit_per_source: int = DEFAULT_TARGET_USABLE_PER_SOURCE,
    candidate_limit_per_source: int = DEFAULT_CANDIDATE_RECORDS_PER_SOURCE,
    min_words: int = DEFAULT_MIN_WORDS,
    output_base_dir: str | Path = "data/raw",
) -> IngestionResult:
    session_id, session_dir = create_session_dir(output_base_dir)
    date_range = {"from": from_date.isoformat(), "to": to_date.isoformat()}
    candidate_limit_per_source = candidate_limit_for(candidate_limit_per_source)
    usable_target_per_source = effective_usable_target(limit_per_source, candidate_limit_per_source)

    def apify() -> ApifyClient:
        return ApifyClient(settings.apify_api_keys)

    collectors: dict[str, Collector] = {
        "app_store": lambda: collect_app_store(
            from_date=from_date,
            to_date=to_date,
            target_usable=usable_target_per_source,
            min_words=min_words,
            candidate_limit=candidate_limit_per_source,
        ),
        "play_store": lambda: collect_play_store(
            from_date=from_date,
            to_date=to_date,
            target_usable=usable_target_per_source,
            min_words=min_words,
            candidate_limit=candidate_limit_per_source,
        ),
        "reddit": lambda: collect_reddit(
            client=apify(),
            searches=searches_by_source.get("reddit", []),
            from_date=from_date,
            to_date=to_date,
            limit=usable_target_per_source,
            min_words=min_words,
            candidate_limit=candidate_limit_per_source,
            comment_depth=DEFAULT_REDDIT_COMMENT_DEPTH,
            comments_per_post=DEFAULT_REDDIT_COMMENTS_PER_POST,
        ),
        "youtube": lambda: collect_youtube(
            api_key=settings.youtube_api_key,
            searches=searches_by_source.get("youtube", []),
            from_date=from_date,
            to_date=to_date,
            limit=usable_target_per_source,
            min_words=min_words,
            candidate_limit=candidate_limit_per_source,
            videos_per_query=DEFAULT_YOUTUBE_VIDEOS_PER_QUERY,
        ),
        "spotify_community": lambda: collect_spotify_community(
            searches=searches_by_source.get("spotify_community", []),
            from_date=from_date,
            to_date=to_date,
            limit=usable_target_per_source,
            min_words=min_words,
            candidate_limit=candidate_limit_per_source,
        ),
    }

    def collect_source(source: str) -> SourceResult:
        searches = searches_by_source.get(source, [])
        if source not in collectors:
            return save_source_records(session_dir, source, [], searches, date_range, ["Unknown source."])
        if source not in {"app_store", "play_store"} and not searches:
            return save_source_records(session_dir, source, [], searches, date_range, ["No searches configured."])
        collector = collectors[source]
        try:
            records, errors = collector()
        except Exception as exc:
            records, errors = [], [str(exc)]
        return save_source_records(session_dir, source, records, searches, date_range, errors)

    results_by_source: dict[str, SourceResult] = {}
    with ThreadPoolExecutor(max_workers=min(5, max(1, len(enabled_sources)))) as executor:
        futures = {executor.submit(collect_source, source): source for source in enabled_sources}
        for future in as_completed(futures):
            source = futures[future]
            results_by_source[source] = future.result()
    source_results = [results_by_source[source] for source in enabled_sources if source in results_by_source]

    manifest_path = save_manifest(
        session_dir=session_dir,
        session_id=session_id,
        source_results=source_results,
        config={
            "date_range": date_range,
            "target_usable_per_source": usable_target_per_source,
            "candidate_limit_per_source": candidate_limit_per_source,
            "configured_usable_target_per_source": limit_per_source,
            "min_words": min_words,
            "enabled_sources": enabled_sources,
        },
    )
    return IngestionResult(
        session_id=session_id,
        session_dir=str(session_dir),
        manifest_path=manifest_path,
        source_results=source_results,
    )
