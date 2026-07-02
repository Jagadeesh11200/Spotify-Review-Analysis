from src.defaults import DEFAULT_SEARCHES_BY_SOURCE, SOURCE_GROUPS


def test_source_groups_cover_each_ingestion_source_once():
    grouped_sources = [source for group in SOURCE_GROUPS for source in group["sources"]]

    assert set(grouped_sources) == set(DEFAULT_SEARCHES_BY_SOURCE)
    assert len(grouped_sources) == len(set(grouped_sources))


def test_reddit_searches_are_discovery_and_repetition_focused():
    joined = " ".join(DEFAULT_SEARCHES_BY_SOURCE["reddit"]).lower()

    assert "discover" in joined
    assert "recommend" in joined
    assert "same" in joined or "repeat" in joined
    assert "taste" in joined or "algorithm" in joined
