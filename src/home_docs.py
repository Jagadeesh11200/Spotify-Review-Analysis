from __future__ import annotations

from dataclasses import dataclass


USER_GUIDE_ROUTE = "user-guide"
ARCHITECTURE_ROUTE = "architecture"


@dataclass(frozen=True)
class HomeDoc:
    route: str
    title: str
    link_label: str
    summary: str
    markdown: str


USER_GUIDE_MARKDOWN = """
### User Guide

Start with the dashboard that is already loaded. The default view uses the saved 1,500-record analysis, so a demo user can understand the product story without spending API time or waiting for a fresh scrape.

#### Recommended Flow

1. Open the `Dashboard` page first.
2. Read Q1 through Q6 from top to bottom. The dashboard is organized around the six product questions.
3. Use the dashboard filter panel to choose sources.
4. Use the user-category dropdown to choose one or more listener groups.
5. Click `Hide Unclassified or weak signal records` when you want to hide unclassified feedback and focus on cleaner behavioral signal.
6. Open `What this chart means` inside any card when a chart label or count is unfamiliar.
7. Use `Reset` to return to the complete default evidence set.

#### When To Run It Yourself

Only open a blank tool when you want to test the pipeline end to end. Fresh demo runs are capped so they finish faster and avoid unnecessary API usage.

To run your own sample:

1. Click `Open a blank tool and run Collect + Analyze`.
2. Select a date range.
3. Keep the target small for demos.
4. Review sources and search phrases.
5. Click `Collect data`.
6. Check `Meaningful`, not just collected volume. Meaningful records passed relevance, English, word-count, and specificity checks.
7. Click `Run analysis` after collection completes.

#### How To Read The Dashboard

Use the dashboard like a product discovery room:

- Q1 explains where discovery breaks.
- Q2 explains what recommendation frustrations repeat.
- Q3 explains what users are trying to achieve.
- Q4 explains why users repeat music.
- Q5 explains which listener categories experience different challenges.
- Q6 explains unmet needs and product opportunity areas.
- Verbatim evidence gives the real user language behind the charts.
"""


ARCHITECTURE_MARKDOWN = """
### System Intelligence And Method

This system is designed as a feedback intelligence engine for Spotify discovery problems. The method is simple: collect public feedback, protect the dataset from noise, extract structured product meaning with Gemini, and make every dashboard number traceable to real feedback.

#### Intelligence Layer 1: Source Coverage

The system reads public English feedback from App Store, Play Store, Reddit, YouTube, and Spotify Community. Each source has a different bias: stores are short and emotional, Reddit and forums are richer in reasoning, and YouTube adds comment-level discovery reactions.

#### Intelligence Layer 2: Signal Protection

Before Gemini analysis, records pass quality gates for language, length, relevance, and behavioral specificity. This prevents one-line complaints like "bad app" from being treated the same as a detailed explanation of why discovery failed.

#### Intelligence Layer 3: Six Product Questions

Gemini 2.5 Pro runs six focused passes: discovery barriers, recommendation frustrations, listening intent, repetition drivers, user categories, and unmet needs. This keeps each classification aligned to a product question instead of generic sentiment.

#### Intelligence Layer 4: Validation And Aggregation

The aggregation layer keeps only high-confidence extractions in quantitative charts. Counts, chart rows, filters, and evidence quotes are recomputed from the active record set, so source filters and user-category filters stay consistent.

#### Intelligence Layer 5: Explainable Dashboard

The dashboard is intentionally not a metadata table. It is a guided evidence surface: each chart answers one product question, each legend explains how to read it, and each insight sentence is generated from the chart rows currently in view.
"""


DOC_PAGES = {
    USER_GUIDE_ROUTE: HomeDoc(
        route=USER_GUIDE_ROUTE,
        title="User Guide",
        link_label="How to operate this tool",
        summary="Plain-English guide for collection, analysis, filters, warnings, and dashboard reading.",
        markdown=USER_GUIDE_MARKDOWN,
    ),
    ARCHITECTURE_ROUTE: HomeDoc(
        route=ARCHITECTURE_ROUTE,
        title="Backend Architecture",
        link_label="Backend architecture one-pager",
        summary="One-page product and technical synopsis of ingestion, filtering, Gemini analysis, aggregation, and dashboard validation.",
        markdown=ARCHITECTURE_MARKDOWN,
    ),
}


def get_doc_page(route: str | None) -> HomeDoc | None:
    if not route:
        return None
    return DOC_PAGES.get(str(route).strip().lower())


def flowchart_html() -> str:
    return """
    <div class="doc-pill-row">
        <span class="doc-pill">Start with dashboard</span>
        <span class="doc-pill">Filter evidence</span>
        <span class="doc-pill">Run fresh sample only when needed</span>
    </div>
    <div class="doc-flow">
        <div class="flow-card"><em>Step 1</em><b>Open dashboard</b><span>Begin with the default analyzed run so the product story is visible immediately.</span></div>
        <div class="flow-arrow">-></div>
        <div class="flow-card"><em>Step 2</em><b>Filter evidence</b><span>Use source buttons, user-category multi-select, and weak-signal hiding.</span></div>
        <div class="flow-arrow">-></div>
        <div class="flow-card"><em>Step 3</em><b>Read Q1-Q6</b><span>Move through discovery failures, frustrations, intent, repetition, segments, and unmet needs.</span></div>
        <div class="flow-arrow">-></div>
        <div class="flow-card"><em>Optional</em><b>Run fresh sample</b><span>Use the blank tool only when you want to test collection and analysis yourself.</span></div>
        <div class="flow-arrow">-></div>
        <div class="flow-card"><em>Output</em><b>Use evidence</b><span>Turn chart patterns and verbatim quotes into product hypotheses.</span></div>
    </div>
    """


def architecture_flow_html() -> str:
    return """
    <div class="doc-pill-row">
        <span class="doc-pill">Live public data</span>
        <span class="doc-pill">Quality-gated records</span>
        <span class="doc-pill">Six Gemini passes</span>
        <span class="doc-pill">Traceable dashboard</span>
    </div>
    <div class="doc-architecture">
        <div><em>Listen</em><b>Source adapters</b><span>Collect public feedback from stores, discussions, comments, and community threads.</span></div>
        <div><em>Normalize</em><b>Shared feedback schema</b><span>Convert every source into consistent JSON with text, date, source, engagement, and metadata.</span></div>
        <div><em>Protect</em><b>Quality gates</b><span>Keep English, relevant, specific, behavior-rich records and remove low-signal noise.</span></div>
        <div><em>Reason</em><b>Gemini product passes</b><span>Classify each record against six product questions instead of generic sentiment.</span></div>
        <div><em>Verify</em><b>Aggregation logic</b><span>Use only high-confidence extractions for chart counts, filters, and insight summaries.</span></div>
        <div><em>Explain</em><b>Dashboard evidence</b><span>Show chart patterns, legends, filters, and verbatim quotes from the same active dataset.</span></div>
    </div>
    """
