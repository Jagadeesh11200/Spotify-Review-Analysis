import json
import re
from datetime import date, datetime

from src.analysis.interactive_dashboard import build_interactive_dashboard_html
from src.analysis.pipeline import run_review_analysis
from src.config import AppSettings
from src.ingestion import run_ingestion
from src.models import FeedbackRecord
from src.quality import apply_quality
from src.sources.play_store import collect_play_store


class ContractGemini:
    def __init__(self):
        self.calls = 0
        self.prompts: list[str] = []

    def generate_json(self, prompt: str):
        self.calls += 1
        self.prompts.append(prompt)
        record_ids = sorted({value for value in re.findall(r'"record_id":\s*"([^"]+)"', prompt) if value != "string"})
        return {"analyses": [self._item(prompt, record_id) for record_id in record_ids]}

    def _item(self, prompt: str, record_id: str) -> dict:
        if "Q1 -" in prompt:
            return {
                "record_id": record_id,
                "primary_barrier_type": "algorithmic",
                "primary_discovery_barrier": "over_personalization",
                "novelty_safety_state": "wants_safe_novelty",
                "barrier_evidence_quote": "same songs",
                "secondary_barrier_type": "trust",
                "discovery_failure_modes": ["same_songs_repeating", "discover_weekly_stale"],
                "named_features": ["Discover Weekly"],
                "q1_confidence": 0.9,
            }
        if "Q2 -" in prompt:
            return {
                "record_id": record_id,
                "frustrations": [
                    {
                        "category": "filter_bubble_lock_in",
                        "severity": 4,
                        "status": "ongoing",
                        "evidence_quote": "same songs",
                    }
                ],
                "recommendation_frustration_themes": ["same_songs_repeating"],
                "overall_severity": 4,
                "ongoing_vs_resolved": "ongoing",
                "best_verbatim_quote": "Spotify keeps recommending the same songs.",
                "q2_confidence": 0.9,
            }
        if "Q3 -" in prompt:
            return {
                "record_id": record_id,
                "activity_context": "relaxing_at_home_passively",
                "discovery_mode": "lean_back",
                "user_goals": ["passive_freshness", "escape_repetitive_playlists"],
                "effort_tolerance": "low_effort",
                "desired_outcome": "fresh music without manual searching",
                "intent_evidence_quote": "discover new music",
                "q3_confidence": 0.9,
            }
        if "Q4 -" in prompt:
            return {
                "record_id": record_id,
                "repetition_type": "algorithm_trapped",
                "repetition_drivers": ["algorithmic_reinforcement", "playlist_dependency"],
                "repetition_intentional": False,
                "desire_to_change_repetition": True,
                "repetition_evidence_quote": "same loop",
                "q4_confidence": 0.9,
            }
        if "Q5 -" in prompt:
            return {
                "record_id": record_id,
                "segment_scores": {
                    "comfort_listener": 0.1,
                    "playlist_heavy_user": 0.2,
                    "active_explorer": 0.8,
                    "mood_based_listener": 0.1,
                    "regional_language_listener": 0.1,
                    "artist_loyal_user": 0.1,
                    "casual_listener": 0.1,
                    "premium_power_user": 0.1,
                },
                "segment_evidence": {"active_explorer": ["Discover Weekly"]},
                "top_segment": "active_explorer",
                "segment_confidence_gap": 0.7,
                "listening_intensity": "high",
                "intensity_evidence_quote": "every day",
                "subscription_signal": "unknown",
                "subscription_evidence_quote": "",
                "churn_risk": True,
                "churn_signal_type": "disengagement",
                "churn_evidence_quote": "gave up",
                "q5_confidence": 0.9,
            }
        return {
            "record_id": record_id,
            "workarounds": [
                {
                    "description": "manual search outside recommendations",
                    "underlying_need": "steerable discovery",
                    "feature_hypothesis": "controls for exploration breadth",
                    "quote": "manually search",
                }
            ],
            "competitive_displacements": [],
            "resignation_signals": [],
            "unmet_need_tags": ["freshness_control", "playlist_evolution"],
            "opportunity_area": "playlist_refresh",
            "q6_confidence": 0.9,
        }


def test_phase1_to_phase2_dashboard_contract(monkeypatch, tmp_path):
    def fake_reviews(*args, **kwargs):
        return (
            [
                {
                    "reviewId": "usable-1",
                    "userName": "listener-one",
                    "at": datetime(2026, 6, 10, 10, 0, 0),
                    "content": (
                        "Spotify recommendations keep serving the same songs from my old playlists every day, "
                        "and Discover Weekly no longer helps me discover new music from unfamiliar artists."
                    ),
                    "score": 2,
                    "thumbsUpCount": 14,
                },
                {
                    "reviewId": "prefilter-junk",
                    "userName": "listener-two",
                    "at": datetime(2026, 6, 11, 10, 0, 0),
                    "content": "Great app thanks",
                    "score": 5,
                    "thumbsUpCount": 1,
                },
                {
                    "reviewId": "strict-filtered",
                    "userName": "listener-three",
                    "at": datetime(2026, 6, 12, 10, 0, 0),
                    "content": (
                        "Spotify music catalog contains audio content and public opinions around entertainment, "
                        "design, branding, pricing, updates, colors, accounts, devices, screens, pages, and settings."
                    ),
                    "score": 3,
                    "thumbsUpCount": 2,
                },
                {
                    "reviewId": "usable-2",
                    "userName": "listener-four",
                    "at": datetime(2026, 6, 13, 10, 0, 0),
                    "content": (
                        "Spotify keeps pushing the same recommendation loop after I skip tracks, so I manually search "
                        "for new artists because the app does not help me find fresh music anymore."
                    ),
                    "score": 1,
                    "thumbsUpCount": 25,
                },
            ],
            None,
        )

    def fake_collect_play_store(**kwargs):
        return collect_play_store(reviews_func=fake_reviews, **kwargs)

    monkeypatch.setattr("src.ingestion.collect_play_store", fake_collect_play_store)

    ingestion = run_ingestion(
        settings=AppSettings(GEMINI_API_KEY="unused"),
        from_date=date(2026, 6, 1),
        to_date=date(2026, 6, 30),
        searches_by_source={"play_store": []},
        enabled_sources=["play_store"],
        limit_per_source=2,
        candidate_limit_per_source=4,
        min_words=20,
        output_base_dir=tmp_path / "raw",
    )

    source_result = ingestion.source_results[0]
    assert source_result.raw_count == 2
    assert source_result.usable_count == 2
    assert source_result.filtered_count == 0

    source_payload = json.loads((tmp_path / "raw" / ingestion.session_id / "play_store.json").read_text(encoding="utf-8"))
    manifest_payload = json.loads((tmp_path / "raw" / ingestion.session_id / "manifest.json").read_text(encoding="utf-8"))
    assert source_payload["usable_count"] == 2
    assert "play_store:prefilter-junk" not in {record["external_id"] for record in source_payload["records"]}
    assert "play_store:strict-filtered" not in {record["external_id"] for record in source_payload["records"]}
    assert manifest_payload["config"]["candidate_limit_per_source"] == 4

    gemini = ContractGemini()
    analysis = run_review_analysis(
        settings=AppSettings(GEMINI_API_KEY="unused"),
        session_dir=ingestion.session_dir,
        output_base_dir=tmp_path / "analysis",
        gemini=gemini,
        batch_size=20,
        max_workers=1,
        use_cache=False,
    )

    assert gemini.calls == 7
    joined_prompts = "\n".join(gemini.prompts)
    assert "play_store:usable-1" in joined_prompts
    assert "play_store:usable-2" in joined_prompts
    assert "play_store:strict-filtered" not in joined_prompts
    assert "play_store:prefilter-junk" not in joined_prompts

    assert len(analysis["records"]) == 2
    assert len(analysis["extractions"]) == 2
    assert analysis["source_manifest"]["config"]["candidate_limit_per_source"] == 4
    assert analysis["aggregate"]["summary"]["quantitative_records"] == 2
    assert analysis["aggregate"]["q1_discovery_barriers"]["ranked_barriers"][0]["barrier"] == "algorithmic"
    assert analysis["aggregate"]["q2_recommendation_frustrations"]["ongoing_ranked"][0]["frustration"] == "filter_bubble_lock_in"
    assert analysis["aggregate"]["q5_segment_differences"]["classified_counts"]["active_explorer"] == 2
    assert analysis["aggregate"]["q6_unmet_needs"]["workarounds"]
    assert analysis["aggregate"]["product_lens"]["why_users_repeat_music"]
    assert analysis["aggregate"]["product_lens"]["why_discovery_fails"]
    assert analysis["aggregate"]["product_lens"]["what_users_are_trying_to_achieve"]

    html = build_interactive_dashboard_html(analysis["extractions"])
    assert "Discovery review analysis" not in html
    assert "Why Users Repeat Music" in html
    assert "Why Discovery Fails" in html
    assert "What Users Are Trying To Achieve" in html
    assert "Discovery-frustrated explorer" in html
    assert "Hide Unclassified or weak signal records" in html
    assert "play_store:usable-1" in html
    assert "play_store:strict-filtered" not in html
    assert "Segment" in html

    extraction_payload = json.loads((tmp_path / "analysis" / ingestion.session_id / "extractions.json").read_text(encoding="utf-8"))
    analysis_payload = json.loads((tmp_path / "analysis" / ingestion.session_id / "analysis.json").read_text(encoding="utf-8"))
    assert extraction_payload["source_manifest"]["config"]["target_usable_per_source"] == 2
    assert analysis_payload["source_manifest"]["config"]["candidate_limit_per_source"] == 4


def test_spotify_community_tokenless_ingestion_flows_to_phase2(monkeypatch, tmp_path):
    def fake_collect_spotify_community(**kwargs):
        record = FeedbackRecord(
            source="spotify_community",
            source_query=kwargs["searches"][0],
            external_id="spotify_community:message-100",
            created_at="2026-06-09T08:30:00+00:00",
            author="listener42",
            text=(
                "Spotify keeps recommending the same songs from my old playlists and Discover Weekly no longer "
                "helps me discover new music from unfamiliar artists, so I manually search outside the app."
            ),
            url="https://community.spotify.com/t5/Ideas/Better-discovery/td-p/100",
            language="en",
            metadata={
                "title": "Better discovery for repeated recommendations",
                "source_api": "khoros_api_v2",
                "kudos_count": 12,
                "reply_count": 4,
            },
        )
        return [apply_quality(record, kwargs["min_words"])], []

    monkeypatch.setattr("src.ingestion.collect_spotify_community", fake_collect_spotify_community)

    ingestion = run_ingestion(
        settings=AppSettings(GEMINI_API_KEY="unused"),
        from_date=date(2026, 6, 1),
        to_date=date(2026, 6, 30),
        searches_by_source={"spotify_community": ["same songs"]},
        enabled_sources=["spotify_community"],
        limit_per_source=1,
        candidate_limit_per_source=2,
        min_words=20,
        output_base_dir=tmp_path / "raw",
    )

    assert ingestion.source_results[0].usable_count == 1
    source_payload = json.loads((tmp_path / "raw" / ingestion.session_id / "spotify_community.json").read_text(encoding="utf-8"))
    assert source_payload["usable_records"][0]["metadata"]["source_api"] == "khoros_api_v2"

    gemini = ContractGemini()
    analysis = run_review_analysis(
        settings=AppSettings(GEMINI_API_KEY="unused"),
        session_dir=ingestion.session_dir,
        output_base_dir=tmp_path / "analysis",
        gemini=gemini,
        batch_size=10,
        max_workers=1,
        use_cache=False,
    )

    assert gemini.calls == 7
    assert "spotify_community:message-100" in "\n".join(gemini.prompts)
    assert analysis["aggregate"]["summary"]["sources"]["spotify_community"] == 1
    html = build_interactive_dashboard_html(analysis["extractions"])
    assert "spotify_community:message-100" in html


def test_reddit_apify_source_flows_to_phase2_dashboard(monkeypatch, tmp_path):
    def reddit_record(query: str) -> FeedbackRecord:
        return apply_quality(
            FeedbackRecord(
                source="reddit",
                source_query=query,
                external_id="reddit:usable-1",
                created_at="2026-06-10T10:00:00+00:00",
                author="listener",
                text=(
                    "Spotify recommendations keep looping the same playlist songs every day, and Discover Weekly "
                    "does not help me discover new music from unfamiliar artists anymore."
                ),
                url="https://example.com/reddit/usable-1",
                language="en",
                metadata={"source_actor": "apify-test", "like_count": 20, "reply_count": 5},
            ),
            min_words=20,
            context_text=query,
        )

    def fake_collect_reddit(**kwargs):
        return [reddit_record(kwargs["searches"][0])], []

    monkeypatch.setattr("src.ingestion.collect_reddit", fake_collect_reddit)

    ingestion = run_ingestion(
        settings=AppSettings(GEMINI_API_KEY="unused", APIFY_API_KEY_1="unused"),
        from_date=date(2026, 6, 1),
        to_date=date(2026, 6, 30),
        searches_by_source={
            "reddit": ["spotify algorithm same songs over and over"],
        },
        enabled_sources=["reddit"],
        limit_per_source=1,
        candidate_limit_per_source=3,
        min_words=20,
        output_base_dir=tmp_path / "raw",
    )

    assert {result.source for result in ingestion.source_results} == {"reddit"}
    assert all(result.usable_count == 1 for result in ingestion.source_results)

    gemini = ContractGemini()
    analysis = run_review_analysis(
        settings=AppSettings(GEMINI_API_KEY="unused"),
        session_dir=ingestion.session_dir,
        output_base_dir=tmp_path / "analysis",
        gemini=gemini,
        batch_size=10,
        max_workers=1,
        use_cache=False,
    )

    assert gemini.calls == 7
    joined_prompts = "\n".join(gemini.prompts)
    assert "reddit:usable-1" in joined_prompts
    assert analysis["aggregate"]["summary"]["sources"]["reddit"] == 1
    html = build_interactive_dashboard_html(analysis["extractions"])
    assert "Reddit" in html
    assert "reddit:usable-1" in html


def test_candidate_limit_caps_collected_and_meaningful_counts_even_with_high_usable_setting(monkeypatch, tmp_path):
    def fake_reviews(*args, **kwargs):
        rows = []
        for index in range(150):
            rows.append(
                {
                    "reviewId": f"review-{index}",
                    "userName": "listener",
                    "at": datetime(2026, 6, 10, 10, 0, 0),
                    "content": (
                        f"Spotify recommendations keep repeating the same songs from my old playlists every day {index}, "
                        "and Discover Weekly no longer helps me discover new music from unfamiliar artists."
                    ),
                    "score": 2,
                    "thumbsUpCount": 1,
                }
            )
        return rows, None

    def fake_collect_play_store(**kwargs):
        return collect_play_store(reviews_func=fake_reviews, **kwargs)

    monkeypatch.setattr("src.ingestion.collect_play_store", fake_collect_play_store)

    ingestion = run_ingestion(
        settings=AppSettings(GEMINI_API_KEY="unused"),
        from_date=date(2026, 6, 1),
        to_date=date(2026, 6, 30),
        searches_by_source={"play_store": []},
        enabled_sources=["play_store"],
        limit_per_source=500,
        candidate_limit_per_source=100,
        min_words=20,
        output_base_dir=tmp_path / "raw",
    )

    result = ingestion.source_results[0]
    manifest_payload = json.loads((tmp_path / "raw" / ingestion.session_id / "manifest.json").read_text(encoding="utf-8"))

    assert result.raw_count == 100
    assert result.usable_count == 100
    assert manifest_payload["config"]["target_usable_per_source"] == 100
    assert manifest_payload["config"]["configured_usable_target_per_source"] == 500
    assert manifest_payload["config"]["candidate_limit_per_source"] == 100
