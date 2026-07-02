from datetime import date

from src.sources.reddit import REDDIT_ACTOR_ID, collect_reddit, has_reddit_discovery_focus, parse_old_reddit_search


def test_old_reddit_search_parser_extracts_relevant_post_fields():
    html = """
    <div class="search-result search-result-link" data-fullname="t3_abc">
      <header class="search-result-header">
        <a class="search-title" href="https://old.reddit.com/r/truespotify/comments/abc/title/">Why are Spotify recommendations bad?</a>
      </header>
      <div class="search-result-meta">
        <span class="search-score">12 points</span>
        <a class="search-comments">9 comments</a>
        <span class="search-time"><time datetime="2026-06-10T10:00:00+00:00">1 day ago</time></span>
        <span class="search-author">by <a class="author">listener</a></span>
      </div>
      <div class="search-result-body">
        Spotify recommendations keep repeating the same playlist songs and I cannot discover new music.
      </div>
    </div>
    """

    items = parse_old_reddit_search(html, "spotify recommendations bad", "truespotify")

    assert len(items) == 1
    assert items[0]["id"] == "t3_abc"
    assert items[0]["score"] == 12
    assert items[0]["num_comments"] == 9
    assert items[0]["subreddit"] == "r/truespotify"
    assert items[0]["source_api"] == "old_reddit_public_html"


def test_reddit_collector_falls_back_to_apify_when_public_path_has_no_records(monkeypatch):
    calls = []

    def fake_public(**kwargs):
        return None

    class FakeApify:
        def run_actor_items(self, actor_id, actor_input, **kwargs):
            calls.append((actor_id, actor_input, kwargs))
            return [
                {
                    "id": "post-1",
                    "type": "post",
                    "searchTerm": "spotify recommendations bad",
                    "title": "Spotify recommendations are stuck in a loop",
                    "selftext": (
                        "Discover Weekly keeps recycling old playlist songs and I cannot find new artists "
                        "without leaving Spotify."
                    ),
                    "created_utc": "2026-06-10T10:00:00Z",
                    "author": "listener",
                    "score": 120,
                    "num_comments": 42,
                    "permalink": "/r/spotify/comments/post-1/thread/",
                },
                {
                    "id": "comment-1",
                    "type": "comment",
                    "searchTerm": "spotify recommendations bad",
                    "postTitle": "Spotify recommendations are stuck in a loop",
                    "body": (
                        "This is exactly why I switched after months of skipping tracks, because the same loop "
                        "kept coming back every day and I could not escape old listening habits."
                    ),
                    "created_utc": "2026-06-10T11:00:00Z",
                    "author": "reply-user",
                    "score": 30,
                    "reply_count": 3,
                },
            ]

    monkeypatch.setattr("src.sources.reddit.collect_public_reddit", fake_public)

    records, errors = collect_reddit(
        client=FakeApify(),
        searches=["spotify recommendations bad", "spotify ai dj repeats"],
        from_date=date(2026, 6, 1),
        to_date=date(2026, 6, 19),
        limit=10,
        min_words=20,
        comments_per_post=5,
    )

    assert not errors
    assert calls[0][0] == REDDIT_ACTOR_ID
    assert calls[0][1]["searches"] == ["spotify recommendations bad"]
    assert calls[0][1]["searchPosts"] is True
    assert calls[0][1]["searchComments"] is True
    assert calls[0][1]["includeMediaLinks"] is True
    assert calls[0][1]["maxComments"] == 5
    assert calls[0][2]["timeout_seconds"] == 120
    assert calls[0][2]["max_total_charge_usd"] == 0.15
    usable = [record for record in records if record.quality_passed]
    contextual_comment = next(record for record in usable if record.external_id == "reddit_comment:comment-1")
    assert contextual_comment.metadata["post_title"] == "Spotify recommendations are stuck in a loop"
    assert contextual_comment.engagement_score > 0


def test_reddit_collector_suppresses_empty_query_warnings_when_source_has_records(monkeypatch):
    from src.models import FeedbackRecord
    from src.quality import apply_quality

    def fake_public(records, errors, seen, searches, min_words, **kwargs):
        errors.append("reddit public search 'empty query': no usable records from focused subreddits.")
        record = FeedbackRecord(
            source="reddit",
            source_query=searches[0],
            external_id="reddit_post:public-1",
            created_at="2026-06-10T10:00:00+00:00",
            author="listener",
            text=(
                "Spotify recommendations keep repeating the same songs from my old playlists and Discover Weekly "
                "does not help me discover new music from unfamiliar artists anymore."
            ),
            language="en",
            metadata={"score": 12, "num_comments": 4, "source_api": "old_reddit_public_html"},
        )
        records.append(apply_quality(record, min_words, context_text=searches[0]))

    monkeypatch.setattr("src.sources.reddit.collect_public_reddit", fake_public)

    class FakeApify:
        def run_actor_items(self, actor_id, actor_input, **kwargs):
            return []

    records, errors = collect_reddit(
        client=FakeApify(),
        searches=["spotify recommendations bad"],
        from_date=date(2026, 6, 1),
        to_date=date(2026, 6, 19),
        limit=10,
        min_words=20,
    )

    assert errors == []
    assert records[0].quality_passed


def test_reddit_relevance_gate_excludes_spotify_support_announcements():
    text = (
        "Playlist Folders are Now Available on Spotify Mobile. Read the full post in the Spotify Community. "
        "Spotify Support Article: Playlist Folders. Genres, shuffle, playlists, and recommendations are mentioned "
        "inside a long support document, but this is not user feedback about discovery problems."
    )

    assert not has_reddit_discovery_focus(text)


def test_reddit_lite_actor_output_fields_are_normalized():
    from src.sources.reddit import normalize_reddit_item

    post = normalize_reddit_item(
        {
            "id": "t3_post",
            "parsedId": "post",
            "dataType": "post",
            "searchTerm": "spotify discover weekly recommendations",
            "title": "Spotify Discover Weekly keeps repeating songs",
            "body": (
                "The recommendations are stuck on the same artists and I cannot discover new music "
                "that matches my taste without digging through Reddit threads."
            ),
            "createdAt": "2026-06-10T05:23:15.000Z",
            "username": "listener",
            "communityName": "r/truespotify",
            "upVotes": 150,
            "upVoteRatio": 0.92,
            "numberOfComments": 41,
            "url": "https://www.reddit.com/r/truespotify/comments/post/title/",
        },
        "spotify recommendations",
    )
    comment = normalize_reddit_item(
        {
            "id": "t1_comment",
            "dataType": "comment",
            "parentId": "t3_post",
            "category": "truespotify",
            "body": (
                "I keep getting the same playlist songs every day, so I use song radio and manual searches "
                "to find anything fresh."
            ),
            "createdAt": "2026-06-10T06:00:00.000Z",
            "username": "reply-user",
            "upVotes": 25,
        },
        "spotify recommendations",
    )

    assert post.external_id == "reddit_post:t3_post"
    assert post.metadata["kind"] == "post"
    assert post.metadata["score"] == 150
    assert post.metadata["upvote_ratio"] == 0.92
    assert post.metadata["num_comments"] == 41
    assert post.metadata["subreddit"] == "r/truespotify"
    assert post.metadata["source_actor"] == REDDIT_ACTOR_ID
    assert comment.external_id == "reddit_comment:t1_comment"
    assert comment.metadata["kind"] == "comment"
    assert comment.metadata["post_id"] == "t3_post"
    assert comment.metadata["score"] == 25
