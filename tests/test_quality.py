from src.models import FeedbackRecord
from src.quality import apply_quality, assess_prefilter, assess_quality


def test_quality_rejects_short_feedback():
    result = assess_quality("bad app", language="en", min_words=20)

    assert not result.passed
    assert result.reason == "too_short"


def test_prefilter_rejects_obvious_junk_before_quality_gate():
    result = assess_prefilter(
        "Great video thanks for sharing these useful examples today because the explanation was clear and helpful",
        context_text="Spotify recommendations problem",
    )

    assert not result.passed
    assert result.reason == "generic_context_comment_prefilter"


def test_prefilter_allows_contextual_discussion_feedback():
    text = (
        "This is exactly why I switched after months of skipping tracks because the same loop kept coming back "
        "every day and I could not escape old habits."
    )
    result = assess_prefilter(text, context_text="Spotify recommendations problem")

    assert result.passed


def test_quality_accepts_specific_discovery_feedback():
    text = (
        "Spotify recommendations keep pushing the same songs every day, and Discover Weekly no longer helps me "
        "find new artists because the playlist feels locked to my old listening habits."
    )

    result = assess_quality(text, language="en", min_words=20)

    assert result.passed
    assert result.reason == "passed"


def test_quality_rejects_non_english_language_code():
    text = "Spotify recommendations keep repeating the same songs and playlists even when I want new music discovery."

    result = assess_quality(text, language="es", min_words=5)

    assert not result.passed
    assert result.reason == "not_english"


def test_quality_rejects_long_but_vague_feedback():
    text = (
        "Spotify music catalog contains audio content and public opinions around entertainment, design, "
        "branding, pricing, updates, colors, accounts, devices, screens, pages, and settings."
    )

    result = assess_quality(text, language="en", min_words=20)

    assert not result.passed
    assert result.reason == "missing_discovery_or_listening_signal"


def test_quality_rejects_generic_app_access_review_without_discovery_signal():
    text = (
        "I have always been a Spotify lover, but now I cannot even open or access the app and I am really "
        "frustrated because I used to listen every morning and night on my phone."
    )

    result = assess_quality(text, language="en", min_words=20)

    assert not result.passed
    assert result.reason == "missing_discovery_or_listening_signal"


def test_quality_accepts_youtube_comment_with_relevant_video_context():
    text = (
        "This is exactly why I switched to Apple Music after months of skipping tracks, because the same loop kept "
        "coming back every day and I could not escape my old listening habits."
    )
    context = "Spotify recommendations problem algorithm keeps playing the same songs and blocks new music discovery"

    result = assess_quality(text, language=None, min_words=20, context_text=context)

    assert result.passed
    assert result.reason == "passed"


def test_quality_rejects_generic_youtube_comment_even_with_relevant_context():
    text = (
        "Great video, thanks for explaining this so clearly. I learned a lot from the examples and the discussion "
        "in the comments was also really helpful today."
    )
    context = "Spotify recommendations problem algorithm keeps playing the same songs and blocks new music discovery"

    result = assess_quality(text, language=None, min_words=20, context_text=context)

    assert not result.passed
    assert result.reason == "missing_specific_behavior_signal"


def test_quality_does_not_match_short_behavior_terms_inside_other_words():
    text = (
        "This was a useful explanation with beautiful examples and a thoughtful discussion from everyone in the "
        "comments, and the creator made the whole topic easy to understand with clear examples today."
    )
    context = "Spotify recommendations problem algorithm keeps playing the same songs and blocks new music discovery"

    result = assess_quality(text, language=None, min_words=20, context_text=context)

    assert not result.passed
    assert result.reason == "missing_specific_behavior_signal"


def test_apply_quality_adds_engagement_and_signal_weight():
    record = FeedbackRecord(
        source="reddit",
        source_query="spotify recommendations",
        external_id="r1",
        text=(
            "Spotify recommendations keep repeating the same songs every day and I gave up on Discover Weekly "
            "because it no longer helps me find new artists outside my old listening habits."
        ),
        language="en",
        metadata={"score": 100, "num_comments": 50},
    )

    result = apply_quality(record, min_words=20)

    assert result.quality_passed
    assert result.specificity_score > 0.7
    assert result.engagement_score == 1.0
    assert result.conversation_score == 1.0
    assert result.signal_weight > 2.0
