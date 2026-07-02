from __future__ import annotations

from datetime import date
import re
import time
from typing import Any
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
import httpx

from src.date_utils import is_within_date_range, to_iso
from src.models import FeedbackRecord
from src.quality import apply_quality, passes_prefilter
from src.source_utils import (
    candidate_limit_for,
    effective_usable_target,
    materially_under_target,
    should_collect_candidates,
    target_tolerance_floor,
    trim_to_target_usable,
    usable_count,
)
from src.sources.apify_client import ApifyClient


REDDIT_ACTOR_ID = "trudax/reddit-scraper-lite"
REDDIT_SEARCH_SUBREDDITS = ["spotify", "truespotify"]
REDDIT_USER_AGENT = "Mozilla/5.0 SpotifyReviewAnalysisDemo/1.0"
POINTS_RE = re.compile(r"(-?\d+)\s+points?", re.IGNORECASE)
COMMENTS_RE = re.compile(r"(\d+)\s+comments?", re.IGNORECASE)
REDDIT_DISCOVERY_FOCUS_TERMS = [
    "recommend",
    "recommendation",
    "algorithm",
    "discover new",
    "discover music",
    "discover weekly",
    "release radar",
    "daily mix",
    "ai dj",
    "radio",
    "autoplay",
    "same song",
    "same songs",
    "repeat",
    "repeating",
    "new music",
    "similar artist",
    "taste profile",
    "genre",
    "shuffle",
]
REDDIT_PROBLEM_BEHAVIOR_TERMS = [
    "bad",
    "suck",
    "sucks",
    "stuck",
    "same",
    "repeat",
    "wrong",
    "hate",
    "problem",
    "issue",
    "can't",
    "cannot",
    "doesn't",
    "dont",
    "don't",
    "miss",
    "wish",
    "want",
    "need",
    "trying",
    "find",
    "switch",
    "switched",
    "apple music",
    "youtube music",
    "workaround",
    "manual",
    "skip",
    "skipping",
]


def collect_reddit(
    client: ApifyClient,
    searches: list[str],
    from_date: date,
    to_date: date,
    limit: int,
    min_words: int,
    candidate_limit: int | None = None,
    comment_depth: int = 2,
    comments_per_post: int = 10,
) -> tuple[list[FeedbackRecord], list[str]]:
    records: list[FeedbackRecord] = []
    errors: list[str] = []
    seen: set[str] = set()
    max_candidates = candidate_limit_for(candidate_limit)
    usable_target = effective_usable_target(limit, max_candidates)
    active_searches = [query.strip() for query in searches if query.strip()]
    if not active_searches:
        return [], ["No Reddit searches configured."]

    collect_public_reddit(
        records=records,
        errors=errors,
        seen=seen,
        searches=active_searches,
        from_date=from_date,
        to_date=to_date,
        min_words=min_words,
        max_candidates=max_candidates,
    )

    public_usable = usable_count(records)
    if public_usable < usable_target and should_collect_candidates(records, max_candidates):
        collect_reddit_apify_fallback(
            client=client,
            records=records,
            errors=errors,
            seen=seen,
            searches=active_searches,
            from_date=from_date,
            to_date=to_date,
            min_words=min_words,
            max_candidates=max_candidates,
            comment_depth=comment_depth,
            comments_per_post=comments_per_post,
        )
    if any(record.quality_passed for record in records) and public_usable:
        errors[:] = [error for error in errors if "no usable records from focused subreddits" not in error]
    if usable_target >= 50 and materially_under_target(usable_count(records), usable_target):
        errors.append(
            "Reddit returned materially fewer meaningful records than requested after public subreddit search and Apify fallback. "
            f"Collected {usable_count(records)} meaningful records from {len(records)} candidates; healthy threshold is {target_tolerance_floor(usable_target)}. "
            "This usually means Reddit exposed a smaller relevant result pool for the configured searches/date range."
        )

    return trim_to_target_usable(records, usable_target, max_records=max_candidates), errors


def collect_public_reddit(
    records: list[FeedbackRecord],
    errors: list[str],
    seen: set[str],
    searches: list[str],
    from_date: date,
    to_date: date,
    min_words: int,
    max_candidates: int,
) -> None:
    with httpx.Client(headers={"User-Agent": REDDIT_USER_AGENT}, timeout=30.0, follow_redirects=True) as http_client:
        for query in searches:
            if not should_collect_candidates(records, max_candidates):
                break
            query_before = len(records)
            for subreddit in REDDIT_SEARCH_SUBREDDITS:
                if not should_collect_candidates(records, max_candidates):
                    break
                url = old_reddit_search_url(subreddit, query)
                try:
                    html = get_with_retries(http_client, url)
                except Exception as exc:
                    errors.append(f"reddit public search '{query}' in r/{subreddit}: {exc}")
                    continue
                for item in parse_old_reddit_search(html, query, subreddit):
                    if not should_collect_candidates(records, max_candidates):
                        break
                    if not is_within_date_range(item_created_at(item), from_date, to_date, include_missing=False):
                        continue
                    record = normalize_reddit_item(item, query)
                    context_text = reddit_context(record.source_query, item)
                    if not has_reddit_discovery_focus(f"{record.text} {context_text}"):
                        continue
                    if not passes_prefilter(record, min_words, context_text=context_text):
                        continue
                    add_record(records, seen, apply_quality(record, min_words, context_text=context_text))
                time.sleep(0.35)
            if len(records) == query_before:
                errors.append(f"reddit public search '{query}': no usable records from focused subreddits.")


def collect_reddit_apify_fallback(
    client: ApifyClient,
    records: list[FeedbackRecord],
    errors: list[str],
    seen: set[str],
    searches: list[str],
    from_date: date,
    to_date: date,
    min_words: int,
    max_candidates: int,
    comment_depth: int,
    comments_per_post: int,
) -> None:
    per_query_limit = max(10, max_candidates // max(1, len(searches)))
    for query in searches:
        if not should_collect_candidates(records, max_candidates):
            break
        run_limit = max(1, min(per_query_limit, max_candidates - len(records)))
        actor_input = {
            "searches": [query],
            "searchPosts": True,
            "searchComments": comment_depth > 0 and comments_per_post > 0,
            "searchCommunities": False,
            "searchUsers": False,
            "searchMedia": False,
            "sort": "relevance",
            "time": "year",
            "includeMediaLinks": True,
            "includeNSFW": False,
            "maxItems": run_limit,
            "maxPostCount": run_limit,
            "maxComments": max(0, comments_per_post),
            "postDateLimit": from_date.isoformat(),
            "commentDateLimit": from_date.isoformat(),
            "proxy": {"useApifyProxy": True},
        }
        try:
            items = client.run_actor_items(
                REDDIT_ACTOR_ID,
                actor_input,
                limit=run_limit,
                max_items=run_limit,
                timeout_seconds=120,
                max_total_charge_usd=0.15,
            )
        except Exception as exc:
            errors.append(f"reddit apify lite fallback '{query}': {exc}")
            continue
        for item in items:
            if not should_collect_candidates(records, max_candidates):
                break
            if item.get("error") or item.get("errorDescription") or item.get("noResults") is True:
                continue
            if not is_within_date_range(item_created_at(item), from_date, to_date, include_missing=False):
                continue
            record = normalize_reddit_item(item, query)
            context_text = reddit_context(record.source_query, item)
            if not has_reddit_discovery_focus(f"{record.text} {context_text}"):
                continue
            if not passes_prefilter(record, min_words, context_text=context_text):
                continue
            add_record(records, seen, apply_quality(record, min_words, context_text=context_text))


def old_reddit_search_url(subreddit: str, query: str) -> str:
    return f"https://old.reddit.com/r/{subreddit}/search?q={quote_plus(query)}&restrict_sr=on&sort=relevance&t=year"


def get_with_retries(client: httpx.Client, url: str, attempts: int = 2) -> str:
    last_error: Exception | None = None
    for attempt in range(attempts + 1):
        try:
            response = client.get(url)
            response.raise_for_status()
            return response.text
        except Exception as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(str(last_error))


def parse_old_reddit_search(html: str, query: str, subreddit: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, Any]] = []
    for result in soup.select(".search-result.search-result-link"):
        title_el = result.select_one("a.search-title")
        if not title_el:
            continue
        time_el = result.select_one(".search-time time")
        body_el = result.select_one(".search-result-body")
        score_el = result.select_one(".search-score")
        comments_el = result.select_one(".search-comments")
        author_el = result.select_one(".search-author .author")
        title = title_el.get_text(" ", strip=True)
        body = body_el.get_text(" ", strip=True) if body_el else ""
        items.append(
            {
                "id": result.get("data-fullname") or title_el.get("href") or title,
                "type": "post",
                "searchTerm": query,
                "title": title,
                "selftext": body,
                "createdAt": time_el.get("datetime") if time_el else None,
                "author": author_el.get_text(" ", strip=True) if author_el else None,
                "score": parse_int(score_el.get_text(" ", strip=True) if score_el else None, POINTS_RE),
                "num_comments": parse_int(comments_el.get_text(" ", strip=True) if comments_el else None, COMMENTS_RE),
                "permalink": title_el.get("href"),
                "subreddit": f"r/{subreddit}",
                "source_api": "old_reddit_public_html",
            }
        )
    return items


def parse_int(value: str | None, pattern: re.Pattern[str]) -> int | None:
    if not value:
        return None
    match = pattern.search(value)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def has_reddit_discovery_focus(text: str) -> bool:
    lowered = text.lower()
    if "read the full post in the spotify community" in lowered or "spotify support article" in lowered:
        return False
    has_discovery = any(term in lowered for term in REDDIT_DISCOVERY_FOCUS_TERMS)
    has_behavior = any(term in lowered for term in REDDIT_PROBLEM_BEHAVIOR_TERMS)
    return has_discovery and has_behavior


def normalize_reddit_item(item: dict[str, Any], fallback_query: str) -> FeedbackRecord:
    kind = infer_kind(item)
    source_query = str(first_present(item, ["search", "searchTerm", "search_term", "query"]) or fallback_query)
    title = str(first_present(item, ["title", "postTitle", "post_title"]) or "")
    body = str(first_present(item, ["selftext", "body", "text", "comment", "content", "description"]) or "")
    text = f"{title}\n\n{body}".strip() if kind == "post" and title else body.strip()
    external_core = str(first_present(item, ["id", "parsedId", "name", "commentId", "postId", "permalink", "url"]) or text[:80])
    permalink = first_present(item, ["permalink", "url", "postUrl", "link", "commentsUrl"])
    url = normalize_reddit_url(permalink)
    author = first_present(item, ["author", "authorName", "author_name", "username", "user"])
    metadata = {
        "kind": kind,
        "subreddit": first_present(item, ["subreddit", "communityName", "category", "community", "subredditName"]),
        "score": first_present(item, ["score", "upVotes", "upvotes", "ups", "points"]),
        "upvote_ratio": first_present(item, ["upVoteRatio", "upvoteRatio", "upvote_ratio"]),
        "num_comments": first_present(item, ["num_comments", "numComments", "numberOfComments", "commentCount", "commentsCount"]),
        "reply_count": first_present(item, ["reply_count", "repliesCount", "childCommentsCount", "numberOfReplies"]),
        "post_id": first_present(item, ["postId", "post_id", "linkId", "parentId"]),
        "post_title": title or first_present(item, ["postTitle", "post_title"]),
        "source_api": first_present(item, ["source_api"]),
        "source_actor": REDDIT_ACTOR_ID,
        "reddit_data_type": first_present(item, ["dataType", "type", "kind", "itemType"]),
    }
    return FeedbackRecord(
        source="reddit",
        source_query=source_query,
        external_id=f"reddit_{kind}:{external_core}",
        created_at=to_iso(item_created_at(item)),
        author=str(author) if author is not None else None,
        text=text,
        url=url,
        language=str(first_present(item, ["lang", "language"]) or "en"),
        metadata=metadata,
    )


def infer_kind(item: dict[str, Any]) -> str:
    explicit = str(first_present(item, ["dataType", "type", "kind", "itemType"]) or "").lower()
    if "comment" in explicit:
        return "comment"
    if "post" in explicit:
        return "post"
    if first_present(item, ["comment", "parentId", "linkId"]):
        return "comment"
    return "post"


def item_created_at(item: dict[str, Any]) -> Any:
    return first_present(item, ["created_utc", "createdUtc", "created", "created_at", "createdAt", "date", "timestamp"])


def reddit_context(query: str, item: dict[str, Any]) -> str:
    return " ".join(
        str(part or "")
        for part in [
            query,
            first_present(item, ["title", "postTitle", "post_title"]),
            first_present(item, ["selftext", "body", "text", "comment", "content"]),
        ]
    )


def normalize_reddit_url(value: Any) -> str | None:
    if not value:
        return None
    text = str(value)
    if text.startswith("http"):
        return text
    if text.startswith("/"):
        return f"https://www.reddit.com{text}"
    return text


def first_present(item: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return None


def add_record(records: list[FeedbackRecord], seen: set[str], record: FeedbackRecord) -> None:
    key = f"{record.source}:{record.external_id}"
    if key in seen:
        return
    seen.add(key)
    records.append(record)
