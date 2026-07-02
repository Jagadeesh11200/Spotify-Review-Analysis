from __future__ import annotations

from datetime import date
from html import unescape
import re
from urllib.parse import quote_plus, urljoin

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


COMMUNITY_BASE_URL = "https://community.spotify.com"
COMMUNITY_API_V2_SEARCH_URL = f"{COMMUNITY_BASE_URL}/api/2.0/search"
COMMUNITY_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
COMMUNITY_MESSAGES_PER_THREAD = 20
COMMUNITY_API_PAGE_SIZE = 50
INT_RE = re.compile(r"\d+")


def collect_spotify_community(
    searches: list[str],
    from_date: date,
    to_date: date,
    limit: int,
    min_words: int,
    candidate_limit: int | None = None,
    client: httpx.Client | None = None,
) -> tuple[list[FeedbackRecord], list[str]]:
    records: list[FeedbackRecord] = []
    errors: list[str] = []
    seen: set[str] = set()
    max_candidates = candidate_limit_for(candidate_limit)
    usable_target = effective_usable_target(limit, max_candidates)
    active_searches = [query for query in searches if query.strip()]
    per_query_raw_limit = max_candidates
    owns_client = client is None
    http = client or httpx.Client(timeout=30.0, follow_redirects=True, headers=COMMUNITY_HEADERS)
    try:
        for query in active_searches:
            if not should_collect_candidates(records, max_candidates):
                break
            query_records = 0
            api_errors: list[str] = []
            search_results = search_community_messages(
                http=http,
                query=query,
                limit=min(max_candidates - len(records), per_query_raw_limit),
                errors=api_errors,
            )
            if not search_results:
                html_errors: list[str] = []
                html = fetch_html(http=http, url=search_url(query), errors=html_errors, error_label=f"spotify community html search '{query}'")
                search_results = parse_search_results(html) if html else []
                if not search_results:
                    errors.extend(api_errors + html_errors)

            for result in search_results:
                if not should_collect_candidates(records, max_candidates) or query_records >= per_query_raw_limit:
                    break
                topic_records = fetch_topic_records(
                    http=http,
                    result=result,
                    query=query,
                    from_date=from_date,
                    to_date=to_date,
                    min_words=min_words,
                    errors=errors,
                    max_records=min(max_candidates - len(records), per_query_raw_limit - query_records),
                )
                for record in topic_records:
                    key = f"{record.source}:{record.external_id}"
                    if key not in seen:
                        seen.add(key)
                        records.append(record)
                        query_records += 1
    finally:
        if owns_client:
            http.close()

    if usable_target >= 50 and materially_under_target(usable_count(records), usable_target):
        errors.append(
            "Spotify Community returned materially fewer meaningful records than requested from public Khoros search/thread pages. "
            f"Collected {usable_count(records)} meaningful records from {len(records)} candidates; healthy threshold is {target_tolerance_floor(usable_target)}. "
            "This usually means the public forum search exposed a smaller relevant result pool for the configured searches/date range."
        )
    return trim_to_target_usable(records, usable_target, max_records=max_candidates), errors


def search_community_messages(
    http: httpx.Client,
    query: str,
    limit: int,
    errors: list[str],
) -> list[dict[str, str]]:
    messages = search_community_api_v2(http=http, query=query, limit=limit, errors=errors)
    results: list[dict[str, object]] = []
    for message in messages:
        title = str(message.get("subject") or message.get("body") or "")
        url = str(message.get("url") or "")
        message_id = str(message.get("message_id") or "")
        if not title or not message_id:
            continue
        results.append(
            {
                "title": title,
                "url": url or f"{COMMUNITY_BASE_URL}/t5/forums/messagepage/message-id/{message_id}",
                "snippet": str(message.get("body") or message.get("teaser") or title),
                "message_id": message_id,
                "thread_id": str(message.get("thread_id") or message.get("root_id") or message_id),
                "created_at": message.get("created_at"),
                "author": message.get("author"),
                "kudos_count": message.get("kudos_count"),
                "reply_count": message.get("reply_count"),
                "source_api": "khoros_api_v2",
            }
        )
    return results


def search_community_api_v2(
    http: httpx.Client,
    query: str,
    limit: int,
    errors: list[str],
) -> list[dict[str, object]]:
    messages: list[dict[str, object]] = []
    page_size = min(COMMUNITY_API_PAGE_SIZE, max(1, limit))
    for offset in range(0, max(1, limit), page_size):
        try:
            response = http.get(
                COMMUNITY_API_V2_SEARCH_URL,
                params={"q": build_message_search_liql(query, page_size, offset)},
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            errors.append(f"spotify community api v2 search '{query}' offset {offset}: {exc}")
            break

        page_messages = parse_api_v2_messages(payload)
        if not page_messages:
            break
        messages.extend(page_messages)
        if len(page_messages) < page_size or len(messages) >= limit:
            break
    return messages[:limit]


def build_message_search_liql(query: str, limit: int, offset: int = 0) -> str:
    safe_query = query.replace("\\", "\\\\").replace("'", "\\'")
    return (
        "SELECT id, subject, body, post_time, author, view_href FROM messages "
        f"WHERE subject MATCHES '{safe_query}' OR body MATCHES '{safe_query}' "
        "ORDER BY post_time DESC "
        f"LIMIT {max(1, limit)} OFFSET {max(0, offset)}"
    )


def parse_api_v2_messages(payload: object) -> list[dict[str, object]]:
    items = api_v2_items(payload)
    messages: list[dict[str, object]] = []
    for position, item in enumerate(items):
        message_id = str(item.get("id") or item.get("message_id") or item.get("uid") or "")
        subject = string_or_none(item.get("subject"))
        body = html_to_text(string_or_none(item.get("body")))
        teaser = html_to_text(string_or_none(item.get("teaser")))
        root_id = nested_id(item.get("root"))
        parent_id = nested_id(item.get("parent"))
        conversation_id = nested_id(item.get("conversation"))
        thread_id = conversation_id or root_id or message_id
        messages.append(
            {
                "message_id": message_id,
                "root_id": root_id,
                "thread_id": thread_id,
                "parent_id": parent_id,
                "subject": subject,
                "body": body,
                "teaser": teaser,
                "created_at": first_present(item, ["post_time", "postTime", "created_at", "date"]),
                "author": nested_name(item.get("author")),
                "url": string_or_none(item.get("view_href") or item.get("url") or item.get("href")),
                "kudos_count": nested_count(item.get("kudos")),
                "reply_count": nested_count(item.get("replies")),
                "board": nested_name(item.get("board")),
                "position": position,
            }
        )
    return messages


def api_v2_items(payload: object) -> list[dict[str, object]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("items", "messages", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    data = payload.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        return api_v2_items(data)
    return []


def string_or_none(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        for key in ("text", "value", "login", "title", "name", "href", "view_href"):
            if value.get(key) is not None:
                return str(value[key])
        return None
    text = str(value).strip()
    return text or None


def first_present(item: dict[str, object], keys: list[str]) -> object | None:
    for key in keys:
        if item.get(key) is not None:
            return item[key]
    return None


def nested_id(value: object) -> str | None:
    if isinstance(value, dict):
        for key in ("id", "uid"):
            if value.get(key) is not None:
                return str(value[key])
        href = string_or_none(value.get("href"))
        if href:
            return href_id(href)
    return string_or_none(value)


def nested_name(value: object) -> str | None:
    if isinstance(value, dict):
        for key in ("login", "display_name", "title", "name", "id"):
            if value.get(key) is not None:
                return str(value[key])
    return string_or_none(value)


def nested_count(value: object) -> int | None:
    if isinstance(value, dict):
        for key in ("count", "sum", "value"):
            if value.get(key) is not None:
                return int_or_none(value[key])
    return int_or_none(value)


def int_or_none(value: object) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def search_url(query: str) -> str:
    return (
        f"{COMMUNITY_BASE_URL}/t5/forums/searchpage/tab/message"
        f"?advanced=false&allow_punctuation=false&collapse_discussion=true&search_type=thread&q={quote_plus(query)}"
    )


def parse_search_results(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, str]] = []
    for anchor in soup.select("a[href*='/t5/']"):
        title = anchor.get_text(" ", strip=True)
        href = anchor.get("href")
        if not title or not href or "searchpage" in href or "#M" in href:
            continue
        if len(title) < 8:
            continue
        url = urljoin(COMMUNITY_BASE_URL, href)
        if any(result["url"] == url for result in results):
            continue
        container = anchor.find_parent(["li", "div", "article"]) or anchor
        snippet = container.get_text(" ", strip=True)
        results.append({"title": title, "url": url, "snippet": snippet})
        if len(results) >= 20:
            break
    return results


def fetch_html(
    http: httpx.Client,
    url: str,
    errors: list[str],
    error_label: str = "spotify community page",
) -> str:
    try:
        response = http.get(url)
        response.raise_for_status()
        return response.text
    except Exception as exc:
        errors.append(f"{error_label}: {exc}")
        return ""


def fetch_topic_records(
    http: httpx.Client,
    result: dict[str, str],
    query: str,
    from_date: date,
    to_date: date,
    min_words: int,
    errors: list[str],
    max_records: int = 50,
) -> list[FeedbackRecord]:
    if result.get("thread_id") or result.get("message_id"):
        thread_errors: list[str] = []
        records = fetch_thread_records(
            http=http,
            result=result,
            query=query,
            from_date=from_date,
            to_date=to_date,
            min_words=min_words,
            errors=thread_errors,
            max_records=max_records,
        )
        if records:
            return records

    if result.get("source_api") == "khoros_api_v2":
        record = rest_message_to_record(
            {
                "message_id": result.get("message_id"),
                "thread_id": result.get("thread_id"),
                "subject": result.get("title"),
                "body": result.get("snippet"),
                "created_at": result.get("created_at"),
                "author": result.get("author"),
                "url": result.get("url"),
                "kudos_count": result.get("kudos_count"),
                "reply_count": result.get("reply_count"),
                "position": 0,
            },
            result,
            query,
        )
        context_text = community_context(query, result, [{"body": record.text}])
        if is_within_date_range(record.created_at, from_date, to_date, include_missing=True) and passes_prefilter(record, min_words, context_text=context_text):
            return [apply_quality(record, min_words, context_text=context_text)]

    html_errors: list[str] = []
    html = fetch_html(
        http=http,
        url=result["url"],
        errors=html_errors,
        error_label=f"spotify community topic '{result['url']}'",
    )
    messages = parse_topic_messages(html)
    if not messages:
        messages = [
            {
                "message_id": result["url"],
                "body": result.get("snippet") or result.get("title") or "",
                "created_at": None,
                "author": None,
                "url": result["url"],
                "kudos_count": None,
                "reply_count": None,
                "position": 0,
                "fetch_fallback": True,
            }
        ]

    records: list[FeedbackRecord] = []
    context_text = community_context(query, result, messages)
    for message in messages:
        if len(records) >= max_records:
            break
        created_at_iso = to_iso(message.get("created_at"))
        if not is_within_date_range(created_at_iso, from_date, to_date, include_missing=True):
            continue
        record = FeedbackRecord(
            source="spotify_community",
            source_query=query,
            external_id=f"spotify_community:{message.get('message_id') or result['url']}",
            created_at=created_at_iso,
            author=message.get("author"),
            text=str(message.get("body") or ""),
            url=str(message.get("url") or result["url"]),
            language="en",
            metadata={
                "title": result.get("title"),
                "search_snippet": result.get("snippet"),
                "date_missing": created_at_iso is None,
                "message_position": message.get("position"),
                "kudos_count": message.get("kudos_count"),
                "reply_count": message.get("reply_count"),
                "fetch_fallback": message.get("fetch_fallback", False),
            },
        )
        if not passes_prefilter(record, min_words, context_text=context_text):
            continue
        records.append(apply_quality(record, min_words, context_text=context_text))
    return records


def fetch_thread_records(
    http: httpx.Client,
    result: dict[str, str],
    query: str,
    from_date: date,
    to_date: date,
    min_words: int,
    errors: list[str],
    max_records: int,
) -> list[FeedbackRecord]:
    thread_id = result.get("thread_id") or result.get("message_id")
    if not thread_id:
        return []
    try:
        response = http.get(
            COMMUNITY_API_V2_SEARCH_URL,
            params={"q": build_thread_messages_liql(thread_id, min(COMMUNITY_MESSAGES_PER_THREAD, max(1, max_records)), 0)},
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        errors.append(f"spotify community api v2 thread '{thread_id}': {exc}")
        return []

    messages = parse_api_v2_messages(payload)
    if not messages:
        messages = [
            {
                "message_id": result.get("message_id"),
                "thread_id": thread_id,
                "subject": result.get("title"),
                "body": result.get("snippet"),
                "url": result.get("url"),
                "position": 0,
            }
        ]

    records: list[FeedbackRecord] = []
    context_text = community_context(query, result, messages)
    for position, message in enumerate(messages[: min(COMMUNITY_MESSAGES_PER_THREAD, max_records)]):
        if len(records) >= max_records:
            break
        detailed = enrich_message_detail(http, message, errors)
        detailed["position"] = position
        record = rest_message_to_record(detailed, result, query)
        if not is_within_date_range(record.created_at, from_date, to_date, include_missing=True):
            continue
        if not passes_prefilter(record, min_words, context_text=context_text):
            continue
        records.append(apply_quality(record, min_words, context_text=context_text))
    return records


def enrich_message_detail(http: httpx.Client, message: dict[str, object], errors: list[str]) -> dict[str, object]:
    message_id = message.get("message_id")
    if not message_id or message.get("body"):
        return dict(message)
    try:
        response = http.get(
            COMMUNITY_API_V2_SEARCH_URL,
            params={"q": build_message_detail_liql(str(message_id))},
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        errors.append(f"spotify community api v2 message '{message_id}': {exc}")
        return dict(message)
    details = parse_api_v2_messages(payload)
    if not details:
        return dict(message)
    merged = dict(message)
    merged.update({key: value for key, value in details[0].items() if value not in {None, ""}})
    return merged


def rest_message_to_record(message: dict[str, object], result: dict[str, str], query: str) -> FeedbackRecord:
    message_id = str(message.get("message_id") or result.get("message_id") or result.get("url"))
    subject = str(message.get("subject") or result.get("title") or "")
    body = str(message.get("body") or message.get("teaser") or result.get("snippet") or "")
    text = f"{subject}\n\n{body}".strip()
    created_at_iso = to_iso(message.get("created_at"))
    return FeedbackRecord(
        source="spotify_community",
        source_query=query,
        external_id=f"spotify_community:{message_id}",
        created_at=created_at_iso,
        author=message.get("author"),
        text=text,
        url=str(message.get("url") or result.get("url") or ""),
        language="en",
        metadata={
            "title": result.get("title") or subject,
            "search_snippet": result.get("snippet"),
            "date_missing": created_at_iso is None,
            "message_position": message.get("position"),
            "kudos_count": message.get("kudos_count"),
            "reply_count": message.get("reply_count"),
            "views_count": message.get("views_count"),
            "thread_id": message.get("thread_id") or result.get("thread_id"),
            "parent_id": message.get("parent_id"),
            "source_api": result.get("source_api") or "khoros_api_v2",
        },
    )


def build_thread_messages_liql(thread_id: str, limit: int, offset: int = 0) -> str:
    safe_id = thread_id.replace("\\", "\\\\").replace("'", "\\'")
    return (
        "SELECT id, subject, body, post_time, author, view_href FROM messages "
        f"WHERE conversation.id = '{safe_id}' OR root.id = '{safe_id}' "
        "ORDER BY post_time ASC "
        f"LIMIT {max(1, limit)} OFFSET {max(0, offset)}"
    )


def build_message_detail_liql(message_id: str) -> str:
    safe_id = message_id.replace("\\", "\\\\").replace("'", "\\'")
    return (
        "SELECT id, subject, body, post_time, author, view_href FROM messages "
        f"WHERE id = '{safe_id}' LIMIT 1"
    )


def parse_topic_page(html: str) -> tuple[str | None, str | None, str | None]:
    if not html:
        return None, None, None
    soup = BeautifulSoup(html, "html.parser")

    body_node = (
        soup.select_one(".lia-message-body-content")
        or soup.select_one(".lia-message-body")
        or soup.select_one("[itemprop='text']")
        or soup.select_one("article")
    )
    body = body_node.get_text(" ", strip=True) if body_node else None

    time_node = soup.select_one("time[datetime]")
    created_at = time_node.get("datetime") if time_node else None

    author_node = soup.select_one(".lia-user-name-link") or soup.select_one("[itemprop='author']")
    author = author_node.get_text(" ", strip=True) if author_node else None
    return body, created_at, author


def href_id(href: str | None) -> str | None:
    if not href:
        return None
    return href.rstrip("/").rsplit("/", 1)[-1]


def html_to_text(value: str | None) -> str | None:
    if not value:
        return None
    return BeautifulSoup(unescape(value), "html.parser").get_text(" ", strip=True)


def parse_topic_messages(html: str) -> list[dict[str, object]]:
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    containers = soup.select(
        ".lia-message-view-wrapper, .lia-message-view, .lia-linear-display-message-view, article, [id^='message-']"
    )
    if not containers:
        body, created_at, author = parse_topic_page(html)
        return [
            {
                "message_id": "topic",
                "body": body,
                "created_at": created_at,
                "author": author,
                "url": None,
                "kudos_count": parse_count(soup.select_one(".lia-message-kudos-count, .MessageKudosCount")),
                "reply_count": parse_count(soup.select_one(".lia-message-reply-count, .lia-component-reply-count")),
                "position": 0,
            }
        ] if body else []

    messages: list[dict[str, object]] = []
    seen_bodies: set[str] = set()
    for position, container in enumerate(containers):
        body_node = (
            container.select_one(".lia-message-body-content")
            or container.select_one(".lia-message-body")
            or container.select_one("[itemprop='text']")
        )
        body = body_node.get_text(" ", strip=True) if body_node else ""
        if not body or body in seen_bodies:
            continue
        seen_bodies.add(body)

        time_node = container.select_one("time[datetime]")
        author_node = container.select_one(".lia-user-name-link") or container.select_one("[itemprop='author']")
        anchor = container.select_one("a[href*='#M'], a[href*='/t5/']")
        href = anchor.get("href") if anchor else None
        url = urljoin(COMMUNITY_BASE_URL, href) if href else None
        message_id = container.get("id") or (href.split("#")[-1] if href and "#" in href else f"message-{position}")
        messages.append(
            {
                "message_id": message_id,
                "body": body,
                "created_at": time_node.get("datetime") if time_node else None,
                "author": author_node.get_text(" ", strip=True) if author_node else None,
                "url": url,
                "kudos_count": parse_count(
                    container.select_one(".lia-message-kudos-count, .MessageKudosCount, [class*='kudos']")
                ),
                "reply_count": parse_count(
                    container.select_one(".lia-message-reply-count, .lia-component-reply-count, [class*='reply-count']")
                ),
                "position": len(messages),
            }
        )
    return messages


def parse_count(node) -> int | None:
    if node is None:
        return None
    match = INT_RE.search(node.get_text(" ", strip=True))
    return int(match.group()) if match else None


def community_context(query: str, result: dict[str, str], messages: list[dict[str, object]]) -> str:
    first_body = str(messages[0].get("body") or "") if messages else ""
    return " ".join(
        str(part or "")
        for part in [
            query,
            result.get("title"),
            result.get("snippet"),
            first_body,
        ]
    )
