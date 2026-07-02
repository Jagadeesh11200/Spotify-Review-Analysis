from src.analysis.interactive_dashboard import build_interactive_dashboard_html, dashboard_number_contract
from tests.test_analysis_aggregation import sample_extractions


def test_interactive_dashboard_contains_validated_use_case_sections():
    html = build_interactive_dashboard_html(sample_extractions())

    assert "Segment x Listening Intensity Matrix" in html
    assert "Why Users Repeat Music" in html
    assert "Why Discovery Fails" in html
    assert "What Users Are Trying To Achieve" in html
    assert "Which Segments Face Which Issues" in html
    assert "Primary Discovery Barrier" in html
    assert "Recommendation Frustrations" in html
    assert "Listening Intent - Mode x Context" in html
    assert "Unmet Need Themes" in html
    assert "Product Opportunity Map" in html
    assert "Interview Targeting Recommendations" not in html
    assert "Verbatim Evidence" in html


def test_interactive_dashboard_omits_metadata_table_language():
    html = build_interactive_dashboard_html(sample_extractions())

    assert "Source coverage" not in html
    assert "Barrier evidence by source" not in html
    assert "Targeting matrix detail" not in html
    assert "Goldmine Feedback" not in html
    assert "validationPanel" not in html
    assert "Validation passed" not in html


def test_interactive_dashboard_has_user_friendly_repetition_labels():
    html = build_interactive_dashboard_html(sample_extractions())

    assert "Comfort / ritual listening" in html
    assert "Algorithm keeps looping" in html
    assert "Familiar fallback from low trust" in html
    assert "Discovery feels too much effort" in html
    assert "Type A" not in html
    assert "B+C+D" not in html


def test_interactive_dashboard_filters_only_by_source_and_user_category_dropdown():
    html = build_interactive_dashboard_html(sample_extractions())

    assert "User categories" in html
    assert "multi-select" in html
    assert "toggleSource(" in html
    assert "toggleSegment(" in html
    assert "toggleWeakSignal(" in html
    assert "All user categories" in html
    assert "Hide Unclassified or weak signal records" in html
    assert "Show classified segments only" not in html
    assert "Dashboard filters" in html
    assert "filter-grid" in html
    assert "filter-block" in html
    assert "filter-reset" in html
    assert "filter-row" not in html
    assert "active.segments" in html
    assert "seg-select" not in html
    assert "active.segment=this.value||null" not in html
    assert "onclick=\"active.segment" not in html
    assert "Filter applied." in html
    assert "setFilter('barrier'" not in html
    assert "setFilter('frustration'" not in html
    assert "setFilter('intent'" not in html
    assert "setFilter('repetition'" not in html
    assert "setFilter('workaround'" not in html


def test_interactive_dashboard_groups_panels_by_question_order():
    html = build_interactive_dashboard_html(sample_extractions())

    quality_index = html.index('<div class="quality-note" id="qualityNote"></div>')
    q1_index = html.index("Q1 - Why Users Struggle")
    q2_index = html.index("Q2 - Most Common")
    q3_index = html.index("Q3 - Listening")
    q4_index = html.index("Q4 - Why Users")
    q5_index = html.index("Segment x Listening Intensity Matrix")
    q6_index = html.index("Q6 - Consistent")

    assert quality_index < q1_index < q2_index < q3_index < q4_index < q5_index < q6_index


def test_interactive_dashboard_explains_issue_intensity_and_usage_intensity():
    html = build_interactive_dashboard_html(sample_extractions())

    assert "This does not mean premium power user; usage frequency and user category are separate" in html
    assert "Unclassified" in html


def test_interactive_dashboard_removes_redundant_top_sections():
    html = build_interactive_dashboard_html(sample_extractions())

    assert "Discovery review analysis" not in html
    assert "Feedback being analyzed" not in html
    assert '<div class="metrics" id="metrics"></div>' not in html
    assert '<div class="active-note" id="activeNote">' not in html
    assert "Dashboard filters:" not in html
    assert "Filter controls are the source buttons" not in html


def test_interactive_dashboard_has_closed_explanatory_legends_for_each_chart():
    html = build_interactive_dashboard_html(sample_extractions())

    assert html.count("<details class=\"legend\">") >= 12
    assert html.count("What this chart means") >= 12
    assert "<details class=\"legend\" open" not in html
    assert "Left labels are the failure themes found in reviews." in html
    assert "Rows are listening mode" in html
    assert "Each cell shows record count" in html
    assert "Use this as product discovery input" in html


def test_interactive_dashboard_explains_meaningful_vs_dashboard_record_counts():
    html = build_interactive_dashboard_html(sample_extractions())

    assert "high-confidence records from" in html
    assert "low-confidence records are kept out" in html
    assert "confidenceThreshold" in html


def test_interactive_dashboard_uses_user_friendly_labels():
    html = build_interactive_dashboard_html(sample_extractions())

    assert "Needs manual review" in html
    assert "Stuck in same taste loop" in html
    assert "Control-first listener" in html
    assert "Discovery-frustrated explorer" in html
    assert "Active explorer" not in html
    assert "Playlist-heavy user" not in html
    assert "Premium power user" in html
    assert "Freshness control" in html
    assert "Filter Bubble Lock In" not in html


def test_interactive_dashboard_intent_cells_keep_numbers_visible():
    html = build_interactive_dashboard_html(sample_extractions())

    assert "background:rgba(32,167,122" in html
    assert "font-weight:850" in html
    assert "opacity:${0.12+0.88*v/max}" not in html


def test_interactive_dashboard_has_overflow_safe_card_layout():
    html = build_interactive_dashboard_html(sample_extractions())

    assert "overflow-x:hidden" in html
    assert "grid-template-columns:repeat(2,minmax(0,1fr))" in html
    assert "grid-template-columns:minmax(112px,165px) minmax(0,1fr) minmax(58px,92px)" in html
    assert "function compactRows(rows,limit=7)" in html
    assert "table-layout:fixed" in html


def test_interactive_dashboard_q6_need_chart_uses_only_unmet_need_tags():
    html = build_interactive_dashboard_html(sample_extractions())

    assert "(r.unmetNeedTags||[]).forEach" in html
    assert "unique(r.needs.map(n=>n.label))" not in html
    assert "Controlled Freshness" not in html
    assert "Other themes" not in html


def test_interactive_dashboard_chart_insights_are_derived_from_rendered_rows():
    html = build_interactive_dashboard_html(sample_extractions())

    assert "function insightFromRows(rows,prefix,unit='records')" in html
    assert "dominates this view" in html
    assert "signal is spread across multiple themes" in html
    assert "INSIGHTS.unmet_needs" not in html
    assert "INSIGHTS.discovery_barriers" not in html


def test_interactive_dashboard_number_contract_reconciles_single_record_charts():
    contract = dashboard_number_contract(sample_extractions())

    assert contract["valid"], contract["issues"]
    assert contract["dashboard_records"] == 2
    assert contract["q5_matrix_total"] == 2
    assert contract["segment_total"] == 2
    assert contract["intensity_total"] == 2
    assert contract["barrier_total"] == 2
    assert contract["controlled_freshness_records"] == 2
    assert contract["unwanted_repetition_records"] == 2
    assert contract["trust_gap_records"] == 1
