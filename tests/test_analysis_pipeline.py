import json

from src.analysis.aggregation import aggregate_analysis
from src.analysis.pipeline import ANALYSIS_CACHE_VERSION, run_review_analysis
from src.config import AppSettings
from tests.test_analysis_aggregation import sample_extractions


class FakeGemini:
    def __init__(self):
        self.calls = 0

    def generate_json(self, prompt: str):
        self.calls += 1
        if "Q1 -" in prompt:
            item = {"record_id": "r1", "primary_barrier_type": "algorithmic", "primary_discovery_barrier": "over_personalization", "novelty_safety_state": "wants_safe_novelty", "barrier_evidence_quote": "same recommendations", "secondary_barrier_type": "unclear", "discovery_failure_modes": ["same_songs_repeating"], "named_features": ["Discover Weekly"], "q1_confidence": 0.9}
        elif "Q2 -" in prompt:
            item = {"record_id": "r1", "frustrations": [{"category": "filter_bubble_lock_in", "severity": 4, "status": "ongoing", "evidence_quote": "same songs"}], "recommendation_frustration_themes": ["same_songs_repeating"], "overall_severity": 4, "ongoing_vs_resolved": "ongoing", "best_verbatim_quote": "same recommendations", "q2_confidence": 0.9}
        elif "Q3 -" in prompt:
            item = {"record_id": "r1", "activity_context": "unclear", "discovery_mode": "lean_back", "user_goals": ["passive_freshness"], "effort_tolerance": "low_effort", "desired_outcome": "better new music", "intent_evidence_quote": "find new music", "q3_confidence": 0.9}
        elif "Q4 -" in prompt:
            item = {"record_id": "r1", "repetition_type": "algorithm_trapped", "repetition_drivers": ["algorithmic_reinforcement"], "repetition_intentional": False, "desire_to_change_repetition": True, "repetition_evidence_quote": "loop", "q4_confidence": 0.9}
        elif "Q5 -" in prompt:
            item = {"record_id": "r1", "segment_scores": {"comfort_listener": 0.1, "playlist_heavy_user": 0.1, "active_explorer": 0.8, "mood_based_listener": 0.1, "regional_language_listener": 0.1, "artist_loyal_user": 0.1, "casual_listener": 0.1, "premium_power_user": 0.1}, "segment_evidence": {}, "top_segment": "active_explorer", "segment_confidence_gap": 0.7, "listening_intensity": "high", "intensity_evidence_quote": "all day", "subscription_signal": "unknown", "subscription_evidence_quote": "", "churn_risk": True, "churn_signal_type": "disengagement", "churn_evidence_quote": "gave up", "q5_confidence": 0.9}
        else:
            item = {"record_id": "r1", "workarounds": [], "competitive_displacements": [], "resignation_signals": [], "unmet_need_tags": ["freshness_control"], "opportunity_area": "freshness_control", "q6_confidence": 0.9}
        return {"analyses": [item]}


def test_run_review_analysis_saves_outputs(tmp_path):
    session = tmp_path / "raw" / "session_1"
    session.mkdir(parents=True)
    (session / "reddit.json").write_text(
        json.dumps(
            {
                "usable_records": [
                    {
                        "external_id": "r1",
                        "source": "reddit",
                        "text": "Spotify recommendations keep playing the same songs and I cannot discover new music anymore.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = run_review_analysis(
        settings=AppSettings(GEMINI_API_KEY="unused"),
        session_dir=session,
        output_base_dir=tmp_path / "analysis",
        gemini=FakeGemini(),
        batch_size=4,
    )

    assert result["aggregate"]["summary"]["quantitative_records"] == 1
    assert result["aggregate"]["q5_segment_differences"]["targeting_matrix"]
    assert result["aggregate"]["synthesis"]["churn_risk_records"] == 1
    assert "Q1" in result["markdown"]
    assert (tmp_path / "analysis" / "session_1" / "analysis.json").exists()


def test_run_review_analysis_ignores_stale_cached_extractions(tmp_path):
    session = tmp_path / "raw" / "session_cached"
    session.mkdir(parents=True)
    (session / "reddit.json").write_text(
        json.dumps(
            {
                "usable_records": [
                    {
                        "external_id": "r1",
                        "source": "reddit",
                        "text": "Spotify recommendations keep repeating the same songs and I cannot discover new music anymore.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "analysis" / "session_cached"
    output_dir.mkdir(parents=True)
    extractions = sample_extractions()
    (output_dir / "extractions.json").write_text(json.dumps({"analysis_cache_version": "old", "errors": [], "extractions": extractions}), encoding="utf-8")
    (output_dir / "analysis.json").write_text(json.dumps({"aggregate": aggregate_analysis(extractions)}), encoding="utf-8")
    (output_dir / "report.md").write_text("old report", encoding="utf-8")

    gemini = FakeGemini()
    result = run_review_analysis(
        settings=AppSettings(GEMINI_API_KEY="unused"),
        session_dir=session,
        output_base_dir=tmp_path / "analysis",
        gemini=gemini,
    )

    assert not result.get("cached")
    assert gemini.calls == 7
    extraction_payload = json.loads((output_dir / "extractions.json").read_text(encoding="utf-8"))
    assert extraction_payload["analysis_cache_version"] == ANALYSIS_CACHE_VERSION
