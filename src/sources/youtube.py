from __future__ import annotations

from datetime import date
from typing import Any

import httpx

from src.date_utils import is_within_date_range, to_iso
from src.models import FeedbackRecord
from src.quality import apply_quality, passes_prefilter
from src.source_utils import candidate_limit_for, effective_usable_target, should_collect_candidates, trim_to_target_usable


YOUTUBE_BASE_URL = "https://www.googleapis.com/youtube/v3"


def collect_youtube(
    api_key: str | None,
    searches: list[str],
    from_date: date,
    to_date: date,
    limit: int,
    min_words: int,
    candidate_limit: int | None = None,
    videos_per_query: int = 5,
    client: httpx.Client | None = None,
) -> tuple[list[FeedbackRecord], list[str]]:
    if not api_key:
        return [], ["YouTube API key is not configured."]

    records: list[FeedbackRecord] = []
    errors: list[str] = []
    seen: set[str] = set()
    max_candidates = candidate_limit_for(candidate_limit)
    usable_target = effective_usable_target(limit, max_candidates)
    owns_client = client is None
    http = client or httpx.Client(timeout=30.0)
    try:
        for query in searches:
            if not should_collect_candidates(records, max_candidates):
                break
            videos = search_videos(http, api_key, query, videos_per_query, errors)
            for video in videos:
                if not should_collect_candidates(records, max_candidates):
                    break
                comments = collect_video_comments(
                    http=http,
                    api_key=api_key,
                    video=video,
                    query=query,
                    from_date=from_date,
                    to_date=to_date,
                    max_records=min(max_candidates - len(records), max(25, usable_target)),
                    min_words=min_words,
                    errors=errors,
                )
                for record in comments:
                    key = f"{record.source}:{record.external_id}"
                    if key not in seen:
                        seen.add(key)
                        records.append(record)
    finally:
        if owns_client:
            http.close()

    return trim_to_target_usable(records, usable_target, max_records=max_candidates), errors


def search_videos(http: httpx.Client, api_key: str, query: str, max_results: int, errors: list[str]) -> list[dict[str, Any]]:
    try:
        response = http.get(
            f"{YOUTUBE_BASE_URL}/search",
            params={
                "part": "snippet",
                "type": "video",
                "q": query,
                "maxResults": min(50, max(1, max_results)),
                "key": api_key,
            },
        )
        response.raise_for_status()
    except Exception as exc:
        errors.append(f"youtube video search '{query}': {exc}")
        return []

    payload = response.json()
    videos: list[dict[str, Any]] = []
    for item in payload.get("items", []):
        video_id = item.get("id", {}).get("videoId")
        if video_id:
            snippet = item.get("snippet", {})
            videos.append(
                {
                    "video_id": video_id,
                    "title": snippet.get("title"),
                    "description": snippet.get("description"),
                    "channel_title": snippet.get("channelTitle"),
                    "published_at": to_iso(snippet.get("publishedAt")),
                }
            )
    return videos


def collect_video_comments(
    http: httpx.Client,
    api_key: str,
    video: dict[str, Any],
    query: str,
    from_date: date,
    to_date: date,
    max_records: int,
    min_words: int,
    errors: list[str],
) -> list[FeedbackRecord]:
    records: list[FeedbackRecord] = []
    seen_comments: set[str] = set()
    video_id = str(video.get("video_id") or "")
    context_text = youtube_quality_context(query, video)
    if not video_id:
        return records
    for order in ["relevance", "time"]:
        page_token: str | None = None
        while len(records) < max_records:
            params = {
                "part": "snippet,replies",
                "videoId": video_id,
                "maxResults": min(100, max_records - len(records)),
                "order": order,
                "textFormat": "plainText",
                "key": api_key,
            }
            if page_token:
                params["pageToken"] = page_token
            try:
                response = http.get(f"{YOUTUBE_BASE_URL}/commentThreads", params=params)
                if response.status_code in {403, 404}:
                    break
                response.raise_for_status()
            except Exception as exc:
                errors.append(f"youtube comments '{video_id}' ({order}): {exc}")
                break

            payload = response.json()
            for item in payload.get("items", []):
                for comment in comments_from_thread(item):
                    if len(records) >= max_records:
                        break
                    record = normalize_comment(comment, query, video)
                    if record.external_id in seen_comments:
                        continue
                    seen_comments.add(record.external_id)
                    created_at = record.created_at
                    if not is_within_date_range(created_at, from_date, to_date, include_missing=False):
                        continue
                    if not passes_prefilter(record, min_words, context_text=context_text):
                        continue
                    records.append(apply_quality(record, min_words, context_text=context_text))

            page_token = payload.get("nextPageToken")
            if not page_token:
                break
    return records


def comments_from_thread(item: dict[str, Any]) -> list[dict[str, Any]]:
    comments: list[dict[str, Any]] = []
    top_level_comment = item.get("snippet", {}).get("topLevelComment", {})
    top_level = top_level_comment.get("snippet")
    if top_level:
        comments.append(top_level | {"comment_id": top_level_comment.get("id"), "thread_reply_count": item.get("snippet", {}).get("totalReplyCount")})
    for reply in item.get("replies", {}).get("comments", []):
        snippet = reply.get("snippet")
        if snippet:
            comments.append(snippet | {"comment_id": reply.get("id")})
    return comments


def youtube_quality_context(query: str, video: dict[str, Any]) -> str:
    return " ".join(
        str(part or "")
        for part in [
            query,
            video.get("title"),
            video.get("description"),
            video.get("channel_title"),
        ]
    )


def normalize_comment(comment: dict[str, Any], query: str, video: dict[str, Any]) -> FeedbackRecord:
    comment_id = str(comment.get("comment_id") or comment.get("textOriginal", "")[:80])
    video_id = str(video.get("video_id") or "")
    return FeedbackRecord(
        source="youtube",
        source_query=query,
        external_id=f"youtube_comment:{comment_id}",
        created_at=to_iso(comment.get("publishedAt") or comment.get("updatedAt")),
        author=comment.get("authorDisplayName"),
        text=str(comment.get("textOriginal") or comment.get("textDisplay") or ""),
        url=f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}",
        language=None,
        metadata={
            "video_id": video_id,
            "video_title": video.get("title"),
            "video_channel": video.get("channel_title"),
            "video_published_at": video.get("published_at"),
            "like_count": comment.get("likeCount"),
            "thread_reply_count": comment.get("thread_reply_count"),
        },
    )
