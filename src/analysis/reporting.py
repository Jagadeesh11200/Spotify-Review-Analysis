from __future__ import annotations

from typing import Any


def render_markdown_report(aggregate: dict[str, Any]) -> str:
    lines: list[str] = []
    summary = aggregate.get("summary", {})
    lines.append("# Spotify Discovery Feedback Analysis")
    lines.append("")
    lines.append(f"Analyzed {summary.get('quantitative_records', 0)} high-confidence records out of {summary.get('total_extractions', 0)} usable feedback items.")
    lines.append("")
    add_product_lens(lines, aggregate.get("product_lens", {}))
    add_q1(lines, aggregate.get("q1_discovery_barriers", {}))
    add_q2(lines, aggregate.get("q2_recommendation_frustrations", {}))
    add_q3(lines, aggregate.get("q3_listening_intents", {}))
    add_q4(lines, aggregate.get("q4_repetitive_listening", {}))
    add_q5(lines, aggregate.get("q5_segment_differences", {}))
    add_q6(lines, aggregate.get("q6_unmet_needs", {}))
    add_synthesis(lines, aggregate.get("synthesis", {}))
    return "\n".join(lines)


def add_product_lens(lines: list[str], product_lens: dict[str, Any]) -> None:
    lines.append("## Controlled Freshness PM Summary")
    freshness = product_lens.get("controlled_freshness", {})
    lines.append(f"- Controlled freshness demand: {freshness.get('controlled_freshness_rate', 0)}% of dashboard-ready records")
    lines.append(f"- Unwanted repetition: {freshness.get('unwanted_repetition_rate', 0)}%")
    lines.append(f"- Recommendation trust gap: {freshness.get('trust_gap_rate', 0)}%")
    lines.append("")
    lines.append("### Top product opportunity areas")
    for row in product_lens.get("opportunity_areas", [])[:6]:
        lines.append(f"- {row.get('opportunity', 'unclear')}: {row.get('records', 0)} records")
    lines.append("")


def add_q1(lines: list[str], q1: dict[str, Any]) -> None:
    lines.append("## Q1 - Why users struggle to discover new music")
    for row in q1.get("ranked_pm_barriers", [])[:5]:
        lines.append(f"- {row.get('barrier', 'unclear')}: {row.get('percentage', 0)}% severity-weighted PM barrier")
    for row in q1.get("ranked_barriers", [])[:5]:
        lines.append(f"- {row.get('barrier', 'unclear')}: {row.get('percentage', 0)}% severity-weighted mentions")
    lines.append("")


def add_q2(lines: list[str], q2: dict[str, Any]) -> None:
    lines.append("## Q2 - Most common recommendation frustrations")
    for row in q2.get("ongoing_ranked", [])[:7]:
        lines.append(f"- {row.get('frustration', 'unclear')}: {row.get('percentage', 0)}% of ongoing severity-weighted frustration")
    lines.append("")


def add_q3(lines: list[str], q3: dict[str, Any]) -> None:
    lines.append("## Q3 - Listening behaviors users are trying to achieve")
    for row in q3.get("intent_matrix", [])[:5]:
        lines.append(
            f"- {row.get('activity_context', 'unclear')} x {row.get('discovery_mode', 'unclear')}: "
            f"{row.get('count', 0)} records, dominant frustration {row.get('dominant_frustration', 'unclear')}"
        )
    lines.append("")


def add_q4(lines: list[str], q4: dict[str, Any]) -> None:
    split = q4.get("intentional_vs_unintentional", {})
    lines.append("## Q4 - What causes repetitive listening")
    lines.append(f"- Intentional repetition: {split.get('intentional', 0)}")
    lines.append(f"- Unintentional or opportunity-state repetition: {split.get('unintentional', 0)}")
    for row in q4.get("ranked_repetition_types", [])[:5]:
        lines.append(f"- {row.get('type', 'unclear')}: {row.get('count', 0)} mentions, severity weight {row.get('severity_weight', 0)}")
    lines.append("")


def add_q5(lines: list[str], q5: dict[str, Any]) -> None:
    lines.append("## Q5 - Segment-specific discovery challenges")
    lines.append(f"- Segment classification rate: {q5.get('classification_rate', 0)}%")
    counts = q5.get("classified_counts", {})
    for segment, count in counts.items():
        lines.append(f"- {segment}: {count} classified records")
    lines.append("")
    lines.append("")


def add_q6(lines: list[str], q6: dict[str, Any]) -> None:
    lines.append("## Q6 - Consistent unmet needs")
    for row in q6.get("recurring_need_phrases", [])[:8]:
        mention_value = row.get("weighted_mentions", row.get("mentions", 0))
        lines.append(f"- {row.get('need', 'unclear')}: {mention_value} weighted mentions")
    lines.append("")


def add_synthesis(lines: list[str], synthesis: dict[str, Any]) -> None:
    lines.append("## Synthesis")
    lines.append(f"- Dominant barrier: {synthesis.get('dominant_barrier')}")
    lines.append(f"- Dominant frustration: {synthesis.get('dominant_frustration')}")
    lines.append(f"- Dominant discovery mode: {synthesis.get('dominant_discovery_mode')}")
    lines.append(f"- Average issue intensity: {synthesis.get('average_severity')} out of 5")
    lines.append(f"- {synthesis.get('model_note')}")
