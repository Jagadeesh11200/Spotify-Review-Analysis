from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean
from typing import Any

from src.analysis.taxonomy import (
    DISCOVERY_BARRIERS_PM,
    DISCOVERY_FAILURE_MODES,
    NOVELTY_SAFETY_STATES,
    OPPORTUNITY_AREAS,
    Q1_BARRIER_TYPES,
    Q2_FRUSTRATION_CATEGORIES,
    Q3_ACTIVITY_CONTEXTS,
    Q3_DISCOVERY_MODES,
    Q4_REPETITION_TYPES,
    Q5_INTENSITY_LEVELS,
    Q5_SEGMENTS,
    REPETITION_DRIVERS,
    SUBSCRIPTION_SIGNALS,
    UNMET_NEEDS,
    USER_GOALS,
)


MIN_EXTRACTION_CONFIDENCE = 0.55
MIN_SEGMENT_SCORE = 0.70
MIN_SEGMENT_GAP = 0.25


def aggregate_analysis(extractions: list[dict[str, Any]]) -> dict[str, Any]:
    quantitative = [
        item
        for item in extractions
        if item.get("quality_for_analysis", True) and float(item.get("extraction_confidence") or 0) >= MIN_EXTRACTION_CONFIDENCE
    ]
    return {
        "summary": {
            "total_extractions": len(extractions),
            "quantitative_records": len(quantitative),
            "low_confidence_or_failed": len(extractions) - len(quantitative),
            "sources": dict(Counter(item.get("source", "unknown") for item in quantitative)),
        },
        "q1_discovery_barriers": aggregate_q1(quantitative),
        "q2_recommendation_frustrations": aggregate_q2(quantitative),
        "q3_listening_intents": aggregate_q3(quantitative),
        "q4_repetitive_listening": aggregate_q4(quantitative),
        "q5_segment_differences": aggregate_q5(quantitative),
        "q6_unmet_needs": aggregate_q6(quantitative),
        "product_lens": aggregate_product_lens(quantitative),
        "synthesis": synthesize(quantitative),
        "dashboard": build_dashboard_summary(quantitative),
    }


def aggregate_q1(items: list[dict[str, Any]]) -> dict[str, Any]:
    weighted = Counter()
    pm_weighted = Counter()
    novelty_weighted = Counter()
    by_source: dict[str, Counter] = defaultdict(Counter)
    feature_counts = Counter()
    quotes: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for item in items:
        barrier = safe_choice(item.get("primary_barrier_type"), Q1_BARRIER_TYPES, "unclear")
        pm_barrier = safe_choice(item.get("primary_discovery_barrier"), DISCOVERY_BARRIERS_PM, "unclear")
        novelty_state = safe_choice(item.get("novelty_safety_state"), NOVELTY_SAFETY_STATES, "unclear")
        severity = int(item.get("overall_severity") or 1)
        weight = weighted_severity(item)
        weighted[barrier] += weight
        pm_weighted[pm_barrier] += weight
        novelty_weighted[novelty_state] += weight
        by_source[item.get("source", "unknown")][barrier] += weight
        quote = item.get("barrier_evidence_quote") or item.get("best_verbatim_quote")
        if quote:
            quotes[barrier].append({"quote": quote, "source": item.get("source"), "severity": severity, "signal_weight": item_weight(item)})
        if barrier == "algorithmic":
            for feature in item.get("named_features", []) or []:
                feature_counts[str(feature)] += item_weight(item)

    total_weight = sum(weighted.values()) or 1
    return {
        "ranked_barriers": [
            {"barrier": key, "weighted_mentions": round(value, 2), "percentage": round(value / total_weight * 100, 1)}
            for key, value in weighted.most_common()
        ],
        "ranked_pm_barriers": counter_rows(pm_weighted, "barrier"),
        "novelty_safety_distribution": counter_rows(novelty_weighted, "state"),
        "by_source": {source: counter_to_percentages(counter) for source, counter in by_source.items()},
        "algorithmic_feature_heatmap": [{"feature": key, "weighted_mentions": round(value, 2)} for key, value in feature_counts.most_common()],
        "top_quotes": {key: top_quotes(value) for key, value in quotes.items()},
    }


def aggregate_q2(items: list[dict[str, Any]]) -> dict[str, Any]:
    ongoing = Counter()
    resolved = Counter()
    themes = Counter()
    severity_values: dict[str, list[int]] = defaultdict(list)
    quotes: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for item in items:
        for frustration in item.get("frustrations", []) or []:
            category = safe_choice(frustration.get("category"), Q2_FRUSTRATION_CATEGORIES, None)
            if not category:
                continue
            severity = clamp_int(frustration.get("severity"), 1, 5, 1)
            weight = severity * item_weight(item)
            status = str(frustration.get("status") or "unclear")
            if status == "resolved":
                resolved[category] += weight
            else:
                ongoing[category] += weight
                severity_values[category].append(severity)
            quote = frustration.get("evidence_quote")
            if quote:
                quotes[category].append({"quote": quote, "source": item.get("source"), "severity": severity, "signal_weight": item_weight(item)})
        for theme in item.get("recommendation_frustration_themes", []) or []:
            if str(theme) in DISCOVERY_FAILURE_MODES:
                themes[str(theme)] += weighted_severity(item)

    return {
        "ongoing_ranked": counter_rows(ongoing, "frustration"),
        "resolved_background": counter_rows(resolved, "frustration"),
        "user_facing_themes": counter_rows(themes, "theme"),
        "severity_distribution": {
            category: {
                "count": len(values),
                "average": round(mean(values), 2) if values else 0,
                "high_severity_count": sum(1 for value in values if value >= 4),
            }
            for category, values in severity_values.items()
        },
        "top_quotes": {key: top_quotes(value) for key, value in quotes.items()},
    }


def aggregate_q3(items: list[dict[str, Any]]) -> dict[str, Any]:
    matrix: dict[str, dict[str, dict[str, Any]]] = defaultdict(lambda: defaultdict(lambda: {"count": 0, "severity_sum": 0, "frustrations": Counter(), "quotes": []}))
    outcomes: list[dict[str, Any]] = []

    for item in items:
        context = safe_choice(item.get("activity_context"), Q3_ACTIVITY_CONTEXTS, "unclear")
        mode = safe_choice(item.get("discovery_mode"), Q3_DISCOVERY_MODES, "unclear")
        severity = int(item.get("overall_severity") or 1)
        weight = weighted_severity(item)
        cell = matrix[context][mode]
        cell["count"] += 1
        cell["severity_sum"] += weight
        for frustration in item.get("frustrations", []) or []:
            category = frustration.get("category")
            if category:
                cell["frustrations"][str(category)] += 1
        quote = item.get("intent_evidence_quote") or item.get("best_verbatim_quote")
        if quote:
            cell["quotes"].append({"quote": quote, "source": item.get("source"), "severity": severity, "signal_weight": item_weight(item)})
        outcome = item.get("desired_outcome")
        if outcome:
            outcomes.append({"outcome": outcome, "source": item.get("source"), "severity": severity, "signal_weight": item_weight(item)})

    matrix_rows = []
    for context, modes in matrix.items():
        for mode, cell in modes.items():
            matrix_rows.append(
                {
                    "activity_context": context,
                    "discovery_mode": mode,
                    "count": cell["count"],
                    "severity_sum": cell["severity_sum"],
                    "dominant_frustration": cell["frustrations"].most_common(1)[0][0] if cell["frustrations"] else "unclear",
                    "representative_quote": top_quotes(cell["quotes"], limit=1),
                }
            )
    matrix_rows.sort(key=lambda row: (row["severity_sum"], row["count"]), reverse=True)
    return {"intent_matrix": matrix_rows, "desired_outcomes": top_quotes(outcomes, key="outcome", limit=10)}


def aggregate_q4(items: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter()
    severity = Counter()
    quotes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    desire_to_change = Counter()
    for item in items:
        repetition = safe_choice(item.get("repetition_type"), Q4_REPETITION_TYPES, "unclear")
        counts[repetition] += 1
        severity[repetition] += weighted_severity(item)
        if item.get("desire_to_change_repetition"):
            desire_to_change[repetition] += item_weight(item)
        quote = item.get("repetition_evidence_quote") or item.get("best_verbatim_quote")
        if quote:
            quotes[repetition].append({"quote": quote, "source": item.get("source"), "severity": int(item.get("overall_severity") or 1), "signal_weight": item_weight(item)})

    intentional = counts["comfort_ritual"]
    unintentional = counts["algorithm_trapped"] + counts["trust_deficit"] + counts["friction_induced"]
    return {
        "intentional_vs_unintentional": {"intentional": intentional, "unintentional": unintentional},
        "ranked_repetition_types": [
            {"type": key, "count": counts[key], "severity_weight": round(severity[key], 2), "desire_to_change_weight": round(desire_to_change[key], 2)}
            for key, _ in severity.most_common()
        ],
        "top_quotes": {key: top_quotes(value) for key, value in quotes.items()},
    }


def aggregate_q5(items: list[dict[str, Any]]) -> dict[str, Any]:
    classified: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        segment = classify_segment(item)
        classified[segment].append(item)

    baseline = frustration_counter(items)
    matrix = []
    for segment in Q5_SEGMENTS + ["unclassified"]:
        segment_items = classified.get(segment, [])
        profile = frustration_counter(segment_items)
        for category in Q2_FRUSTRATION_CATEGORIES:
            baseline_value = baseline.get(category, 0)
            segment_value = profile.get(category, 0)
            matrix.append(
                {
                    "segment": segment,
                    "frustration": category,
                    "segment_weight": segment_value,
                    "baseline_weight": baseline_value,
                    "delta": segment_value - baseline_value,
                    "confidence_note": segment_confidence_note(segment),
                }
            )
    return {
        "classified_counts": {segment: len(values) for segment, values in classified.items()},
        "classification_rate": round((len(items) - len(classified.get("unclassified", []))) / len(items) * 100, 1) if items else 0.0,
        "intensity_distribution": intensity_distribution(items),
        "targeting_matrix": targeting_matrix(items),
        "segment_frustration_matrix": matrix,
        "high_confidence_thresholds": {"top_score_min": MIN_SEGMENT_SCORE, "gap_min": MIN_SEGMENT_GAP},
    }


def aggregate_q6(items: list[dict[str, Any]]) -> dict[str, Any]:
    workarounds = []
    displacements = []
    resignation = []
    needs = Counter()
    for item in items:
        for workaround in item.get("workarounds", []) or []:
            workarounds.append(with_source(workaround, item))
            need = workaround.get("underlying_need")
            if need:
                needs[str(need).lower()] += item_weight(item)
        for displacement in item.get("competitive_displacements", []) or []:
            displacements.append(with_source(displacement, item))
            need = displacement.get("need_served")
            if need:
                needs[str(need).lower()] += item_weight(item)
        for signal in item.get("resignation_signals", []) or []:
            resignation.append(with_source(signal, item))
            need = signal.get("need_statement")
            if need:
                needs[str(need).lower()] += item_weight(item)

    return {
        "workarounds": top_items(workarounds, "quote", limit=10),
        "competitive_displacements": top_items(displacements, "quote", limit=10),
        "resignation_signals": top_items(resignation, "quote", limit=10),
        "recurring_need_phrases": [{"need": key, "weighted_mentions": round(value, 2)} for key, value in needs.most_common(15)],
        "cross_path_evidence": cross_path_evidence(workarounds, displacements, resignation),
    }


def aggregate_product_lens(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "controlled_freshness": controlled_freshness_metrics(items),
        "why_users_repeat_music": list_counter_rows(items, "repetition_drivers", REPETITION_DRIVERS, "driver"),
        "why_discovery_fails": list_counter_rows(items, "discovery_failure_modes", DISCOVERY_FAILURE_MODES, "failure_mode"),
        "what_users_are_trying_to_achieve": list_counter_rows(items, "user_goals", USER_GOALS, "goal"),
        "unmet_needs": list_counter_rows(items, "unmet_need_tags", UNMET_NEEDS, "need"),
        "opportunity_areas": single_field_counter_rows(items, "opportunity_area", OPPORTUNITY_AREAS, "opportunity"),
        "subscription_signals": single_field_counter_rows(items, "subscription_signal", SUBSCRIPTION_SIGNALS, "subscription"),
        "segment_issue_map": segment_issue_map(items),
    }


def controlled_freshness_metrics(items: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(items) or 1
    safe_novelty_states = {"wants_safe_novelty", "too_familiar"}
    control_needs = {"freshness_control", "familiarity_balance", "better_variety", "mood_awareness", "language_culture_relevance", "low_effort_exploration", "deeper_discovery", "playlist_evolution", "trust_recovery"}
    escape_goals = {"fresh_music_without_effort", "passive_freshness", "safe_adjacent_genre_exploration", "similar_but_not_same", "escape_repetitive_playlists", "taste_expansion", "deep_exploration"}
    unwanted_repetition = {"algorithm_trapped", "trust_deficit", "friction_induced"}
    safe_novelty_count = sum(1 for item in items if item.get("novelty_safety_state") in safe_novelty_states)
    control_need_count = sum(1 for item in items if set(item.get("unmet_need_tags", []) or []) & control_needs)
    escape_goal_count = sum(1 for item in items if set(item.get("user_goals", []) or []) & escape_goals)
    controlled_freshness_count = sum(1 for item in items if item.get("novelty_safety_state") in safe_novelty_states or set(item.get("unmet_need_tags", []) or []) & control_needs or set(item.get("user_goals", []) or []) & escape_goals)
    unwanted_repetition_count = sum(1 for item in items if item.get("repetition_type") in unwanted_repetition or bool(set(item.get("repetition_drivers", []) or []) & {"algorithmic_reinforcement", "low_discovery_confidence", "playlist_dependency", "weak_exploration_controls", "poor_first_song_risk", "time_pressure"}))
    trust_gap_count = sum(1 for item in items if item.get("primary_discovery_barrier") == "low_recommendation_trust" or item.get("primary_barrier_type") == "trust")
    return {
        "records": len(items),
        "controlled_freshness_records": controlled_freshness_count,
        "controlled_freshness_rate": round(controlled_freshness_count / total * 100, 1),
        "safe_novelty_records": safe_novelty_count,
        "unwanted_repetition_records": unwanted_repetition_count,
        "unwanted_repetition_rate": round(unwanted_repetition_count / total * 100, 1),
        "trust_gap_records": trust_gap_count,
        "trust_gap_rate": round(trust_gap_count / total * 100, 1),
    }


def single_field_counter_rows(items: list[dict[str, Any]], field: str, allowed: list[str], label: str) -> list[dict[str, Any]]:
    counts = Counter()
    severity = Counter()
    for item in items:
        key = str(item.get(field) or "")
        if key not in allowed or key == "unknown":
            continue
        counts[key] += 1
        severity[key] += weighted_severity(item)
    total = sum(counts.values()) or 1
    return [
        {label: key, "records": counts[key], "percentage": round(counts[key] / total * 100, 1), "severity_weight": round(severity[key], 2)}
        for key, _ in severity.most_common()
    ]


def list_counter_rows(items: list[dict[str, Any]], field: str, allowed: list[str], label: str) -> list[dict[str, Any]]:
    counts = Counter()
    severity = Counter()
    quotes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        values = item.get(field) if isinstance(item.get(field), list) else []
        for value in values:
            key = str(value)
            if key not in allowed:
                continue
            counts[key] += 1
            severity[key] += weighted_severity(item)
            quote = item.get("best_verbatim_quote") or item.get("barrier_evidence_quote") or item.get("intent_evidence_quote") or item.get("repetition_evidence_quote")
            if quote:
                quotes[key].append({"quote": quote, "source": item.get("source"), "severity": int(item.get("overall_severity") or 1), "signal_weight": item_weight(item)})
    total = sum(counts.values()) or 1
    return [
        {
            label: key,
            "records": counts[key],
            "percentage": round(counts[key] / total * 100, 1),
            "severity_weight": round(severity[key], 2),
            "top_quotes": top_quotes(quotes[key], limit=2),
        }
        for key, _ in severity.most_common()
    ]


def segment_issue_map(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for segment in Q5_SEGMENTS + ["unclassified"]:
        segment_items = [item for item in items if classify_segment(item) == segment]
        repeat = Counter()
        failures = Counter()
        goals = Counter()
        for item in segment_items:
            repeat.update(value for value in item.get("repetition_drivers", []) if value in REPETITION_DRIVERS)
            failures.update(value for value in item.get("discovery_failure_modes", []) if value in DISCOVERY_FAILURE_MODES)
            goals.update(value for value in item.get("user_goals", []) if value in USER_GOALS)
        rows.append(
            {
                "segment": segment,
                "records": len(segment_items),
                "top_repeat_driver": repeat.most_common(1)[0][0] if repeat else "not_enough_signal",
                "top_discovery_failure": failures.most_common(1)[0][0] if failures else "not_enough_signal",
                "top_goal": goals.most_common(1)[0][0] if goals else "not_enough_signal",
                "average_severity": round(mean([int(item.get("overall_severity") or 1) for item in segment_items]), 2) if segment_items else 0.0,
            }
        )
    return rows


def synthesize(items: list[dict[str, Any]]) -> dict[str, Any]:
    q2 = frustration_counter(items)
    barriers = Counter()
    pm_barriers = Counter()
    modes = Counter()
    for item in items:
        barriers[item.get("primary_barrier_type", "unclear")] += weighted_severity(item)
        pm_barriers[item.get("primary_discovery_barrier", "unclear")] += weighted_severity(item)
        modes[item.get("discovery_mode", "unclear")] += item_weight(item)
    unmet_items = sum(len(item.get("workarounds", []) or []) + len(item.get("competitive_displacements", []) or []) + len(item.get("resignation_signals", []) or []) for item in items)
    churn_count = sum(1 for item in items if item.get("churn_risk"))
    total_signal_weight = sum(item_weight(item) for item in items)
    return {
        "dominant_barrier": barriers.most_common(1)[0][0] if barriers else "unclear",
        "dominant_pm_barrier": pm_barriers.most_common(1)[0][0] if pm_barriers else "unclear",
        "dominant_frustration": q2.most_common(1)[0][0] if q2 else "unclear",
        "dominant_discovery_mode": modes.most_common(1)[0][0] if modes else "unclear",
        "unmet_need_signal_count": unmet_items,
        "churn_risk_records": churn_count,
        "churn_risk_rate": round(churn_count / len(items) * 100, 1) if items else 0.0,
        "average_severity": round(mean([int(item.get("overall_severity") or 1) for item in items]), 2) if items else 0.0,
        "total_signal_weight": round(total_signal_weight, 2),
        "model_note": "Charts are weighted by issue severity and source signal strength. Upvotes, likes, replies, and thread discussion raise priority; low-confidence extractions are excluded.",
    }


def build_dashboard_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    source_counts = Counter(item.get("source", "unknown") for item in items)
    source_barriers: dict[str, Counter] = defaultdict(Counter)
    for item in items:
        source_barriers[item.get("source", "unknown")][item.get("primary_barrier_type", "unclear")] += weighted_severity(item)

    frustration_sources: dict[str, set[str]] = defaultdict(set)
    for item in items:
        source = str(item.get("source", "unknown"))
        for frustration in item.get("frustrations", []) or []:
            category = frustration.get("category")
            if category:
                frustration_sources[str(category)].add(source)

    return {
        "source_counts": [{"source": source, "records": count} for source, count in source_counts.most_common()],
        "source_barrier_matrix": [
            {"source": source, "barrier": barrier, "severity_weight": round(weight, 2)}
            for source, counter in source_barriers.items()
            for barrier, weight in counter.items()
        ],
        "cross_source_frustrations": [
            {"frustration": category, "source_count": len(sources), "sources": sorted(sources)}
            for category, sources in sorted(frustration_sources.items(), key=lambda kv: len(kv[1]), reverse=True)
        ],
        "quote_bank": quote_bank(items),
        "goldmine_records": goldmine_records(items),
        "validation": dashboard_validation(items),
    }


def classify_segment(item: dict[str, Any]) -> str:
    scores = item.get("segment_scores") if isinstance(item.get("segment_scores"), dict) else {}
    numeric = {segment: float(scores.get(segment) or 0.0) for segment in Q5_SEGMENTS}
    ranked = sorted(numeric.items(), key=lambda kv: kv[1], reverse=True)
    if not ranked:
        return "unclassified"
    top, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    gap = float(item.get("segment_confidence_gap") or (top_score - second_score))
    if top_score >= MIN_SEGMENT_SCORE and gap >= MIN_SEGMENT_GAP:
        return top
    return "unclassified"


def classify_intensity(item: dict[str, Any]) -> str:
    intensity = str(item.get("listening_intensity") or "low")
    return intensity if intensity in Q5_INTENSITY_LEVELS else "low"


def targeting_matrix(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for segment in Q5_SEGMENTS + ["unclassified"]:
        for intensity in Q5_INTENSITY_LEVELS:
            cell_items = [item for item in items if classify_segment(item) == segment and classify_intensity(item) == intensity]
            rows.append(targeting_cell(segment, intensity, cell_items))
    return rows


def dashboard_validation(items: list[dict[str, Any]]) -> dict[str, Any]:
    source_total = sum(Counter(item.get("source", "unknown") for item in items).values())
    matrix_total = sum(row["records"] for row in targeting_matrix(items))
    classified_counts = Counter(classify_segment(item) for item in items)
    classified_total = sum(classified_counts.values())
    issues = []
    if matrix_total != len(items):
        issues.append(f"Q5 matrix total {matrix_total} does not match dashboard record total {len(items)}.")
    if source_total != len(items):
        issues.append(f"Source total {source_total} does not match dashboard record total {len(items)}.")
    if classified_total != len(items):
        issues.append(f"Segment total {classified_total} does not match dashboard record total {len(items)}.")
    return {
        "records": len(items),
        "source_total": source_total,
        "q5_matrix_total": matrix_total,
        "segment_total": classified_total,
        "classified_counts": dict(classified_counts),
        "valid": not issues,
        "issues": issues,
    }


def targeting_cell(segment: str, intensity: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    severity_values = [int(item.get("overall_severity") or 1) for item in items]
    severity_weights = [weighted_severity(item) for item in items]
    barriers = Counter(item.get("primary_barrier_type", "unclear") for item in items)
    repetitions = Counter(item.get("repetition_type", "unclear") for item in items)
    frustrations = frustration_counter(items)
    churn_count = sum(1 for item in items if item.get("churn_risk"))
    workaround_count = sum(len(item.get("workarounds", []) or []) for item in items)
    addressable_repetition_count = sum(1 for item in items if item.get("repetition_type") in {"algorithm_trapped", "trust_deficit", "friction_induced"})
    return {
        "segment": segment,
        "intensity": intensity,
        "records": len(items),
        "average_severity": round(mean(severity_values), 2) if severity_values else 0.0,
        "severity_weight": round(sum(severity_weights), 2),
        "average_signal_weight": round(mean([item_weight(item) for item in items]), 2) if items else 0.0,
        "dominant_barrier": barriers.most_common(1)[0][0] if barriers else "unclear",
        "dominant_frustration": frustrations.most_common(1)[0][0] if frustrations else "unclear",
        "dominant_repetition": repetitions.most_common(1)[0][0] if repetitions else "unclear",
        "workaround_count": workaround_count,
        "workaround_rate": round(workaround_count / len(items) * 100, 1) if items else 0.0,
        "addressable_repetition_rate": round(addressable_repetition_count / len(items) * 100, 1) if items else 0.0,
        "churn_risk_records": churn_count,
        "churn_risk_rate": round(churn_count / len(items) * 100, 1) if items else 0.0,
    }


def intensity_distribution(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for intensity in Q5_INTENSITY_LEVELS:
        intensity_items = [item for item in items if classify_intensity(item) == intensity]
        severity_values = [int(item.get("overall_severity") or 1) for item in intensity_items]
        churn_count = sum(1 for item in intensity_items if item.get("churn_risk"))
        rows.append(
            {
                "intensity": intensity,
                "records": len(intensity_items),
                "average_severity": round(mean(severity_values), 2) if severity_values else 0.0,
                "signal_weight": round(sum(item_weight(item) for item in intensity_items), 2),
                "churn_risk_rate": round(churn_count / len(intensity_items) * 100, 1) if intensity_items else 0.0,
            }
        )
    return rows


def quote_bank(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    quotes = []
    for item in items:
        quote = item.get("best_verbatim_quote") or item.get("barrier_evidence_quote") or item.get("repetition_evidence_quote")
        if not quote:
            continue
        quotes.append(
            {
                "quote": quote,
                "source": item.get("source", "unknown"),
                "segment": classify_segment(item),
                "intensity": classify_intensity(item),
                "barrier": item.get("primary_barrier_type", "unclear"),
                "severity": int(item.get("overall_severity") or 1),
                "signal_weight": item_weight(item),
                "churn_risk": bool(item.get("churn_risk")),
                "record_id": item.get("record_id"),
            }
        )
    return sorted(quotes, key=lambda row: (row["severity"] * row["signal_weight"], row["churn_risk"]), reverse=True)[:25]


def goldmine_records(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in items:
        score = weighted_severity(item) + (1.0 if item.get("churn_risk") else 0.0)
        score += min(len(item.get("workarounds", []) or []) + len(item.get("competitive_displacements", []) or []), 3) * 0.35
        rows.append(
            {
                "record_id": item.get("record_id"),
                "source": item.get("source"),
                "score": round(score, 2),
                "severity": item.get("overall_severity"),
                "signal_weight": item_weight(item),
                "engagement_score": item.get("engagement_score", 0.0),
                "conversation_score": item.get("conversation_score", 0.0),
                "barrier": item.get("primary_barrier_type", "unclear"),
                "segment": classify_segment(item),
                "intensity": classify_intensity(item),
                "quote": item.get("best_verbatim_quote") or item.get("barrier_evidence_quote") or item.get("repetition_evidence_quote"),
            }
        )
    return sorted(rows, key=lambda row: row["score"], reverse=True)[:20]


def frustration_counter(items: list[dict[str, Any]]) -> Counter:
    counter = Counter()
    for item in items:
        for frustration in item.get("frustrations", []) or []:
            category = frustration.get("category")
            if category:
                counter[str(category)] += clamp_int(frustration.get("severity"), 1, 5, 1) * item_weight(item)
    return counter


def counter_rows(counter: Counter, label: str) -> list[dict[str, Any]]:
    total = sum(counter.values()) or 1
    return [{label: key, "severity_weight": round(value, 2), "percentage": round(value / total * 100, 1)} for key, value in counter.most_common()]


def counter_to_percentages(counter: Counter) -> list[dict[str, Any]]:
    total = sum(counter.values()) or 1
    return [{"category": key, "severity_weight": round(value, 2), "percentage": round(value / total * 100, 1)} for key, value in counter.most_common()]


def top_quotes(items: list[dict[str, Any]], key: str = "quote", limit: int = 3) -> list[dict[str, Any]]:
    sorted_items = sorted(items, key=lambda item: item.get("severity", 1) * float(item.get("signal_weight") or 1.0), reverse=True)
    return [{key: item.get(key, item.get("quote", "")), "source": item.get("source"), "severity": item.get("severity"), "signal_weight": item.get("signal_weight", 1.0)} for item in sorted_items[:limit]]


def top_items(items: list[dict[str, Any]], quote_key: str, limit: int = 10) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: item.get("severity", 1) * float(item.get("signal_weight") or 1.0), reverse=True)[:limit]


def cross_path_evidence(workarounds: list[dict[str, Any]], displacements: list[dict[str, Any]], resignation: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "theme": "discovery_memory_and_evaluation_layer",
            "workaround_mentions": count_contains(workarounds, ["playlist", "list", "save", "later", "note"]),
            "competitive_mentions": count_contains(displacements, ["notes", "youtube", "blog", "reddit"]),
            "resignation_mentions": count_contains(resignation, ["lost", "disappear", "later", "save"]),
        },
        {
            "theme": "context_aware_profile_separation",
            "workaround_mentions": count_contains(workarounds, ["account", "profile", "playlist", "context"]),
            "competitive_mentions": count_contains(displacements, ["apple", "youtube", "account"]),
            "resignation_mentions": count_contains(resignation, ["profile", "context", "history", "taste"]),
        },
        {
            "theme": "trusted_peer_discovery",
            "workaround_mentions": count_contains(workarounds, ["friend", "message", "reddit", "blog"]),
            "competitive_mentions": count_contains(displacements, ["reddit", "friend", "youtube", "blog"]),
            "resignation_mentions": count_contains(resignation, ["social", "friend", "trust"]),
        },
    ]


def count_contains(items: list[dict[str, Any]], terms: list[str]) -> int:
    count = 0
    for item in items:
        text = " ".join(str(value) for value in item.values()).lower()
        if any(term in text for term in terms):
            count += 1
    return count


def with_source(value: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    output = dict(value)
    output["source"] = item.get("source")
    output["severity"] = item.get("overall_severity", 1)
    output["signal_weight"] = item_weight(item)
    output["record_id"] = item.get("record_id")
    return output


def item_weight(item: dict[str, Any]) -> float:
    try:
        return max(1.0, min(float(item.get("signal_weight") or 1.0), 3.0))
    except (TypeError, ValueError):
        return 1.0


def weighted_severity(item: dict[str, Any]) -> float:
    return clamp_int(item.get("overall_severity"), 1, 5, 1) * item_weight(item)


def safe_choice(value: Any, allowed: list[str], default: str | None) -> str | None:
    text = str(value) if value is not None else ""
    return text if text in allowed else default


def clamp_int(value: Any, low: int, high: int, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def segment_confidence_note(segment: str) -> str:
    if segment in {"active_explorer", "playlist_heavy_user", "regional_language_listener", "artist_loyal_user"}:
        return "higher confidence text proxy when explicit language is present"
    if segment in {"comfort_listener", "mood_based_listener", "premium_power_user"}:
        return "moderate confidence behavioral proxy; validate with listening history"
    if segment == "casual_listener":
        return "low-effort freshness proxy; validate with behavioral data"
    return "unclassified or insufficient confidence"
