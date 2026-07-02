from datetime import date

import httpx

from src.sources.youtube import collect_youtube


def test_youtube_collector_collects_comments_with_quality_filter():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/search"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": {"videoId": "video-1"},
                            "snippet": {
                                "title": "Spotify recommendations problem",
                                "description": "Why Spotify keeps playing the same songs instead of new music.",
                                "channelTitle": "Music UX",
                                "publishedAt": "2026-06-01T10:00:00Z",
                            },
                        }
                    ]
                },
            )
        if request.url.path.endswith("/commentThreads"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "snippet": {
                                "topLevelComment": {
                                    "id": "comment-1",
                                    "snippet": {
                                        "authorDisplayName": "User",
                                        "publishedAt": "2026-06-10T10:00:00Z",
                                        "textOriginal": (
                                            "Spotify recommendations keep repeating the same songs from my old playlists, "
                                            "and I cannot discover new music unless I leave the app and search elsewhere."
                                        ),
                                    },
                                }
                            }
                        }
                    ]
                },
            )
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    records, errors = collect_youtube(
        api_key="key",
        searches=["Spotify recommendations problem"],
        from_date=date(2026, 6, 1),
        to_date=date(2026, 6, 19),
        limit=10,
        min_words=20,
        videos_per_query=1,
        client=client,
    )

    assert not errors
    assert len(records) == 1
    assert records[0].quality_passed
    assert records[0].metadata["video_title"] == "Spotify recommendations problem"
    comment_request = next(request for request in requests if request.url.path.endswith("/commentThreads"))
    assert comment_request.url.params["order"] == "relevance"


def test_youtube_collector_uses_video_context_for_meaningful_comments():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/search"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": {"videoId": "video-1"},
                            "snippet": {
                                "title": "Spotify algorithm keeps recommending the same songs",
                                "description": "A discussion about Spotify discovery and recommendation loops.",
                                "channelTitle": "Music UX",
                                "publishedAt": "2026-06-01T10:00:00Z",
                            },
                        }
                    ]
                },
            )
        if request.url.path.endswith("/commentThreads"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "snippet": {
                                "topLevelComment": {
                                    "id": "comment-contextual",
                                    "snippet": {
                                        "authorDisplayName": "User",
                                        "publishedAt": "2026-06-10T10:00:00Z",
                                        "textOriginal": (
                                            "This is exactly why I switched to another app after months of skipping "
                                            "tracks, because the same loop kept coming back every day and I could "
                                            "not escape my old listening habits."
                                        ),
                                    },
                                }
                            }
                        },
                        {
                            "snippet": {
                                "topLevelComment": {
                                    "id": "comment-generic",
                                    "snippet": {
                                        "authorDisplayName": "Other",
                                        "publishedAt": "2026-06-10T10:00:00Z",
                                        "textOriginal": (
                                            "Great video, thanks for explaining this so clearly. I learned a lot from "
                                            "the examples and the discussion in the comments was really helpful."
                                        ),
                                    },
                                }
                            }
                        },
                    ]
                },
            )
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    records, errors = collect_youtube(
        api_key="key",
        searches=["Spotify recommendations problem"],
        from_date=date(2026, 6, 1),
        to_date=date(2026, 6, 19),
        limit=10,
        min_words=20,
        videos_per_query=1,
        client=client,
    )

    assert not errors
    records_by_id = {record.external_id: record for record in records}
    assert records_by_id["youtube_comment:comment-contextual"].quality_passed
    assert "youtube_comment:comment-generic" not in records_by_id
