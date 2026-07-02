from src.analysis.aggregation import aggregate_analysis


def sample_extractions():
    return [
        {
            "record_id": "r1",
            "source": "reddit",
            "quality_for_analysis": True,
            "primary_barrier_type": "algorithmic",
            "primary_discovery_barrier": "over_personalization",
            "novelty_safety_state": "wants_safe_novelty",
            "barrier_evidence_quote": "it only recommends the same songs",
            "discovery_failure_modes": ["same_songs_repeating", "discover_weekly_stale"],
            "recommendation_frustration_themes": ["same_songs_repeating", "discover_weekly_stale"],
            "named_features": ["Discover Weekly"],
            "frustrations": [
                {"category": "filter_bubble_lock_in", "severity": 4, "status": "ongoing", "evidence_quote": "same songs"},
                {"category": "recommendation_opacity", "severity": 2, "status": "ongoing", "evidence_quote": "no idea why"},
            ],
            "activity_context": "relaxing_at_home_passively",
            "discovery_mode": "lean_back",
            "user_goals": ["passive_freshness", "escape_repetitive_playlists"],
            "effort_tolerance": "low_effort",
            "desired_outcome": "new music should find me without work",
            "intent_evidence_quote": "I just want new music to play",
            "repetition_type": "algorithm_trapped",
            "repetition_drivers": ["algorithmic_reinforcement", "playlist_dependency"],
            "repetition_intentional": False,
            "desire_to_change_repetition": True,
            "repetition_evidence_quote": "stuck in a loop",
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
            "segment_confidence_gap": 0.6,
            "listening_intensity": "high",
            "subscription_signal": "unknown",
            "churn_risk": True,
            "churn_signal_type": "disengagement",
            "specificity_score": 0.9,
            "engagement_score": 1.0,
            "conversation_score": 1.0,
            "signal_weight": 2.5,
            "workarounds": [
                {
                    "description": "manual to explore playlist",
                    "underlying_need": "discovery memory layer",
                    "feature_hypothesis": "discovery inbox",
                    "quote": "I save tracks to a playlist for later",
                }
            ],
            "competitive_displacements": [],
            "resignation_signals": [],
            "unmet_need_tags": ["freshness_control", "playlist_evolution"],
            "opportunity_area": "playlist_refresh",
            "overall_severity": 4,
            "best_verbatim_quote": "Spotify is stuck in a loop",
            "extraction_confidence": 0.9,
        },
        {
            "record_id": "r2",
            "source": "app_store",
            "quality_for_analysis": True,
            "primary_barrier_type": "trust",
            "primary_discovery_barrier": "low_recommendation_trust",
            "novelty_safety_state": "too_unfamiliar",
            "discovery_failure_modes": ["mood_mismatch"],
            "recommendation_frustration_themes": ["mood_mismatch"],
            "frustrations": [{"category": "autoplay_regression", "severity": 5, "status": "ongoing", "evidence_quote": "autoplay is awful"}],
            "activity_context": "focused_work_or_studying",
            "discovery_mode": "incidental",
            "user_goals": ["match_current_mood"],
            "effort_tolerance": "low_effort",
            "repetition_type": "trust_deficit",
            "repetition_drivers": ["low_discovery_confidence", "time_pressure"],
            "segment_scores": {
                "comfort_listener": 0.1,
                "playlist_heavy_user": 0.1,
                "active_explorer": 0.1,
                "mood_based_listener": 0.8,
                "regional_language_listener": 0.1,
                "artist_loyal_user": 0.1,
                "casual_listener": 0.2,
                "premium_power_user": 0.1,
            },
            "segment_confidence_gap": 0.6,
            "listening_intensity": "medium",
            "subscription_signal": "premium",
            "churn_risk": True,
            "churn_signal_type": "switching",
            "specificity_score": 0.8,
            "engagement_score": 0.0,
            "conversation_score": 0.0,
            "signal_weight": 1.0,
            "workarounds": [],
            "competitive_displacements": [{"platform_or_method": "YouTube", "need_served": "contextual music discovery", "migration_status": "returned_to_spotify", "quote": "I use YouTube first"}],
            "resignation_signals": [{"accepted_limitation": "Spotify will not understand context", "need_statement": "context-aware profile separation", "quote": "I gave up expecting it"}],
            "unmet_need_tags": ["mood_awareness", "trust_recovery"],
            "opportunity_area": "mood_aware_discovery",
            "overall_severity": 5,
            "best_verbatim_quote": "I stopped trusting autoplay",
            "extraction_confidence": 0.85,
        },
    ]


def test_aggregate_analysis_answers_all_six_questions():
    aggregate = aggregate_analysis(sample_extractions())

    assert aggregate["summary"]["quantitative_records"] == 2
    assert aggregate["q1_discovery_barriers"]["ranked_barriers"]
    assert aggregate["q1_discovery_barriers"]["ranked_pm_barriers"][0]["barrier"] == "over_personalization"
    assert aggregate["q1_discovery_barriers"]["novelty_safety_distribution"]
    assert aggregate["q2_recommendation_frustrations"]["ongoing_ranked"][0]["frustration"] == "filter_bubble_lock_in"
    assert aggregate["q2_recommendation_frustrations"]["user_facing_themes"]
    assert aggregate["q3_listening_intents"]["intent_matrix"]
    assert aggregate["q4_repetitive_listening"]["intentional_vs_unintentional"]["unintentional"] == 2
    assert aggregate["q5_segment_differences"]["classified_counts"]["active_explorer"] == 1
    assert aggregate["q6_unmet_needs"]["recurring_need_phrases"]
    assert aggregate["product_lens"]["controlled_freshness"]["controlled_freshness_records"] == 2
    assert aggregate["product_lens"]["controlled_freshness"]["unwanted_repetition_records"] == 2
    assert aggregate["product_lens"]["controlled_freshness"]["trust_gap_records"] == 1
    assert aggregate["product_lens"]["why_users_repeat_music"][0]["driver"] == "algorithmic_reinforcement"
    assert aggregate["product_lens"]["why_discovery_fails"]
    assert aggregate["product_lens"]["what_users_are_trying_to_achieve"]
    assert aggregate["product_lens"]["segment_issue_map"]
    assert aggregate["product_lens"]["opportunity_areas"][0]["opportunity"] == "playlist_refresh"
    assert aggregate["synthesis"]["dominant_frustration"] == "filter_bubble_lock_in"
    assert aggregate["dashboard"]["source_barrier_matrix"]
    assert aggregate["dashboard"]["cross_source_frustrations"]
    assert aggregate["q5_segment_differences"]["classification_rate"] == 100.0
    assert aggregate["q5_segment_differences"]["targeting_matrix"]
    assert "interview_recommendations" not in aggregate["q5_segment_differences"]
    assert aggregate["synthesis"]["churn_risk_rate"] == 100.0
    assert aggregate["synthesis"]["total_signal_weight"] == 3.5
    assert aggregate["dashboard"]["quote_bank"]
    assert aggregate["dashboard"]["goldmine_records"][0]["record_id"] == "r1"
    assert sum(row["records"] for row in aggregate["q5_segment_differences"]["targeting_matrix"]) == aggregate["summary"]["quantitative_records"]
    assert aggregate["dashboard"]["validation"]["valid"]
    assert aggregate["dashboard"]["validation"]["records"] == aggregate["summary"]["quantitative_records"]
