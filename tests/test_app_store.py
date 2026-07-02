from datetime import date

import httpx

from src.sources.app_store import collect_app_store


def test_app_store_collector_normalizes_quality_reviews():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "feed": {
                    "entry": [
                        {"im:name": {"label": "Spotify"}},
                        {
                            "id": {"label": "review-1"},
                            "updated": {"label": "2026-06-10T10:00:00-07:00"},
                            "title": {"label": "Recommendations are repetitive"},
                            "content": {
                                "label": (
                                    "Spotify keeps recommending the same songs from my old playlists, and Discover Weekly "
                                    "does not help me find new music or unfamiliar artists anymore."
                                )
                            },
                            "im:rating": {"label": "2"},
                            "author": {"name": {"label": "listener"}},
                        },
                    ]
                }
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))

    records, errors = collect_app_store(
        from_date=date(2026, 6, 1),
        to_date=date(2026, 6, 19),
        target_usable=1,
        min_words=20,
        client=client,
    )

    assert not errors
    assert len(records) == 1
    assert records[0].quality_passed
    assert records[0].rating == 2


def test_app_store_collector_uses_amp_fallback_when_rss_is_empty():
    token = "eyJ" + ("a" * 140)

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "itunes.apple.com" in url:
            return httpx.Response(200, json={"feed": {"entry": []}})
        if url.startswith("https://apps.apple.com/us/app/"):
            return httpx.Response(200, text='<html><script src="/assets/index-test.js"></script></html>')
        if url.startswith("https://apps.apple.com/assets/index-test.js"):
            return httpx.Response(200, text=f"window.__token='{token}';")
        if url.startswith("https://amp-api-edge.apps.apple.com/v1/catalog/us/apps/"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "amp-review-1",
                            "attributes": {
                                "date": "2026-06-10T12:00:00Z",
                                "rating": 2,
                                "title": "Smart shuffle repeats everything",
                                "review": (
                                    "Spotify smart shuffle keeps adding the same playlist songs, and Discover Weekly "
                                    "stopped helping me find new artists or fresh music that matches my taste."
                                ),
                                "userName": "listener",
                                "versionString": "9.1",
                            },
                        }
                    ]
                },
            )
        raise AssertionError(f"Unexpected URL: {url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    records, errors = collect_app_store(
        from_date=date(2026, 6, 1),
        to_date=date(2026, 6, 19),
        target_usable=1,
        min_words=20,
        countries=["us"],
        candidate_limit=5,
        client=client,
    )

    assert not errors
    assert len(records) == 1
    assert records[0].quality_passed
    assert records[0].metadata["source_api"] == "apple_amp_reviews"
    assert records[0].external_id == "app_store:us:amp-review-1"


def test_app_store_amp_fallback_retries_rate_limit_then_succeeds():
    token = "eyJ" + ("a" * 140)
    amp_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal amp_calls
        url = str(request.url)
        if "itunes.apple.com" in url:
            return httpx.Response(200, json={"feed": {"entry": []}})
        if url.startswith("https://apps.apple.com/us/app/"):
            return httpx.Response(200, text='<html><script src="/assets/index-test.js"></script></html>')
        if url.startswith("https://apps.apple.com/assets/index-test.js"):
            return httpx.Response(200, text=f"window.__token='{token}';")
        if url.startswith("https://amp-api-edge.apps.apple.com/v1/catalog/us/apps/"):
            amp_calls += 1
            if amp_calls == 1:
                return httpx.Response(429, headers={"Retry-After": "0"})
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "amp-review-after-retry",
                            "attributes": {
                                "date": "2026-06-10T12:00:00Z",
                                "rating": 1,
                                "title": "Recommendations got stuck",
                                "review": (
                                    "Spotify recommendations are stuck on the same songs, and I cannot discover new "
                                    "artists from playlist radio or Discover Weekly anymore."
                                ),
                            },
                        }
                    ]
                },
            )
        raise AssertionError(f"Unexpected URL: {url}")

    records, errors = collect_app_store(
        from_date=date(2026, 6, 1),
        to_date=date(2026, 6, 19),
        target_usable=1,
        min_words=20,
        countries=["us"],
        candidate_limit=5,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        amp_retry_delays_seconds=(0,),
    )

    assert not errors
    assert amp_calls == 2
    assert len(records) == 1
    assert records[0].external_id == "app_store:us:amp-review-after-retry"


def test_app_store_amp_fallback_reports_clean_warning_after_rate_limit_exhaustion():
    token = "eyJ" + ("a" * 140)

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "itunes.apple.com" in url:
            return httpx.Response(200, json={"feed": {"entry": []}})
        if url.startswith("https://apps.apple.com/us/app/"):
            return httpx.Response(200, text='<html><script src="/assets/index-test.js"></script></html>')
        if url.startswith("https://apps.apple.com/assets/index-test.js"):
            return httpx.Response(200, text=f"window.__token='{token}';")
        if url.startswith("https://amp-api-edge.apps.apple.com/v1/catalog/us/apps/"):
            return httpx.Response(429, headers={"Retry-After": "0"})
        raise AssertionError(f"Unexpected URL: {url}")

    records, errors = collect_app_store(
        from_date=date(2026, 6, 1),
        to_date=date(2026, 6, 19),
        target_usable=1,
        min_words=20,
        countries=["us"],
        candidate_limit=5,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        amp_retry_delays_seconds=(0,),
    )

    assert records == []
    assert len(errors) == 1
    assert "temporarily rate-limited" in errors[0]
    assert "https://" not in errors[0]
