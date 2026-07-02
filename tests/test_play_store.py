from datetime import date, datetime

from src.sources.play_store import collect_play_store


def test_play_store_collector_normalizes_quality_reviews():
    def fake_reviews(*args, **kwargs):
        return (
            [
                {
                    "reviewId": "review-1",
                    "userName": "listener",
                    "at": datetime(2026, 6, 10, 10, 0, 0),
                    "content": (
                        "Spotify recommendations keep serving the same songs from my old playlist, and the app makes "
                        "music discovery feel difficult when I want new artists."
                    ),
                    "score": 2,
                    "thumbsUpCount": 4,
                }
            ],
            None,
        )

    records, errors = collect_play_store(
        from_date=date(2026, 6, 1),
        to_date=date(2026, 6, 19),
        target_usable=1,
        min_words=20,
        reviews_func=fake_reviews,
    )

    assert not errors
    assert len(records) == 1
    assert records[0].quality_passed
    assert records[0].rating == 2
