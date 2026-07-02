from __future__ import annotations

from datetime import date
import re
import time
from typing import Any

import httpx

from src.date_utils import is_within_date_range, to_iso
from src.defaults import SPOTIFY_APP_STORE_ID
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


APP_STORE_COUNTRIES = ["us", "ca", "gb", "au", "ie", "nz"]
APP_STORE_PAGE_URL = "https://apps.apple.com/{country}/app/spotify-music-and-podcasts/id{app_id}"
APP_STORE_AMP_REVIEWS_URL = "https://amp-api-edge.apps.apple.com/v1/catalog/{country}/apps/{app_id}/reviews"
APP_STORE_RSS_URLS = [
    "https://itunes.apple.com/{country}/rss/customerreviews/page={page}/id={app_id}/sortBy=mostRecent/json",
    "https://itunes.apple.com/{country}/rss/customerreviews/page={page}/id={app_id}/sortby=mostrecent/json",
]
APPLE_JWT_RE = re.compile(r"eyJ[a-zA-Z0-9_\-.]{100,}")
APPLE_SCRIPT_RE = re.compile(r'<script[^>]+src="([^"]*index[^"]*\.js)"')
APP_STORE_AMP_PAGE_DELAY_SECONDS = 0.75
APP_STORE_AMP_RETRY_DELAYS_SECONDS = (3.0, 8.0, 15.0)


class AppStoreRateLimitError(RuntimeError):
    pass


def collect_app_store(
    from_date: date,
    to_date: date,
    target_usable: int,
    min_words: int,
    candidate_limit: int | None = None,
    app_id: str = SPOTIFY_APP_STORE_ID,
    countries: list[str] | None = None,
    client: httpx.Client | None = None,
    amp_page_delay_seconds: float = APP_STORE_AMP_PAGE_DELAY_SECONDS,
    amp_retry_delays_seconds: tuple[float, ...] = APP_STORE_AMP_RETRY_DELAYS_SECONDS,
) -> tuple[list[FeedbackRecord], list[str]]:
    records: list[FeedbackRecord] = []
    errors: list[str] = []
    seen: set[str] = set()
    max_candidates = candidate_limit_for(candidate_limit)
    usable_target = effective_usable_target(target_usable, max_candidates)
    owns_client = client is None
    http = client or httpx.Client(timeout=30.0, follow_redirects=True)
    storefronts = [country.lower() for country in (countries or APP_STORE_COUNTRIES) if country.strip()]
    try:
        for country in storefronts:
            if not should_collect_candidates(records, max_candidates):
                break
            page = 1
            while should_collect_candidates(records, max_candidates) and page <= 10:
                try:
                    payload = fetch_review_page(http, page=page, app_id=app_id, country=country)
                except Exception as exc:
                    errors.append(f"app store {country} page {page}: {exc}")
                    break

                entries = payload.get("feed", {}).get("entry", [])
                if page == 1 and entries:
                    entries = entries[1:] if "im:name" in entries[0] else entries
                if not entries:
                    break

                for entry in entries:
                    if not should_collect_candidates(records, max_candidates):
                        break
                    record = normalize_review(entry, country=country)
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
                page += 1
        if usable_count(records) < usable_target and should_collect_candidates(records, max_candidates):
            collect_amp_reviews(
                http=http,
                records=records,
                errors=errors,
                seen=seen,
                storefronts=storefronts,
                app_id=app_id,
                from_date=from_date,
                to_date=to_date,
                min_words=min_words,
                max_candidates=max_candidates,
                page_delay_seconds=amp_page_delay_seconds,
                retry_delays_seconds=amp_retry_delays_seconds,
            )
    finally:
        if owns_client:
            http.close()

    if not records and not errors:
        errors.append("App Store returned no public review records for the selected date range.")
    if usable_target >= 50 and materially_under_target(usable_count(records), usable_target):
        errors.append(
            "App Store returned materially fewer meaningful records than requested from available public storefront review pages. "
            f"Collected {usable_count(records)} meaningful records from {len(records)} candidates; healthy threshold is {target_tolerance_floor(usable_target)}. "
            "This usually means Apple exposed a smaller public review window for the selected date range, or temporarily rate-limited deeper pagination."
        )
    return trim_to_target_usable(records, usable_target, max_records=max_candidates), errors


def collect_amp_reviews(
    http: httpx.Client,
    records: list[FeedbackRecord],
    errors: list[str],
    seen: set[str],
    storefronts: list[str],
    app_id: str,
    from_date: date,
    to_date: date,
    min_words: int,
    max_candidates: int,
    page_delay_seconds: float = APP_STORE_AMP_PAGE_DELAY_SECONDS,
    retry_delays_seconds: tuple[float, ...] = APP_STORE_AMP_RETRY_DELAYS_SECONDS,
) -> None:
    token: str | None = None
    rate_limited = False
    for country in storefronts:
        if rate_limited or not should_collect_candidates(records, max_candidates):
            break
        if token is None:
            try:
                token = fetch_apple_web_token(http, app_id=app_id, country=country)
            except Exception as exc:
                errors.append(f"app store amp token {country}: {exc}")
                continue
        offset = 0
        max_offset = max(200, max_candidates * 2)
        while should_collect_candidates(records, max_candidates) and offset <= max_offset:
            if offset > 0 and page_delay_seconds > 0:
                time.sleep(page_delay_seconds)
            try:
                payload = fetch_amp_review_page(
                    http,
                    token=token,
                    app_id=app_id,
                    country=country,
                    offset=offset,
                    limit=min(20, max_candidates - len(records)),
                    retry_delays_seconds=retry_delays_seconds,
                )
            except AppStoreRateLimitError:
                errors.append(
                    "Apple temporarily rate-limited additional App Store review pages. "
                    f"Collected {len(records)} App Store candidate records so far; wait a few minutes and run collection again if you need more."
                )
                rate_limited = True
                break
            except Exception as exc:
                errors.append(f"app store amp {country} offset {offset}: {exc}")
                break
            items = payload.get("data", [])
            if not items:
                break
            for item in items:
                if not should_collect_candidates(records, max_candidates):
                    break
                record = normalize_amp_review(item, country=country)
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
            if not payload.get("next"):
                break
            offset += len(items)


def fetch_apple_web_token(http: httpx.Client, app_id: str, country: str = "us") -> str:
    page_url = APP_STORE_PAGE_URL.format(country=country, app_id=app_id)
    response = http.get(page_url, headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html,*/*"})
    response.raise_for_status()
    scripts = APPLE_SCRIPT_RE.findall(response.text)
    for script in scripts:
        script_url = script if script.startswith("http") else f"https://apps.apple.com{script}"
        script_response = http.get(script_url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/javascript,*/*"})
        script_response.raise_for_status()
        match = APPLE_JWT_RE.search(script_response.text)
        if match:
            return match.group(0)
    raise RuntimeError("Could not find Apple public web token.")


def fetch_amp_review_page(
    http: httpx.Client,
    token: str,
    app_id: str,
    country: str,
    offset: int,
    limit: int,
    retry_delays_seconds: tuple[float, ...] = APP_STORE_AMP_RETRY_DELAYS_SECONDS,
) -> dict[str, Any]:
    url = APP_STORE_AMP_REVIEWS_URL.format(country=country, app_id=app_id)
    response: httpx.Response | None = None
    for attempt in range(len(retry_delays_seconds) + 1):
        response = http.get(
            url,
            params={"l": "en-US", "offset": offset, "limit": max(1, limit), "platform": "iphone", "sort": "recent"},
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Origin": "https://apps.apple.com",
                "Referer": APP_STORE_PAGE_URL.format(country=country, app_id=app_id),
                "Authorization": f"Bearer {token}",
            },
        )
        if response.status_code != 429:
            break
        if attempt >= len(retry_delays_seconds):
            raise AppStoreRateLimitError("Apple AMP reviews endpoint returned HTTP 429.")
        retry_after = parse_retry_after(response.headers.get("Retry-After"))
        delay_seconds = retry_after if retry_after is not None else retry_delays_seconds[attempt]
        if delay_seconds > 0:
            time.sleep(delay_seconds)
    if response is None:
        raise RuntimeError("Apple AMP reviews endpoint did not return a response.")
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def fetch_review_page(http: httpx.Client, page: int, app_id: str, country: str = "us") -> dict[str, Any]:
    last_payload: dict[str, Any] | None = None
    last_error: Exception | None = None
    for url_template in APP_STORE_RSS_URLS:
        try:
            response = http.get(url_template.format(country=country, page=page, app_id=app_id), params={"l": "en"})
            response.raise_for_status()
            payload = response.json()
            entries = payload.get("feed", {}).get("entry", [])
            if entries:
                return payload
            last_payload = payload
        except Exception as exc:
            last_error = exc
    if last_payload is not None:
        return last_payload
    raise RuntimeError(str(last_error))


def text_value(value: Any) -> str | None:
    if isinstance(value, dict):
        label = value.get("label")
        return str(label) if label is not None else None
    if value is not None:
        return str(value)
    return None


def normalize_review(entry: dict[str, Any], country: str = "us") -> FeedbackRecord:
    review_id = text_value(entry.get("id")) or text_value(entry.get("link")) or text_value(entry.get("title")) or ""
    title = text_value(entry.get("title")) or ""
    content = text_value(entry.get("content")) or ""
    rating_text = text_value(entry.get("im:rating"))
    try:
        rating = float(rating_text) if rating_text is not None else None
    except ValueError:
        rating = None
    author = None
    if isinstance(entry.get("author"), dict):
        author = text_value(entry["author"].get("name"))
    link = entry.get("link")
    url = link.get("attributes", {}).get("href") if isinstance(link, dict) else None
    return FeedbackRecord(
        source="app_store",
        source_query="spotify_app_store_reviews",
        external_id=f"app_store:{review_id}",
        created_at=to_iso(text_value(entry.get("updated"))),
        author=author,
        text=f"{title}\n\n{content}".strip(),
        url=url,
        rating=rating,
        language="en",
        metadata={"app_id": SPOTIFY_APP_STORE_ID, "storefront": country, "version": text_value(entry.get("im:version"))},
    )


def normalize_amp_review(item: dict[str, Any], country: str = "us") -> FeedbackRecord:
    attributes = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
    review_id = str(item.get("id") or attributes.get("id") or attributes.get("date") or attributes.get("title") or "")
    title = str(attributes.get("title") or "")
    review = str(attributes.get("review") or "")
    rating = attributes.get("rating")
    try:
        rating_value = float(rating) if rating is not None else None
    except (TypeError, ValueError):
        rating_value = None
    return FeedbackRecord(
        source="app_store",
        source_query="spotify_app_store_reviews",
        external_id=f"app_store:{country}:{review_id}",
        created_at=to_iso(attributes.get("date")),
        author=str(attributes.get("userName")) if attributes.get("userName") else None,
        text=f"{title}\n\n{review}".strip(),
        url=APP_STORE_PAGE_URL.format(country=country, app_id=SPOTIFY_APP_STORE_ID),
        rating=rating_value,
        language="en",
        metadata={
            "app_id": SPOTIFY_APP_STORE_ID,
            "storefront": country,
            "version": attributes.get("versionString"),
            "source_api": "apple_amp_reviews",
            "is_edited": attributes.get("isEdited"),
        },
    )
