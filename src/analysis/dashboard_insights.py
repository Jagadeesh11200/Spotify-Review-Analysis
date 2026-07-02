from __future__ import annotations

import json
from typing import Any

from src.analysis.gemini_client import GeminiLike


DASHBOARD_INSIGHT_KEYS = [
    "top_cards",
    "q5_anchor",
    "segment_profiles",
    "intensity_distribution",
    "discovery_barriers",
    "recommendation_frustrations",
    "listening_intents",
    "repetition_patterns",
    "unmet_needs",
    "verbatim_evidence",
]


def generate_dashboard_insights(aggregate: dict[str, Any], gemini: GeminiLike) -> tuple[dict[str, str], list[str]]:
    try:
        payload = gemini.generate_json(build_dashboard_insight_prompt(aggregate))
        return normalize_dashboard_insights(payload), []
    except Exception as exc:
        return default_dashboard_insights(), [f"dashboard insights: {exc}"]


def build_dashboard_insight_prompt(aggregate: dict[str, Any]) -> str:
    compact = {
        "summary": aggregate.get("summary", {}),
        "synthesis": aggregate.get("synthesis", {}),
        "q1": aggregate.get("q1_discovery_barriers", {}).get("ranked_barriers", [])[:5],
        "q2": aggregate.get("q2_recommendation_frustrations", {}).get("ongoing_ranked", [])[:7],
        "q3": aggregate.get("q3_listening_intents", {}).get("intent_matrix", [])[:8],
        "q4": aggregate.get("q4_repetitive_listening", {}).get("ranked_repetition_types", [])[:6],
        "q5": {
            "classified_counts": aggregate.get("q5_segment_differences", {}).get("classified_counts", {}),
            "classification_rate": aggregate.get("q5_segment_differences", {}).get("classification_rate"),
            "targeting_matrix": aggregate.get("q5_segment_differences", {}).get("targeting_matrix", []),
        },
        "q6": aggregate.get("q6_unmet_needs", {}).get("recurring_need_phrases", [])[:10],
        "product_lens": aggregate.get("product_lens", {}),
        "validation": aggregate.get("dashboard", {}).get("validation", {}),
    }
    return f"""
Dashboard insight pass for Spotify discovery review analysis.

Write concise, user-facing explanations for dashboard panels. The dashboard is for Growth PMs studying controlled freshness: users want novelty that still feels safe, relevant, mood-aware, culturally aware, and worth their time.

Rules:
- Do not invent numbers. Only explain patterns visible in the provided aggregate.
- Use plain language. Avoid analytics jargon when possible.
- Explain "issue intensity" as how strongly the review describes recommendation/discovery pain or behavior change.
- Clarify that listening intensity is usage frequency and is separate from segment. A high-intensity listener is not automatically a power user.
- Explain insights in terms of controlled freshness, unwanted repetition, discovery trust, user goals, and product opportunity areas.
- Keep each explanation to one sentence, maximum 28 words.
- Return only JSON.

Return this JSON shape:
{{
  "insights": {{
    "top_cards": "string",
    "q5_anchor": "string",
    "segment_profiles": "string",
    "intensity_distribution": "string",
    "discovery_barriers": "string",
    "recommendation_frustrations": "string",
    "listening_intents": "string",
    "repetition_patterns": "string",
    "unmet_needs": "string",
    "verbatim_evidence": "string"
  }}
}}

Aggregate:
{json.dumps(compact, ensure_ascii=False)}
"""


def normalize_dashboard_insights(payload: dict[str, Any]) -> dict[str, str]:
    raw = payload.get("insights") if isinstance(payload.get("insights"), dict) else {}
    defaults = default_dashboard_insights()
    output: dict[str, str] = {}
    for key in DASHBOARD_INSIGHT_KEYS:
        value = raw.get(key)
        output[key] = clean_sentence(value) if isinstance(value, str) and value.strip() else defaults[key]
    return output


def clean_sentence(value: str) -> str:
    text = " ".join(value.split())
    words = text.split()
    if len(words) > 32:
        text = " ".join(words[:32]).rstrip(".,;:") + "."
    return text


def default_dashboard_insights() -> dict[str, str]:
    return {
        "top_cards": "Top cards show controlled-freshness demand, unwanted repetition, trust gap, and the strongest opportunity area for the current filters.",
        "q5_anchor": "Use the category dropdown to filter behavior-based discovery segments; the matrix compares each category with listening frequency.",
        "segment_profiles": "Segments show the user job behind discovery friction: comfort, playlist dependence, active exploration, mood, region, artist loyalty, casual use, or premium power use.",
        "intensity_distribution": "Listening intensity estimates frequency of use; it is separate from power-user behavior or product knowledge.",
        "discovery_barriers": "Barriers show the primary mechanism blocking meaningful discovery, counted once per feedback record.",
        "recommendation_frustrations": "Frustrations can have multiple labels per record, so totals represent mentions rather than unique reviews.",
        "listening_intents": "Intent cells show whether users wanted passive freshness, active exploration, or incidental discovery in a specific context.",
        "repetition_patterns": "Repetition separates chosen comfort from unwanted loops caused by confidence, playlists, time pressure, or algorithmic reinforcement.",
        "unmet_needs": "Unmet needs show where users want controlled freshness: freshness, familiarity balance, variety, mood, language, transparency, depth, or trust repair.",
        "verbatim_evidence": "Quotes are selected from the highest-signal records matching the active source and user category filters.",
    }
