from datetime import date, timedelta
from pathlib import Path
import traceback
from typing import Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from src.analysis.aggregation import MIN_EXTRACTION_CONFIDENCE, aggregate_analysis, classify_intensity, classify_segment
from src.analysis.interactive_dashboard import build_interactive_dashboard_html
from src.analysis.pipeline import run_review_analysis
from src.config import get_settings
from src.default_session import load_default_run, write_default_session
from src.defaults import DEFAULT_MIN_WORDS, DEFAULT_SEARCHES_BY_SOURCE, SOURCE_GROUPS, SOURCE_LABELS
from src.home_docs import ARCHITECTURE_ROUTE, USER_GUIDE_ROUTE, architecture_flow_html, flowchart_html, get_doc_page
from src.ingestion import run_ingestion
from src.source_utils import overfetch_candidate_limit
from src.ui_navigation import COLLECT_PAGE, DASHBOARD_PAGE, PAGE_OPTIONS, prepare_page_state, request_page_navigation


st.set_page_config(
    page_title="Spotify Review Analysis",
    layout="wide",
)


SEGMENT_LABELS = {
    "power_user": "Power user",
    "genre_enthusiast": "Genre enthusiast",
    "playlist_heavy_user": "Control-first listener",
    "active_explorer": "Discovery-frustrated explorer",
    "mood_based_listener": "Mood-based listener",
    "casual_listener": "Casual listener",
    "unclassified": "Unclassified",
}

INTENSITY_LABELS = {"high": "High intensity", "medium": "Medium intensity", "low": "Low intensity"}

SOURCE_UI_HINTS = {
    "app_store": ("Store reviews", "Short, high-volume mobile feedback"),
    "play_store": ("Store reviews", "Android review signal and ratings"),
    "reddit": ("Discussion", "Longer user reasoning and workarounds"),
    "youtube": ("Comments", "Video-led discussion around Spotify discovery"),
    "spotify_community": ("Forum", "Feature requests and support-style threads"),
}


DEFAULT_RUN_LOADED_KEY = "_default_run_loaded"
FRESH_TOOL_KEY = "_fresh_tool_requested"
FULL_DASHBOARD_IFRAME_HEIGHT = 4800
MIN_TARGET_RECORD_LIMIT = 5
DEFAULT_TARGET_RECORD_LIMIT = 300
FRESH_RUN_TARGET_RECORD_LIMIT = 25


def apply_home_style() -> None:
    st.markdown(
        """
        <style>
        :root {
            --spotify-green: #1DB954;
            --spotify-green-dark: #137a3a;
            --app-bg: #F7F8F6;
            --panel-bg: #FFFFFF;
            --panel-soft: #F1F4EF;
            --ink: #18201B;
            --muted: #657067;
            --line: #DDE4DC;
            --warning: #E49B22;
            --danger: #E0524D;
        }
        html, body, [data-testid="stAppViewContainer"] {
            background: var(--app-bg);
            color: var(--ink);
        }
        [data-testid="stHeader"] {
            background: rgba(247,248,246,.94);
            border-bottom: 1px solid rgba(221,228,220,.85);
        }
        [data-testid="stToolbar"] {
            right: 1rem;
        }
        .block-container {
            padding-top: 3.25rem;
            padding-bottom: 3rem;
            max-width: 1240px;
        }
        .app-hero {
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--panel-bg);
            padding: 22px 24px 18px;
            margin: 0 0 14px;
            box-shadow: 0 10px 28px rgba(24,32,27,.055);
        }
        .app-eyebrow {
            color: var(--spotify-green-dark);
            font-size: 12px;
            font-weight: 800;
            letter-spacing: .04em;
            text-transform: uppercase;
            margin-bottom: 8px;
        }
        .app-title {
            font-size: 36px;
            line-height: 1.08;
            font-weight: 780;
            margin: 0;
            letter-spacing: 0;
        }
        .app-subtitle {
            max-width: 980px;
            color: var(--muted);
            font-size: 17px;
            line-height: 1.55;
            margin: 14px 0 16px;
        }
        .app-chips {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }
        .app-chip {
            border: 1px solid rgba(29,185,84,.24);
            border-radius: 999px;
            background: rgba(29,185,84,.08);
            color: var(--spotify-green-dark);
            font-size: 13px;
            font-weight: 750;
            padding: 7px 12px;
        }
        .home-links {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 10px;
            margin: 4px 0 14px;
        }
        .default-analysis-card {
            border: 1px solid rgba(29,185,84,.28);
            border-left: 5px solid var(--spotify-green);
            border-radius: 8px;
            background: linear-gradient(135deg, rgba(29,185,84,.12), rgba(255,255,255,.98) 58%, rgba(19,122,58,.05));
            padding: 20px 22px;
            margin: 0 0 16px;
            box-shadow: 0 14px 34px rgba(24,32,27,.075);
            position: relative;
            overflow: hidden;
        }
        .default-analysis-card::after {
            content: "";
            position: absolute;
            right: -38px;
            top: -54px;
            width: 150px;
            height: 150px;
            border-radius: 50%;
            background: rgba(29,185,84,.10);
        }
        .default-analysis-layout {
            position: relative;
            z-index: 1;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 18px;
        }
        .default-analysis-main {
            min-width: 0;
        }
        .default-analysis-stat {
            min-width: 158px;
            border: 1px solid rgba(29,185,84,.26);
            background: rgba(255,255,255,.82);
            border-radius: 8px;
            padding: 12px 14px;
            text-align: right;
            box-shadow: 0 8px 22px rgba(24,32,27,.055);
        }
        .default-analysis-stat strong {
            display: block;
            color: var(--spotify-green-dark);
            font-size: 26px;
            line-height: 1;
        }
        .default-analysis-stat span {
            display: block;
            color: var(--muted);
            font-size: 11px;
            margin-top: 5px;
        }
        .default-analysis-kicker {
            color: var(--spotify-green-dark);
            font-size: 12px;
            font-weight: 850;
            letter-spacing: .04em;
            text-transform: uppercase;
            margin-bottom: 4px;
        }
        .default-analysis-title {
            font-size: 18px;
            font-weight: 850;
            color: var(--ink);
            margin-bottom: 8px;
        }
        .default-analysis-copy {
            color: var(--muted);
            font-size: 14px;
            line-height: 1.5;
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 9px;
        }
        .default-analysis-card a {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            color: #fff;
            background: var(--spotify-green-dark);
            font-weight: 850;
            text-decoration: none;
            border: 1px solid var(--spotify-green-dark);
            border-radius: 999px;
            padding: 7px 13px;
            box-shadow: 0 5px 14px rgba(19,122,58,.18);
        }
        .default-analysis-card a:hover {
            color: #fff;
            background: var(--spotify-green);
            border-color: var(--spotify-green);
        }
        .default-analysis-note {
            color: var(--muted);
        }
        .home-help-item {
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--panel-bg);
            box-shadow: 0 1px 2px rgba(24,32,27,.035);
        }
        .home-help-item details {
            padding: 0;
        }
        .home-help-item summary {
            cursor: pointer;
            list-style: none;
            padding: 11px 13px;
        }
        .home-help-item summary::-webkit-details-marker {
            display: none;
        }
        .home-help-top {
            display: flex;
            justify-content: space-between;
            gap: 12px;
            align-items: center;
        }
        .home-help-title {
            min-width: 0;
        }
        .home-help-title strong {
            display: block;
            font-size: 15px;
            line-height: 1.2;
        }
        .home-help-title span {
            display: block;
            font-size: 12px;
            color: var(--muted);
            margin-top: 3px;
        }
        .home-help-link {
            white-space: nowrap;
            color: var(--spotify-green-dark) !important;
            font-size: 12px;
            font-weight: 700;
            text-decoration: none !important;
        }
        .home-help-link:hover {
            text-decoration: underline !important;
        }
        .home-help-body {
            border-top: 1px solid rgba(221,228,220,.8);
            padding: 0 13px 12px;
        }
        .home-help-body ul {
            margin: 9px 0 0;
            padding-left: 17px;
            font-size: 12px;
            opacity: .78;
            line-height: 1.45;
        }
        .home-caption {
            max-width: 850px;
            margin: -4px 0 10px;
            font-size: 13px;
            color: var(--muted);
            line-height: 1.45;
        }
        div[role="radiogroup"] {
            gap: 8px;
            margin: 2px 0 10px;
        }
        div[role="radiogroup"] label {
            border: 1px solid var(--line);
            border-radius: 999px;
            background: var(--panel-bg);
            padding: 6px 12px;
            margin-right: 4px;
        }
        div[data-testid="stForm"] {
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--panel-bg);
            padding: 18px 16px 16px;
            box-shadow: 0 8px 22px rgba(24,32,27,.045);
        }
        div[data-testid="stDateInput"] input,
        div[data-testid="stNumberInput"] input {
            border-radius: 7px;
            border-color: var(--line);
            background: #FAFBF9;
            min-height: 42px;
        }
        div[data-testid="stTabs"] button {
            font-weight: 720;
            color: #334038;
        }
        div[data-testid="stTabs"] button[aria-selected="true"] {
            color: var(--spotify-green-dark);
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--line);
            border-radius: 8px;
            background: #FEFFFD;
            box-shadow: 0 1px 2px rgba(24,32,27,.03);
        }
        .source-card-head {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 8px;
            margin-bottom: 8px;
        }
        .source-name {
            display: block;
            font-weight: 760;
            font-size: 15px;
        }
        .source-desc {
            display: block;
            color: var(--muted);
            font-size: 12px;
            line-height: 1.35;
            margin-top: 3px;
        }
        .source-badge {
            border-radius: 999px;
            background: rgba(29,185,84,.09);
            color: var(--spotify-green-dark);
            border: 1px solid rgba(29,185,84,.18);
            font-size: 11px;
            font-weight: 760;
            padding: 3px 8px;
            white-space: nowrap;
        }
        div[data-testid="stDataFrame"] {
            border-radius: 8px;
            overflow: hidden;
        }
        div[data-testid="stAlert"] {
            border-radius: 8px;
        }
        button[kind="primary"], button[data-testid="baseButton-primary"] {
            border-radius: 7px;
            font-weight: 780;
            min-height: 42px;
        }
        button[data-testid="baseButton-secondary"] {
            border-radius: 7px;
        }
        .doc-flow {
            display: flex;
            gap: 9px;
            align-items: stretch;
            flex-wrap: wrap;
            margin: 10px 0 20px;
        }
        .flow-card, .doc-architecture div {
            border: 1px solid rgba(29,185,84,.18);
            border-radius: 8px;
            background: linear-gradient(180deg, #fff, rgba(29,185,84,.035));
            padding: 14px 14px;
            box-shadow: 0 5px 16px rgba(24,32,27,.045);
        }
        .flow-card {
            flex: 1 1 150px;
        }
        .flow-card em, .doc-architecture em {
            display: block;
            color: #137a3a;
            font-size: 11px;
            font-style: normal;
            font-weight: 850;
            margin-bottom: 4px;
            text-transform: uppercase;
            letter-spacing: .02em;
        }
        .flow-card b, .doc-architecture b {
            display: block;
            font-size: 15px;
            margin-bottom: 5px;
        }
        .flow-card span, .doc-architecture span {
            display: block;
            font-size: 12.5px;
            opacity: .74;
            line-height: 1.42;
        }
        .flow-arrow {
            display: flex;
            align-items: center;
            color: #1DB954;
            font-weight: 700;
        }
        .doc-architecture {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 10px;
            margin: 8px 0 18px;
        }
        .doc-pill-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin: 8px 0 18px;
        }
        .doc-pill {
            border: 1px solid rgba(29,185,84,.20);
            background: rgba(29,185,84,.07);
            color: var(--spotify-green-dark);
            border-radius: 999px;
            padding: 6px 10px;
            font-size: 12px;
            font-weight: 780;
        }
        @media (max-width: 900px) {
            .block-container {
                padding-top: 2rem;
            }
            .app-hero {
                padding: 18px 16px;
            }
            .app-title {
                font-size: 29px;
            }
            .home-links {
                grid-template-columns: 1fr;
            }
            .doc-architecture {
                grid-template-columns: 1fr;
            }
            .flow-arrow {
                display: none;
            }
            .default-analysis-layout {
                align-items: flex-start;
                flex-direction: column;
            }
            .default-analysis-stat {
                text-align: left;
                width: 100%;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def load_default_run_into_state() -> None:
    if st.session_state.get(FRESH_TOOL_KEY):
        st.session_state[DEFAULT_RUN_LOADED_KEY] = True
        return
    if st.session_state.get(DEFAULT_RUN_LOADED_KEY):
        return
    st.session_state[DEFAULT_RUN_LOADED_KEY] = True
    default_run = load_default_run()
    if not default_run:
        return
    ingestion_result, analysis_result = default_run
    st.session_state["current_ingestion_result"] = ingestion_result
    st.session_state["current_session_dir"] = ingestion_result.session_dir
    st.session_state["analysis_result"] = analysis_result
    st.session_state["loaded_default_session_id"] = ingestion_result.session_id
    if st.session_state.get("app_page") not in PAGE_OPTIONS:
        st.session_state["app_page"] = DASHBOARD_PAGE


def apply_fresh_tool_request() -> None:
    fresh_value = st.query_params.get("fresh_run")
    if isinstance(fresh_value, list):
        fresh_requested = "1" in fresh_value
    else:
        fresh_requested = str(fresh_value or "") == "1"
    if not fresh_requested and not st.session_state.get(FRESH_TOOL_KEY):
        return
    st.session_state[FRESH_TOOL_KEY] = True
    st.session_state[DEFAULT_RUN_LOADED_KEY] = True
    for key in ("current_ingestion_result", "current_session_dir", "analysis_result", "loaded_default_session_id"):
        st.session_state.pop(key, None)
    if st.session_state.get("app_page") not in PAGE_OPTIONS:
        st.session_state["app_page"] = COLLECT_PAGE


def render_default_analysis_prompt() -> None:
    if st.session_state.get(FRESH_TOOL_KEY):
        return
    ingestion_result = st.session_state.get("current_ingestion_result")
    analysis_result = st.session_state.get("analysis_result")
    if not ingestion_result or not analysis_result:
        return
    st.markdown(
        f"""
        <div class="default-analysis-card">
            <div class="default-analysis-layout">
                <div class="default-analysis-main">
                    <div class="default-analysis-kicker">Executed analysis loaded by default</div>
                    <div class="default-analysis-title">Start with the ready dashboard. The live-data run is already collected, analyzed, and waiting for review.</div>
                    <div class="default-analysis-copy">
                        <span>Want to test the full pipeline yourself?</span>
                        <a href="?fresh_run=1">Open a blank tool and run Collect + Analyze</a>
                        <span class="default-analysis-note">Fresh runs are capped for demos and may use live API quota.</span>
                    </div>
                </div>
                <div class="default-analysis-stat">
                    <strong>{ingestion_result.total_usable:,}</strong>
                    <span>meaningful records analyzed</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def apply_dashboard_style() -> None:
    st.markdown(
        """
        <style>
        .metric-card {
            border: 1px solid rgba(128,128,128,.22);
            border-radius: 8px;
            padding: 12px 14px;
            background: rgba(128,128,128,.07);
            min-height: 86px;
        }
        .metric-label {
            font-size: 12px;
            opacity: .72;
            margin-bottom: 6px;
        }
        .metric-value {
            font-size: 28px;
            font-weight: 650;
            line-height: 1.1;
        }
        .metric-detail {
            font-size: 12px;
            opacity: .68;
            margin-top: 5px;
        }
        .panel-note {
            border-left: 3px solid #1DB954;
            background: rgba(29,185,84,.08);
            border-radius: 6px;
            padding: 9px 11px;
            font-size: 13px;
            margin: 8px 0 12px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def current_doc_route() -> str | None:
    value = st.query_params.get("doc")
    if isinstance(value, list):
        return value[0] if value else None
    return value


def render_home_links() -> None:
    st.markdown(
        f"""
        <div class="home-caption">
            Need context? Open a guide directly, or expand an item for a quick preview.
        </div>
        <div class="home-links">
            <div class="home-help-item">
                <details>
                    <summary>
                        <div class="home-help-top">
                            <div class="home-help-title">
                                <strong>How to operate this tool</strong>
                                <span>For demo users</span>
                            </div>
                            <a class="home-help-link" href="?doc={USER_GUIDE_ROUTE}" target="_self">Open guide</a>
                        </div>
                    </summary>
                    <div class="home-help-body">
                        <ul>
                            <li>What to select before collection</li>
                            <li>How to read meaningful vs filtered records</li>
                            <li>How to use dashboard filters and evidence</li>
                        </ul>
                    </div>
                </details>
            </div>
            <div class="home-help-item">
                <details>
                    <summary>
                        <div class="home-help-top">
                            <div class="home-help-title">
                                <strong>Backend architecture one-pager</strong>
                                <span>For PMs and reviewers</span>
                            </div>
                            <a class="home-help-link" href="?doc={ARCHITECTURE_ROUTE}" target="_self">Open synopsis</a>
                        </div>
                    </summary>
                    <div class="home-help-body">
                        <ul>
                            <li>Where each source comes from</li>
                            <li>How quality filtering and Gemini passes work</li>
                            <li>Why dashboard numbers stay tied to real records</li>
                        </ul>
                    </div>
                </details>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_app_header() -> None:
    st.markdown(
        """
        <section class="app-hero">
            <div class="app-eyebrow">AI-powered discovery feedback engine</div>
            <h1 class="app-title">Spotify Review Analysis</h1>
            <div class="app-subtitle">
                Collect live public feedback, keep only meaningful discovery signals, and turn them into a dashboard that explains why users repeat music, where discovery fails, and which listener groups need different solutions.
            </div>
            <div class="app-chips">
                <span class="app-chip">Discovery failures</span>
                <span class="app-chip">Repetition drivers</span>
                <span class="app-chip">Segment evidence</span>
                <span class="app-chip">Verbatim proof</span>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_doc_page(route: str) -> bool:
    doc = get_doc_page(route)
    if not doc:
        return False

    apply_home_style()
    st.title(doc.title)
    st.markdown("[<- Back to collection](?doc=)")
    if route == USER_GUIDE_ROUTE:
        st.markdown(flowchart_html(), unsafe_allow_html=True)
    elif route == ARCHITECTURE_ROUTE:
        st.markdown(architecture_flow_html(), unsafe_allow_html=True)
    st.markdown(doc.markdown)
    return True


def searches_from_editor(source: str, default_searches: list[str]) -> list[str]:
    label = SOURCE_LABELS[source]
    if not default_searches:
        return []

    df = pd.DataFrame({"Search phrase": default_searches})
    edited = st.data_editor(
        df,
        key=f"search_editor_{source}",
        hide_index=True,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Search phrase": st.column_config.TextColumn(
                "Search phrase",
                help=f"Queries used for {label}. Add rows or delete rows before running analysis.",
                required=False,
            )
        },
    )
    return [
        str(value).strip()
        for value in edited.get("Search phrase", []).tolist()
        if str(value).strip() and str(value).strip().lower() != "nan"
    ]


def render_source_controls() -> tuple[list[str], dict[str, list[str]]]:
    enabled_sources: list[str] = []
    searches_by_source: dict[str, list[str]] = {}

    group_tabs = st.tabs([f"{group['name']} - {group['tag']}" for group in SOURCE_GROUPS])

    for group, tab in zip(SOURCE_GROUPS, group_tabs):
        with tab:
            st.caption(group["description"])
            sources = [source for source in group["sources"] if source in DEFAULT_SEARCHES_BY_SOURCE]
            columns = st.columns(len(sources))
            for source, column in zip(sources, columns):
                label = SOURCE_LABELS[source]
                default_searches = DEFAULT_SEARCHES_BY_SOURCE[source]
                badge, description = SOURCE_UI_HINTS.get(source, ("Source", "Public feedback source"))
                with column:
                    with st.container(border=True):
                        st.markdown(
                            f"""
                            <div class="source-card-head">
                                <div>
                                    <span class="source-name">{label}</span>
                                    <span class="source-desc">{description}</span>
                                </div>
                                <span class="source-badge">{badge}</span>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        enabled = st.checkbox("Include", value=True, key=f"enabled_{source}")
                        if default_searches:
                            searches = searches_from_editor(source, default_searches)
                        else:
                            st.caption("Collected directly for the Spotify app.")
                            searches = []
                        if enabled:
                            enabled_sources.append(source)
                        searches_by_source[source] = searches

    return enabled_sources, searches_by_source


def render_collection_summary(result) -> None:
    st.success(f"Collected {result.total_usable} meaningful feedback records.")

    rows = []
    for source_result in result.source_results:
        rows.append(
            {
                "Source": SOURCE_LABELS.get(source_result.source, source_result.source),
                "Meaningful": source_result.usable_count,
                "Candidate pool": source_result.raw_count,
                "Filtered": source_result.filtered_count,
                "Warnings": len(source_result.errors),
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    warning_sources = [source_result for source_result in result.source_results if source_result.errors]
    if warning_sources:
        with st.expander("Collection warnings"):
            for source_result in warning_sources:
                st.markdown(f"**{SOURCE_LABELS.get(source_result.source, source_result.source)}**")
                for error in source_result.errors[:10]:
                    st.warning(error)


def render_analysis_dashboard(result: dict[str, Any], show_downloads: bool = True) -> None:
    quantitative = quantitative_extractions(result.get("extractions", []))
    if not quantitative:
        st.warning("No high-confidence extractions are available for dashboard analysis.")
        return

    if show_downloads:
        header_left, header_right = st.columns([0.72, 0.28], vertical_alignment="top")
        header_left.markdown("### Dashboard")
        with header_right:
            with st.expander("Downloads", expanded=False):
                render_download_buttons(result)

    components.html(
        build_interactive_dashboard_html(result.get("extractions", []), result.get("dashboard_insights")),
        height=FULL_DASHBOARD_IFRAME_HEIGHT,
        scrolling=False,
    )


def quantitative_extractions(extractions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in extractions
        if item.get("quality_for_analysis", True) and float(item.get("extraction_confidence") or 0) >= MIN_EXTRACTION_CONFIDENCE
    ]


def filter_dashboard_extractions(
    extractions: list[dict[str, Any]],
    selected_segment: str,
    selected_intensity: str,
    selected_barrier: str,
    selected_frustration: str,
    selected_repetition: str,
) -> list[dict[str, Any]]:
    filtered = []
    for item in extractions:
        if selected_segment != "All" and classify_segment(item) != selected_segment:
            continue
        if selected_intensity != "All" and classify_intensity(item) != selected_intensity:
            continue
        if selected_barrier != "All" and item.get("primary_barrier_type") != selected_barrier:
            continue
        if selected_frustration != "All" and not any(frustration.get("category") == selected_frustration for frustration in item.get("frustrations", []) or []):
            continue
        if selected_repetition != "All" and item.get("repetition_type") != selected_repetition:
            continue
        filtered.append(item)
    return filtered


def render_top_metrics(aggregate: dict[str, Any]) -> None:
    summary = aggregate["summary"]
    synthesis = aggregate["synthesis"]
    q5 = aggregate["q5_segment_differences"]
    cards = [
        ("Reviews analyzed", summary["quantitative_records"], f"{summary['low_confidence_or_failed']} low-confidence excluded"),
        ("Avg severity", synthesis["average_severity"], "1 low - 5 high"),
        ("Unmet-need evidence", synthesis["unmet_need_signal_count"], "workarounds, displacement, or resignation signals"),
        ("Classified into matrix", f"{q5['classification_rate']}%", "unclassified records stay out of segment cells"),
    ]
    cols = st.columns(4)
    for col, (label, value, detail) in zip(cols, cards):
        col.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">{label}</div>
                <div class="metric-value">{value}</div>
                <div class="metric-detail">{detail}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_targeting_matrix_selector(aggregate: dict[str, Any]) -> None:
    st.subheader("Segment x Listening Intensity Targeting Matrix")
    st.markdown(
        '<div class="panel-note">Each cell is computed from high-confidence live extractions. Count shows review volume; severity shows average issue intensity. Pick a cell to drill every question panel into that population.</div>',
        unsafe_allow_html=True,
    )
    matrix = aggregate["q5_segment_differences"].get("targeting_matrix", [])
    by_cell = {(row["segment"], row["intensity"]): row for row in matrix}
    header_cols = st.columns([1.25, 1, 1, 1])
    header_cols[0].markdown("**Segment**")
    for index, intensity in enumerate(["high", "medium", "low"], start=1):
        header_cols[index].markdown(f"**{INTENSITY_LABELS[intensity]}**")

    for segment in ["power_user", "genre_enthusiast", "mood_based_listener", "casual_listener"]:
        row_cols = st.columns([1.25, 1, 1, 1])
        row_cols[0].markdown(f"**{SEGMENT_LABELS[segment]}**")
        for index, intensity in enumerate(["high", "medium", "low"], start=1):
            cell = by_cell.get((segment, intensity), {})
            label = f"{cell.get('records', 0)} records | sev {cell.get('average_severity', 0)}"
            help_text = (
                f"Dominant barrier: {format_label(cell.get('dominant_barrier'))}; "
                f"dominant frustration: {format_label(cell.get('dominant_frustration'))}; "
                f"addressable repetition: {cell.get('addressable_repetition_rate', 0)}%"
            )
            if row_cols[index].button(label, key=f"cell_{segment}_{intensity}", help=help_text, use_container_width=True):
                st.session_state["dashboard_segment"] = segment
                st.session_state["dashboard_intensity"] = intensity
                st.rerun()


def render_synthesis(aggregate: dict[str, Any]) -> None:
    synthesis = aggregate["synthesis"]
    dashboard = aggregate.get("dashboard", {})
    st.subheader("Strategic Synthesis")
    cols = st.columns(3)
    cols[0].metric("Dominant barrier", format_label(synthesis["dominant_barrier"]))
    cols[1].metric("Dominant frustration", format_label(synthesis["dominant_frustration"]))
    cols[2].metric("Dominant discovery mode", format_label(synthesis["dominant_discovery_mode"]))
    st.write(synthesis["model_note"])

    source_counts = pd.DataFrame(dashboard.get("source_counts", []))
    source_barriers = pd.DataFrame(dashboard.get("source_barrier_matrix", []))
    if not source_counts.empty:
        st.caption("Source coverage")
        st.dataframe(source_counts, use_container_width=True, hide_index=True)
    if not source_barriers.empty:
        st.caption("Barrier evidence by source")
        pivot = source_barriers.pivot_table(index="source", columns="barrier", values="severity_weight", aggfunc="sum", fill_value=0)
        st.dataframe(pivot, use_container_width=True)

    cross_source = pd.DataFrame(dashboard.get("cross_source_frustrations", []))
    if not cross_source.empty:
        st.caption("Frustrations appearing across more sources are stronger evidence than one-source findings.")
        st.dataframe(cross_source, use_container_width=True, hide_index=True)


def render_q1(q1: dict[str, Any]) -> None:
    st.divider()
    st.subheader("Q1 - Why do users struggle to discover new music?")
    ranked = pd.DataFrame(q1.get("ranked_barriers", []))
    if not ranked.empty:
        st.bar_chart(ranked.set_index("barrier")["percentage"])
        st.dataframe(ranked, use_container_width=True, hide_index=True)

    by_source_rows = []
    for source, rows in q1.get("by_source", {}).items():
        for row in rows:
            by_source_rows.append({"source": source, **row})
    if by_source_rows:
        st.caption("Source-level distribution helps separate true convergence from platform-format bias.")
        st.dataframe(pd.DataFrame(by_source_rows), use_container_width=True, hide_index=True)

    feature_rows = pd.DataFrame(q1.get("algorithmic_feature_heatmap", []))
    if not feature_rows.empty:
        st.caption("Named features inside algorithmic barrier complaints")
        st.dataframe(feature_rows, use_container_width=True, hide_index=True)
    render_quote_groups(q1.get("top_quotes", {}))


def render_q2(q2: dict[str, Any]) -> None:
    st.divider()
    st.subheader("Q2 - What are the most common frustrations with recommendations?")
    ranked = pd.DataFrame(q2.get("ongoing_ranked", []))
    if not ranked.empty:
        st.bar_chart(ranked.set_index("frustration")["severity_weight"])
        st.dataframe(ranked, use_container_width=True, hide_index=True)

    severity = pd.DataFrame.from_dict(q2.get("severity_distribution", {}), orient="index").reset_index(names="frustration")
    if not severity.empty:
        st.caption("Severity distribution reveals lower-frequency but high-risk frustrations.")
        st.dataframe(severity, use_container_width=True, hide_index=True)
    render_quote_groups(q2.get("top_quotes", {}))


def render_q3(q3: dict[str, Any]) -> None:
    st.divider()
    st.subheader("Q3 - What listening behaviors are users trying to achieve?")
    matrix = pd.DataFrame(q3.get("intent_matrix", []))
    if not matrix.empty:
        display = matrix.drop(columns=["representative_quote"], errors="ignore")
        st.dataframe(display, use_container_width=True, hide_index=True)
        pivot = matrix.pivot_table(index="activity_context", columns="discovery_mode", values="severity_sum", aggfunc="sum", fill_value=0)
        st.caption("Intent matrix: activity context x discovery mode, weighted by severity")
        st.dataframe(pivot, use_container_width=True)

    outcomes = pd.DataFrame(q3.get("desired_outcomes", []))
    if not outcomes.empty:
        st.caption("Desired outcomes extracted from users' own language")
        st.dataframe(outcomes, use_container_width=True, hide_index=True)


def render_q4(q4: dict[str, Any]) -> None:
    st.divider()
    st.subheader("Q4 - What causes users to repeatedly listen to the same content?")
    split = q4.get("intentional_vs_unintentional", {})
    col_a, col_b = st.columns(2)
    col_a.metric("Intentional repetition", split.get("intentional", 0))
    col_b.metric("Unintentional / opportunity-state repetition", split.get("unintentional", 0))
    ranked = pd.DataFrame(q4.get("ranked_repetition_types", []))
    if not ranked.empty:
        st.dataframe(ranked, use_container_width=True, hide_index=True)
    render_quote_groups(q4.get("top_quotes", {}))


def render_q5(q5: dict[str, Any]) -> None:
    st.divider()
    st.subheader("Q5 - Which user segments experience different discovery challenges?")
    col_a, col_b = st.columns(2)
    counts = pd.DataFrame([{"segment": key, "records": value} for key, value in q5.get("classified_counts", {}).items()])
    if not counts.empty:
        col_a.caption(f"Classification rate: {q5.get('classification_rate', 0)}%")
        col_a.dataframe(counts, use_container_width=True, hide_index=True)
    intensity = pd.DataFrame(q5.get("intensity_distribution", []))
    if not intensity.empty:
        col_b.caption("Listening intensity distribution")
        col_b.dataframe(intensity, use_container_width=True, hide_index=True)

    matrix_rows = pd.DataFrame(q5.get("targeting_matrix", []))
    if not matrix_rows.empty:
        st.caption("Targeting matrix detail: segment x intensity cells")
        st.dataframe(matrix_rows, use_container_width=True, hide_index=True)

    matrix = pd.DataFrame(q5.get("segment_frustration_matrix", []))
    if not matrix.empty:
        st.caption("Segment findings are text-proxy hypotheses. Validate them with behavioral data.")
        notable = matrix[matrix["segment_weight"] > 0].sort_values(["segment", "delta"], ascending=[True, False])
        st.dataframe(notable, use_container_width=True, hide_index=True)


def render_quote_bank(quotes: list[dict[str, Any]]) -> None:
    st.divider()
    st.subheader("Verbatim Evidence")
    if not quotes:
        st.caption("No quotes available for the current filter.")
        return
    for quote in quotes[:8]:
        tags = [
            SOURCE_LABELS.get(str(quote.get("source")), format_label(quote.get("source"))),
            SEGMENT_LABELS.get(str(quote.get("segment")), format_label(quote.get("segment"))),
            INTENSITY_LABELS.get(str(quote.get("intensity")), format_label(quote.get("intensity"))),
            f"severity {quote.get('severity', '-')}",
        ]
        st.markdown(f"**{' | '.join(tags)}**")
        st.write(f"\"{quote.get('quote', '')}\"")


def render_goldmine_records(records: list[dict[str, Any]]) -> None:
    st.divider()
    st.subheader("Goldmine Feedback")
    st.caption("Highest-priority records by issue intensity, engagement/upvotes, replies, and unmet-need signals.")
    if not records:
        st.caption("No goldmine records available for the current filters.")
        return
    display = pd.DataFrame(records)
    compact_cols = [
        "score",
        "source",
        "severity",
        "signal_weight",
        "engagement_score",
        "conversation_score",
        "barrier",
        "segment",
        "intensity",
        "quote",
    ]
    st.dataframe(display[[col for col in compact_cols if col in display.columns]], use_container_width=True, hide_index=True)


def render_q6(q6: dict[str, Any]) -> None:
    st.divider()
    st.subheader("Q6 - What unmet needs emerge consistently?")
    needs = pd.DataFrame(q6.get("recurring_need_phrases", []))
    if not needs.empty:
        st.dataframe(needs, use_container_width=True, hide_index=True)
    cross_path = pd.DataFrame(q6.get("cross_path_evidence", []))
    if not cross_path.empty:
        st.caption("Cross-path evidence: needs that appear through workarounds, competitive displacement, and resignation.")
        st.dataframe(cross_path, use_container_width=True, hide_index=True)

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown("**Workarounds**")
        st.dataframe(pd.DataFrame(q6.get("workarounds", [])), use_container_width=True, hide_index=True)
    with col_b:
        st.markdown("**Competitive displacement**")
        st.dataframe(pd.DataFrame(q6.get("competitive_displacements", [])), use_container_width=True, hide_index=True)
    with col_c:
        st.markdown("**Resignation signals**")
        st.dataframe(pd.DataFrame(q6.get("resignation_signals", [])), use_container_width=True, hide_index=True)


def render_quote_groups(groups: dict[str, list[dict[str, Any]]]) -> None:
    if not groups:
        return
    with st.expander("Representative quotes"):
        for label, quotes in groups.items():
            st.markdown(f"**{format_label(label)}**")
            for quote in quotes:
                text = quote.get("quote") or quote.get("outcome") or ""
                st.write(f"- \"{text}\" ({quote.get('source', 'unknown')}, severity {quote.get('severity', '-')})")


def render_downloads(result: dict[str, Any]) -> None:
    st.divider()
    st.subheader("Downloads")
    render_download_buttons(result)


def render_download_buttons(result: dict[str, Any]) -> None:
    report_path = Path(result["paths"]["report"])
    analysis_path = Path(result["paths"]["analysis"])
    extraction_path = Path(result["paths"]["extractions"])
    col_report, col_json, col_extract = st.columns(3)
    col_report.download_button("Report", data=report_path.read_text(encoding="utf-8"), file_name=report_path.name, mime="text/markdown")
    col_json.download_button("Analysis JSON", data=analysis_path.read_text(encoding="utf-8"), file_name=analysis_path.name, mime="application/json")
    col_extract.download_button("Extractions JSON", data=extraction_path.read_text(encoding="utf-8"), file_name=extraction_path.name, mime="application/json")


def format_label(value: Any) -> str:
    return str(value or "unclear").replace("_", " ").title()


def main() -> None:
    if render_doc_page(current_doc_route() or ""):
        return

    settings = get_settings()
    apply_home_style()
    apply_fresh_tool_request()
    load_default_run_into_state()
    render_app_header()
    render_default_analysis_prompt()
    render_home_links()
    prepare_page_state(st.session_state)
    page = st.radio(
        "Page",
        PAGE_OPTIONS,
        horizontal=True,
        label_visibility="collapsed",
        key="app_page",
    )

    if page == DASHBOARD_PAGE:
        analysis_result = st.session_state.get("analysis_result")
        if not analysis_result:
            st.info("Collect data and run analysis first. The dashboard will appear here after analysis completes.")
            return
        if analysis_result["errors"]:
            with st.expander("Analysis warnings"):
                for error in analysis_result["errors"]:
                    st.warning(error)
        render_analysis_dashboard(analysis_result)
        return

    default_to = date.today()
    default_from = default_to - timedelta(days=settings.default_lookback_days)
    loaded_ingestion = st.session_state.get("current_ingestion_result")
    if loaded_ingestion and st.session_state.get("analysis_result"):
        st.caption(
            "The executed analysis above is the default experience. Use the fresh-run link near the page title "
            "when you want to test collection and analysis from scratch."
        )

    with st.form("ingestion_form"):
        col_from, col_to, col_target = st.columns([1, 1, 1])
        from_date = col_from.date_input("From date", value=default_from)
        to_date = col_to.date_input("To date", value=default_to)
        target_record_limit = FRESH_RUN_TARGET_RECORD_LIMIT if st.session_state.get(FRESH_TOOL_KEY) else DEFAULT_TARGET_RECORD_LIMIT
        target_help = (
            "Fresh test runs are capped at 25 meaningful records per source so you can validate the full flow quickly. "
            "The default loaded dashboard still uses the saved 300-record-per-source analysis."
            if st.session_state.get(FRESH_TOOL_KEY)
            else (
                "The app will over-collect candidates internally, then keep the strongest meaningful feedback. "
                "A source is treated as healthy when it reaches at least 95% of this target."
            )
        )
        target_records = col_target.number_input(
            "Target meaningful records / source",
            min_value=MIN_TARGET_RECORD_LIMIT,
            max_value=target_record_limit,
            value=min(target_record_limit, max(MIN_TARGET_RECORD_LIMIT, int(settings.max_items_per_source))),
            step=5,
            help=target_help,
        )
        enabled_sources, searches_by_source = render_source_controls()
        submitted = st.form_submit_button("Collect data")

    if submitted:
        if from_date > to_date:
            st.error("From date must be earlier than or equal to To date.")
            return
        if not enabled_sources:
            st.error("Select at least one source.")
            return

        with st.spinner("Collecting meaningful feedback from selected sources..."):
            candidate_limit = overfetch_candidate_limit(
                int(target_records),
                multiplier=settings.candidate_overfetch_multiplier,
                maximum=settings.candidate_overfetch_max,
            )
            ingestion_result = run_ingestion(
                settings=settings,
                from_date=from_date,
                to_date=to_date,
                searches_by_source=searches_by_source,
                enabled_sources=enabled_sources,
                limit_per_source=int(target_records),
                candidate_limit_per_source=candidate_limit,
                min_words=DEFAULT_MIN_WORDS,
            )
        st.session_state["current_ingestion_result"] = ingestion_result
        st.session_state["current_session_dir"] = ingestion_result.session_dir
        st.session_state.pop("analysis_result", None)

    ingestion_result = st.session_state.get("current_ingestion_result")
    if ingestion_result:
        render_collection_summary(ingestion_result)
        if st.button("Run analysis", type="primary"):
            with st.spinner("Running six Gemini analysis passes and building the dashboard..."):
                try:
                    analysis_result = run_review_analysis(settings=settings, session_dir=ingestion_result.session_dir)
                except Exception as exc:
                    st.error(f"Analysis failed: {exc}")
                    with st.expander("Technical details"):
                        st.code(traceback.format_exc())
                    return
            st.session_state["analysis_result"] = analysis_result
            write_default_session(
                session_id=ingestion_result.session_id,
                session_dir=ingestion_result.session_dir,
                analysis_dir=Path("data/analysis") / ingestion_result.session_id,
            )
            request_page_navigation(st.session_state, DASHBOARD_PAGE)
            st.rerun()


if __name__ == "__main__":
    main()
