import httpx

from src.sources.apify_client import ApifyClient, is_apify_hard_limit_error


def test_apify_client_rotates_keys_and_returns_clean_dataset_items():
    seen_tokens = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_tokens.append(request.url.params["token"])
        if request.url.params["token"] == "bad":
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(200, json=[{"id": "one"}, {"id": "two"}, "ignored"])

    client = httpx.Client(transport=httpx.MockTransport(handler))
    apify = ApifyClient(
        api_keys=["bad", "good"],
        base_url="https://api.apify.com/v2",
        client=client,
        retry_delay_seconds=0,
    )

    items = apify.run_actor_items(
        "trudax/reddit-scraper-lite",
        {"searches": ["spotify"]},
        limit=2,
        max_items=2,
        max_total_charge_usd=0.05,
    )

    assert seen_tokens == ["bad", "bad", "good"]
    assert items == [{"id": "one"}, {"id": "two"}]


def test_apify_hard_limit_detector_matches_platform_feature_disabled_message():
    message = 'HTTP 403 {"error":{"type":"platform-feature-disabled","message":"Monthly usage hard limit exceeded"}}'

    assert is_apify_hard_limit_error(message)
