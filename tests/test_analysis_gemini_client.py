from src.analysis.gemini_client import extract_records_with_gemini, parse_json_response
from src.analysis.question_prompts import build_question_prompt


class FailingThenWorkingGemini:
    def __init__(self):
        self.calls = 0

    def generate_json(self, prompt: str):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary failure")
        record_id = "r1" if '"r1"' in prompt else "r2"
        if "Q1 -" in prompt:
            item = {"record_id": record_id, "primary_barrier_type": "algorithmic", "primary_discovery_barrier": "over_personalization", "novelty_safety_state": "wants_safe_novelty", "barrier_evidence_quote": "same songs", "secondary_barrier_type": "unclear", "discovery_failure_modes": ["same_songs_repeating"], "named_features": [], "q1_confidence": 0.8}
        elif "Q2 -" in prompt:
            item = {"record_id": record_id, "frustrations": [], "recommendation_frustration_themes": ["same_songs_repeating"], "overall_severity": 3, "ongoing_vs_resolved": "ongoing", "best_verbatim_quote": "same songs", "q2_confidence": 0.8}
        elif "Q3 -" in prompt:
            item = {"record_id": record_id, "activity_context": "unclear", "discovery_mode": "lean_back", "user_goals": ["passive_freshness"], "effort_tolerance": "low_effort", "desired_outcome": "new music", "intent_evidence_quote": "new music", "q3_confidence": 0.8}
        elif "Q4 -" in prompt:
            item = {"record_id": record_id, "repetition_type": "algorithm_trapped", "repetition_drivers": ["algorithmic_reinforcement"], "repetition_intentional": False, "desire_to_change_repetition": True, "repetition_evidence_quote": "same songs", "q4_confidence": 0.8}
        elif "Q5 -" in prompt:
            item = {"record_id": record_id, "segment_scores": {"comfort_listener": 0.1, "playlist_heavy_user": 0.1, "active_explorer": 0.1, "mood_based_listener": 0.1, "regional_language_listener": 0.1, "artist_loyal_user": 0.1, "casual_listener": 0.4, "premium_power_user": 0.0}, "segment_evidence": {}, "top_segment": "unclassified", "segment_confidence_gap": 0.0, "listening_intensity": "low", "intensity_evidence_quote": "", "subscription_signal": "unknown", "subscription_evidence_quote": "", "churn_risk": False, "churn_signal_type": "none", "churn_evidence_quote": "", "q5_confidence": 0.8}
        else:
            item = {"record_id": record_id, "workarounds": [], "competitive_displacements": [], "resignation_signals": [], "unmet_need_tags": ["freshness_control"], "opportunity_area": "freshness_control", "q6_confidence": 0.8}
        return {"analyses": [item]}


def test_parse_json_response_accepts_fenced_json():
    payload = parse_json_response('```json\n{"analyses": []}\n```')

    assert payload == {"analyses": []}


def test_extract_records_splits_batch_after_failure():
    records = [
        {"record_id": "r1", "source": "reddit", "text": "Spotify recommendations repeat the same songs and block discovery."},
        {"record_id": "r2", "source": "reddit", "text": "Spotify recommendations repeat the same songs and block discovery."},
    ]
    gemini = FailingThenWorkingGemini()

    extractions, errors = extract_records_with_gemini(records, gemini=gemini, batch_size=2, max_workers=1)

    assert errors
    assert len(extractions) == 2
    assert {item["record_id"] for item in extractions} == {"r1", "r2"}


def test_extract_records_runs_all_six_question_passes():
    records = [{"record_id": "r1", "source": "reddit", "text": "Spotify repeats the same songs and I want new music."}]
    gemini = FailingThenWorkingGemini()
    gemini.calls = 1

    extractions, errors = extract_records_with_gemini(records, gemini=gemini, batch_size=1, max_workers=1)

    assert errors == []
    assert gemini.calls == 7
    assert extractions[0]["primary_barrier_type"] == "algorithmic"
    assert extractions[0]["repetition_type"] == "algorithm_trapped"
    assert extractions[0]["listening_intensity"] == "low"
    assert extractions[0]["churn_signal_type"] == "none"
    assert extractions[0]["extraction_confidence"] == 0.8


def test_prompt_contains_detailed_phase2_taxonomies():
    q2_prompt = build_question_prompt(
        "q2",
        [
            {
                "record_id": "r1",
                "source": "reddit",
                "text": "Spotify keeps recommending the same songs and I want new music discovery.",
            }
        ]
    )
    q4_prompt = build_question_prompt("q4", [{"record_id": "r1", "source": "reddit", "text": "same songs"}])
    q6_prompt = build_question_prompt("q6", [{"record_id": "r1", "source": "reddit", "text": "same songs"}])
    q5_prompt = build_question_prompt("q5", [{"record_id": "r1", "source": "reddit", "text": "same songs"}])
    q3_prompt = build_question_prompt("q3", [{"record_id": "r1", "source": "reddit", "text": "same songs"}])
    q1_prompt = build_question_prompt("q1", [{"record_id": "r1", "source": "reddit", "text": "same songs"}])

    assert "filter_bubble_lock_in" in q2_prompt
    assert "comfort_ritual" in q4_prompt
    assert "Competitive displacement" in q6_prompt or "competitive displacement" in q6_prompt
    assert "top proxy score is >= 0.70" in q5_prompt
    assert "Listening intensity" in q5_prompt
    assert "churn_risk" in q5_prompt
    assert "Subscription signal is an attribute, not the main segment" in q5_prompt
    assert "controlled freshness" in q1_prompt.lower()
    assert "novelty_safety_state" in q1_prompt
    assert "unmet_need_tags" in q6_prompt
    assert "Do not overuse unclear" in q3_prompt
    assert "commuting_or_traveling: car, drive, commute" in q3_prompt
    assert "lean_back: user wants good music to find them passively" in q3_prompt


def test_prompt_compacts_discussion_metadata_for_llm_context():
    prompt = build_question_prompt(
        "q1",
        [
            {
                "record_id": "forum-1",
                "source": "spotify_community",
                "source_query": "same songs",
                "text": "Same problem here after months of skipping tracks because the same loop keeps returning.",
                "specificity_score": 0.8,
                "engagement_score": 0.5,
                "conversation_score": 0.4,
                "signal_weight": 2.1,
                "metadata": {
                    "title": "Discover Weekly repeats",
                    "kudos_count": 12,
                    "reply_count": 8,
                    "message_position": 2,
                },
            }
        ],
    )

    assert "Discover Weekly repeats" in prompt
    assert '"upvote_or_like_signal": 12' in prompt
    assert '"reply_or_comment_signal": 8' in prompt
    assert '"message_position": 2' in prompt
    assert '"signal_weight": 2.1' in prompt
