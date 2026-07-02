from datetime import date

import httpx

from src.sources.spotify_community import (
    build_message_search_liql,
    collect_spotify_community,
    parse_api_v2_messages,
    parse_search_results,
    parse_topic_messages,
    parse_topic_page,
)


def test_parse_spotify_community_search_results():
    html = """
    <html><body>
      <div class="result">
        <a href="/t5/Ideas/Better-music-discovery/idi-p/123">Better music discovery</a>
        <p>Spotify keeps recommending the same songs.</p>
      </div>
      <a href="/t5/forums/searchpage/tab/message?q=x">Search</a>
    </body></html>
    """

    results = parse_search_results(html)

    assert len(results) == 1
    assert results[0]["title"] == "Better music discovery"
    assert results[0]["url"].startswith("https://community.spotify.com/t5/Ideas")


def test_parse_spotify_community_topic_page():
    html = """
    <html><body>
      <time datetime="2026-06-09T08:30:00Z"></time>
      <a class="lia-user-name-link">listener42</a>
      <div class="lia-message-body-content">
        Spotify keeps recommending the same songs from my old playlists and I want better discovery.
      </div>
    </body></html>
    """

    body, created_at, author = parse_topic_page(html)

    assert "same songs" in body
    assert created_at == "2026-06-09T08:30:00Z"
    assert author == "listener42"


def test_parse_spotify_community_topic_messages():
    html = """
    <html><body>
      <div class="lia-message-view-wrapper" id="message-1">
        <time datetime="2026-06-09T08:30:00Z"></time>
        <a class="lia-user-name-link">listener42</a>
        <div class="lia-message-body-content">
          Spotify keeps recommending the same songs from my old playlists and I want better discovery.
        </div>
        <span class="lia-message-kudos-count">12 kudos</span>
      </div>
      <div class="lia-message-view-wrapper" id="message-2">
        <time datetime="2026-06-10T08:30:00Z"></time>
        <a class="lia-user-name-link">listener43</a>
        <div class="lia-message-body-content">
          Same problem here after months of skipping tracks and searching outside the app, because the same loop
          keeps returning when I want unfamiliar artists.
        </div>
      </div>
    </body></html>
    """

    messages = parse_topic_messages(html)

    assert len(messages) == 2
    assert messages[0]["kudos_count"] == 12
    assert messages[1]["author"] == "listener43"


def test_build_spotify_community_liql_search_uses_limit_and_offset():
    liql = build_message_search_liql("same songs", limit=50, offset=100)

    assert "/api/2.0/search" not in liql
    assert "FROM messages" in liql
    assert "MATCHES 'same songs'" in liql
    assert "LIMIT 50 OFFSET 100" in liql


def test_parse_spotify_community_api_v2_messages():
    payload = {
        "data": {
            "items": [
                {
                    "id": "123",
                    "view_href": "https://community.spotify.com/t5/thread/idc-p/123#M1",
                    "root": {"id": "100"},
                    "post_time": "2026-06-09T08:30:00+00:00",
                    "author": {"login": "listener42"},
                    "conversation": {"id": "100"},
                    "parent": {"id": "100"},
                    "kudos": {"count": 12},
                    "replies": {"count": 3},
                    "board": {"title": "Ideas"},
                    "subject": "Discover Weekly repeats",
                    "body": "<p>Spotify keeps recommending the same songs and I want new artists.</p>",
                }
            ]
        }
    }

    messages = parse_api_v2_messages(payload)

    assert messages[0]["message_id"] == "123"
    assert messages[0]["thread_id"] == "100"
    assert messages[0]["parent_id"] == "100"
    assert messages[0]["author"] == "listener42"
    assert messages[0]["kudos_count"] == 12
    assert messages[0]["reply_count"] == 3
    assert messages[0]["board"] == "Ideas"
    assert messages[0]["body"] == "Spotify keeps recommending the same songs and I want new artists."


def test_spotify_community_collector_uses_public_khoros_api_v2():
    queries = []

    def handler(request: httpx.Request) -> httpx.Response:
        queries.append(str(request.url.params.get("q", "")))
        path = request.url.path
        if path.endswith("/api/2.0/search") and "MATCHES" in queries[-1]:
            return httpx.Response(
                200,
                json={
                    "data": {
                        "items": [
                            {
                                "id": "100",
                                "view_href": "https://community.spotify.com/t5/Ideas/Better-discovery/td-p/100",
                                "conversation": {"id": "100"},
                                "root": {"id": "100"},
                                "subject": "Better discovery for repeated recommendations",
                                "teaser": "Spotify keeps recommending the same songs.",
                            }
                        ]
                    }
                },
            )
        if path.endswith("/api/2.0/search") and "conversation.id = '100'" in queries[-1]:
            return httpx.Response(
                200,
                json={
                    "data": {
                        "items": [
                            {
                                "id": "100",
                                "view_href": "https://community.spotify.com/t5/Ideas/Better-discovery/td-p/100",
                                "conversation": {"id": "100"},
                                "root": {"id": "100"},
                                "post_time": "2026-06-09T08:30:00+00:00",
                                "author": {"login": "listener42"},
                                "kudos": {"count": 15},
                                "replies": {"count": 4},
                                "board": {"title": "Ideas"},
                                "subject": "Better discovery for repeated recommendations",
                                "body": "<p>Spotify keeps recommending the same songs from my old playlists and Discover Weekly no longer helps me find new music from unfamiliar artists anymore.</p>",
                            }
                        ]
                    }
                },
            )
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    records, errors = collect_spotify_community(
        searches=["same songs"],
        from_date=date(2026, 1, 1),
        to_date=date(2026, 6, 19),
        limit=10,
        min_words=20,
        client=client,
    )

    assert not errors
    assert len(records) == 1
    assert records[0].quality_passed
    assert records[0].metadata["source_api"] == "khoros_api_v2"
    assert records[0].metadata["kudos_count"] == 15
    assert any("LIMIT 50 OFFSET 0" in query for query in queries)


def test_spotify_community_collector_collects_topic_replies_with_context():
    search_html = """
    <html><body>
      <div>
        <a href="/t5/Ideas/Better-discovery/idi-p/123">Better discovery for repeated recommendations</a>
        <p>Spotify keeps recommending the same songs from my old playlists and I want better music discovery.</p>
      </div>
    </body></html>
    """
    topic_html = """
    <html><body>
      <div class="lia-message-view-wrapper" id="message-1">
        <time datetime="2026-06-09T08:30:00Z"></time>
        <a class="lia-user-name-link">listener42</a>
        <div class="lia-message-body-content">
          Spotify keeps recommending the same songs from my old playlists and I want better discovery for unfamiliar artists,
          because Discover Weekly no longer helps me escape old listening habits.
        </div>
        <span class="lia-message-kudos-count">12 kudos</span>
      </div>
      <div class="lia-message-view-wrapper" id="message-2">
        <time datetime="2026-06-10T08:30:00Z"></time>
        <a class="lia-user-name-link">listener43</a>
        <div class="lia-message-body-content">
          Same problem here after months of skipping tracks and searching outside the app, because the same loop
          keeps returning when I want unfamiliar artists.
        </div>
      </div>
    </body></html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if "searchpage" in str(request.url):
            return httpx.Response(200, text=search_html)
        return httpx.Response(200, text=topic_html)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    records, errors = collect_spotify_community(
        searches=["same songs"],
        from_date=date(2026, 1, 1),
        to_date=date(2026, 6, 19),
        limit=10,
        min_words=20,
        client=client,
    )

    assert not errors
    usable = [record for record in records if record.quality_passed]
    assert {record.external_id for record in usable} == {
        "spotify_community:message-1",
        "spotify_community:message-2",
    }
    assert usable[0].engagement_score > 0


def test_spotify_community_html_fallback_and_snippet_use():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/api/2.0/search"):
            return httpx.Response(500, text="blocked")
        if "searchpage" in str(request.url):
            return httpx.Response(
                200,
                text="""
                <html><body>
                  <div>
                    <a href="/t5/Ideas/Better-discovery/idi-p/123">Better discovery for repeated recommendations</a>
                    <p>Spotify keeps recommending the same songs from my old playlists and I want better music discovery with newer artists.</p>
                  </div>
                </body></html>
                """,
            )
        return httpx.Response(403, text="blocked")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    records, errors = collect_spotify_community(
        searches=["same songs"],
        from_date=date(2026, 1, 1),
        to_date=date(2026, 6, 19),
        limit=1,
        min_words=10,
        client=client,
    )

    assert not errors
    assert len(records) == 1
    assert records[0].quality_passed
