from __future__ import annotations

import json
from html import escape
from typing import Any

from src.analysis.aggregation import MIN_EXTRACTION_CONFIDENCE, classify_intensity, classify_segment
from src.analysis.dashboard_insights import default_dashboard_insights


SEGMENTS = [
    "comfort_listener",
    "playlist_heavy_user",
    "active_explorer",
    "mood_based_listener",
    "regional_language_listener",
    "artist_loyal_user",
    "casual_listener",
    "premium_power_user",
    "unclassified",
]
INTENSITIES = ["high", "medium", "low"]

SEGMENT_LABELS = {
    "comfort_listener": "Comfort listener",
    "playlist_heavy_user": "Control-first listener",
    "active_explorer": "Discovery-frustrated explorer",
    "mood_based_listener": "Mood-based listener",
    "regional_language_listener": "Regional-language listener",
    "artist_loyal_user": "Artist-loyal user",
    "casual_listener": "Casual listener",
    "premium_power_user": "Premium power user",
    "unclassified": "Unclassified",
}

INTENSITY_LABELS = {"high": "High use", "medium": "Medium use", "low": "Low use"}
INTENSITY_HELP = {"high": "4+ hrs/day language", "medium": "daily / 1-3 hrs/day language", "low": "occasional or no frequency signal"}

SOURCE_LABELS_SHORT = {
    "app_store": "App Store",
    "play_store": "Play Store",
    "reddit": "Reddit",
    "youtube": "YouTube",
    "spotify_community": "Forums",
}


def chart_legend(title: str, lines: list[str]) -> str:
    items = "".join(f"<li>{escape(line)}</li>" for line in lines)
    return f"""
    <details class="legend">
      <summary>What this chart means</summary>
      <div class="legend-body">
        <strong>{escape(title)}</strong>
        <ul>{items}</ul>
      </div>
    </details>
    """


def build_interactive_dashboard_html(extractions: list[dict[str, Any]], dashboard_insights: dict[str, str] | None = None) -> str:
    meaningful_count = len(extractions)
    records = [dashboard_record(item) for item in extractions if is_quantitative(item)]
    dashboard_count = len(records)
    excluded_count = max(0, meaningful_count - dashboard_count)
    insights = default_dashboard_insights()
    if isinstance(dashboard_insights, dict):
        insights.update({key: str(value) for key, value in dashboard_insights.items() if value})
    quality_summary = {
        "meaningfulRecords": meaningful_count,
        "dashboardRecords": dashboard_count,
        "excludedRecords": excluded_count,
        "confidenceThreshold": MIN_EXTRACTION_CONFIDENCE,
    }
    payload = json.dumps(records, ensure_ascii=False).replace("</", "<\\/")
    insight_payload = json.dumps(insights, ensure_ascii=False).replace("</", "<\\/")
    quality_payload = json.dumps(quality_summary, ensure_ascii=False).replace("</", "<\\/")
    return f"""
<style>
{dashboard_css()}
</style>
<div class="db">
  <div class="filter-strip" id="filterStrip"></div>
  <div class="filter-toast" id="filterToast"></div>
  <div class="quality-note" id="qualityNote"></div>
  <div class="section-title">Q1 - Why Users Struggle To Discover New Music</div>
  <div class="grid2">
    <section class="card"><div class="card-title">Why Discovery Fails <span class="qb q1">Q1</span></div><p class="hint">This shows the concrete ways discovery breaks down. A single review can mention more than one failure, so the bars count mentions.</p>{chart_legend("Why Discovery Fails", ["Left labels are the failure themes found in reviews.", "The bar length shows which failures are mentioned most often.", "The number on the right is mentions plus share of all failure mentions in the active view."])}<div id="failureChart"></div><div class="ins" id="failureInsight"></div></section>
    <section class="card"><div class="card-title">Primary Discovery Barrier <span class="qb q1">Q1</span></div><p class="hint">This shows the main reason each review says discovery is blocked: algorithm, trust, surface design, or effort.</p>{chart_legend("Primary Discovery Barrier", ["Each review contributes at most one primary barrier.", "The left side names the barrier category; the right side shows record count and share.", "Use this to understand the root cause, not the detailed symptom."])}<div id="barrierChart"></div><div class="ins" id="barrierInsight"></div></section>
  </div>
  <div class="section-title">Q2 - Most Common Recommendation Frustrations</div>
  <section class="card"><div class="card-title">Recommendation Frustrations <span class="qb q2">Q2</span></div><p class="hint">This translates complaints into plain frustration themes, like feeling trapped in the same taste loop or getting the wrong mood.</p>{chart_legend("Recommendation Frustrations", ["A review can have multiple frustrations, so bars are mention counts.", "The right side also shows average issue intensity from 1 to 5.", "Higher issue intensity means the user describes stronger pain, trust loss, or behavior change."])}<div id="frustrationChart"></div><div class="ins" id="frustrationInsight"></div></section>
  <div class="section-title">Q3 - Listening Behaviors Users Want To Achieve</div>
  <div class="grid2">
    <section class="card"><div class="card-title">What Users Are Trying To Achieve <span class="qb q3">Q3</span></div><p class="hint">This shows the outcome users wanted: comfort, taste expansion, passive freshness, deeper exploration, or escape from repetition.</p>{chart_legend("User Goals", ["Left labels are the listening goals inferred from the review.", "Bar length shows which goals appear most often.", "The right side shows records plus share of all goal mentions in the active view."])}<div id="goalChart"></div><div class="ins" id="goalInsight"></div></section>
    <section class="card"><div class="card-title">Listening Intent - Mode x Context <span class="qb q3">Q3</span></div><p class="hint">This shows whether users were actively exploring, leaning back, or discovering incidentally, and in what listening context.</p>{chart_legend("Listening Intent Matrix", ["Rows are listening mode: Active means intentional searching, Lean-back means let Spotify play, Incidental means discovery happens while doing something else.", "Columns are context: home, work, commute, exercise, or social listening.", "Each cell is the number of records for that mode and context; darker cells have more records."])}<div id="intentMatrix"></div><div class="ins" id="intentInsight"></div></section>
  </div>
  <div class="section-title">Q4 - Why Users Keep Repeating Music</div>
  <section class="card"><div class="card-title">Why Users Repeat Music <span class="qb q4">Q4</span></div><p class="hint">This separates healthy repetition, like comfort listening, from unhealthy repetition caused by loops, weak controls, or low trust.</p>{chart_legend("Repeat Drivers", ["Left labels are reasons users keep returning to the same content.", "Bar length shows which repeat drivers are most common.", "Algorithmic reinforcement means Spotify appears to keep narrowing recommendations based on past listening."])}<div id="repeatDriverChart"></div><div class="ins" id="repeatInsight"></div></section>
  <div class="section-title">Q5 - Which User Categories Face Different Challenges</div>
  <section class="card matrix-card">
    <div class="card-title">Segment x Listening Intensity Matrix <span class="qb q5">Q5 anchor</span></div>
    <p class="hint">This compares user categories with listening frequency. A power user is a behavior category; high use only means frequent listening.</p>
    {chart_legend("Segment x Listening Intensity Matrix", ["Rows are user categories inferred from review language.", "Columns are usage frequency: high, medium, or low listening intensity.", "Each cell shows record count; darker color means higher average issue intensity, not more records.", "Use the user category dropdown above to filter. The matrix itself is read-only."])}
    <div id="targetMatrix"></div>
    <div class="ins info" id="q5Insight"></div>
  </section>
  <div class="grid2">
    <section class="card"><div class="card-title">Which Segments Face Which Issues <span class="qb q5">Q5</span></div><p class="hint">This shows which behavior-based user categories appear in the active view and how severe their feedback is on average.</p>{chart_legend("User Category Profiles", ["Each row is a behavior-based user category, not a demographic segment.", "The bar on the right shows that category's share of records in the active view.", "Average issue intensity summarizes how strongly that category expresses discovery or recommendation pain."])}<div id="segmentPanel"></div><div class="ins" id="segmentInsight"></div></section>
    <section class="card"><div class="card-title">Listening Intensity Distribution <span class="qb signal">Usage signal</span></div><p class="hint">This shows how often users seem to listen based on language in the review. It is separate from user category.</p>{chart_legend("Listening Intensity", ["High use means the review suggests all-day or 4+ hours/day listening.", "Medium use means regular daily or routine listening.", "Low use means occasional use or no clear frequency signal.", "This does not mean premium power user; usage frequency and user category are separate."])}<div class="int-grid" id="intensityPanel"></div><div class="ins" id="intensityInsight"></div></section>
  </div>
  <div class="section-title">Q6 - Consistent Unmet Needs</div>
  <div class="grid2">
    <section class="card"><div class="card-title">Unmet Need Themes <span class="qb q6">Q6</span></div><p class="hint">This shows what users need but do not feel Spotify currently provides, such as trust repair, better variety, or freshness control.</p>{chart_legend("Unmet Need Themes", ["Left labels are unmet needs inferred from complaint patterns and workarounds.", "Bar length shows which needs appear most often.", "The right side shows record count plus share of all unmet-need mentions in the active view."])}<div id="needChart"></div><div class="ins" id="needInsight"></div></section>
    <section class="card"><div class="card-title">Product Opportunity Map <span class="qb q6">Q6</span></div><p class="hint">This translates repeated user pain into product opportunity areas, not final feature decisions.</p>{chart_legend("Product Opportunity Map", ["Left labels are possible product opportunity areas suggested by the feedback.", "Bar length shows which opportunities have the most supporting records.", "Use this as product discovery input, then validate with interviews or experiments."])}<div id="opportunityChart"></div><div class="ins" id="opportunityInsight"></div></section>
  </div>
  <section class="card"><div class="card-title">Verbatim Evidence - Active Filters</div><p class="hint">These quotes are the strongest examples from the currently filtered records, useful for PM storytelling and qualitative review.</p>{chart_legend("Verbatim Evidence", ["Each quote comes from a real feedback record in the active filter view.", "Tags show user category, usage intensity, source, and issue intensity.", "Quotes are sorted toward stronger evidence using severity and signal weight."])}<div id="quotes"></div><div class="ins" id="quoteInsight"></div></section>
</div>
<script>
const RECORDS = {payload};
const INSIGHTS = {insight_payload};
const QUALITY = {quality_payload};
{dashboard_js()}
</script>
"""


def is_quantitative(item: dict[str, Any]) -> bool:
    return item.get("quality_for_analysis", True) and float(item.get("extraction_confidence") or 0) >= MIN_EXTRACTION_CONFIDENCE


def dashboard_record(item: dict[str, Any]) -> dict[str, Any]:
    frustrations = item.get("frustrations") if isinstance(item.get("frustrations"), list) else []
    workarounds = item.get("workarounds") if isinstance(item.get("workarounds"), list) else []
    displacements = item.get("competitive_displacements") if isinstance(item.get("competitive_displacements"), list) else []
    signals = item.get("resignation_signals") if isinstance(item.get("resignation_signals"), list) else []
    quote = item.get("best_verbatim_quote") or item.get("barrier_evidence_quote") or item.get("repetition_evidence_quote") or ""
    return {
        "id": str(item.get("record_id", "")),
        "source": str(item.get("source", "unknown")),
        "sourceLabel": SOURCE_LABELS_SHORT.get(str(item.get("source")), str(item.get("source", "unknown"))),
        "segment": classify_segment(item),
        "segmentLabel": SEGMENT_LABELS.get(classify_segment(item), "Unclassified"),
        "intensity": classify_intensity(item),
        "intensityLabel": INTENSITY_LABELS.get(classify_intensity(item), "Low use"),
        "barrier": str(item.get("primary_barrier_type") or "unclear"),
        "pmBarrier": str(item.get("primary_discovery_barrier") or "unclear"),
        "noveltySafety": str(item.get("novelty_safety_state") or "unclear"),
        "failureModes": clean_list(item.get("discovery_failure_modes")),
        "frustrationThemes": clean_list(item.get("recommendation_frustration_themes")),
        "frustrations": [
            {
                "category": str(frustration.get("category", "unclear")),
                "severity": int(frustration.get("severity") or item.get("overall_severity") or 1),
            }
            for frustration in frustrations
            if isinstance(frustration, dict)
        ],
        "context": str(item.get("activity_context") or "unclear"),
        "mode": str(item.get("discovery_mode") or "unclear"),
        "goals": clean_list(item.get("user_goals")),
        "effortTolerance": str(item.get("effort_tolerance") or "unclear"),
        "repetition": str(item.get("repetition_type") or "unclear"),
        "repeatDrivers": clean_list(item.get("repetition_drivers")),
        "severity": int(item.get("overall_severity") or 1),
        "weight": float(item.get("signal_weight") or 1.0),
        "subscription": str(item.get("subscription_signal") or "unknown"),
        "opportunity": str(item.get("opportunity_area") or "unclear"),
        "unmetNeedTags": clean_list(item.get("unmet_need_tags")),
        "quote": escape(str(quote), quote=False),
        "needs": unmet_need_labels(workarounds, displacements, signals),
    }


def dashboard_number_contract(extractions: list[dict[str, Any]]) -> dict[str, Any]:
    records = [dashboard_record(item) for item in extractions if is_quantitative(item)]
    source_total = len(records)
    q5_total = sum(1 for record in records for segment in SEGMENTS for intensity in INTENSITIES if record["segment"] == segment and record["intensity"] == intensity)
    segment_total = sum(1 for record in records if record["segment"] in SEGMENTS)
    intensity_total = sum(1 for record in records if record["intensity"] in INTENSITIES)
    barrier_total = sum(1 for record in records if record["barrier"])
    controlled_freshness = sum(1 for record in records if dashboard_is_controlled_freshness(record))
    unwanted_repetition = sum(1 for record in records if dashboard_is_unwanted_repetition(record))
    trust_gap = sum(1 for record in records if record["pmBarrier"] == "low_recommendation_trust" or record["barrier"] == "trust")
    issues = []
    for label, value in {
        "q5_matrix_total": q5_total,
        "segment_total": segment_total,
        "intensity_total": intensity_total,
        "barrier_total": barrier_total,
    }.items():
        if value != source_total:
            issues.append(f"{label} {value} does not match dashboard record total {source_total}.")
    return {
        "dashboard_records": source_total,
        "q5_matrix_total": q5_total,
        "segment_total": segment_total,
        "intensity_total": intensity_total,
        "barrier_total": barrier_total,
        "controlled_freshness_records": controlled_freshness,
        "unwanted_repetition_records": unwanted_repetition,
        "trust_gap_records": trust_gap,
        "valid": not issues,
        "issues": issues,
    }


def dashboard_is_controlled_freshness(record: dict[str, Any]) -> bool:
    goals = set(record.get("goals") or [])
    needs = set(record.get("unmetNeedTags") or [])
    return (
        record.get("noveltySafety") in {"wants_safe_novelty", "too_familiar"}
        or bool(goals & {"fresh_music_without_effort", "passive_freshness", "safe_adjacent_genre_exploration", "similar_but_not_same", "escape_repetitive_playlists", "taste_expansion", "deep_exploration"})
        or bool(needs & {"freshness_control", "familiarity_balance", "better_variety", "mood_awareness", "language_culture_relevance", "low_effort_exploration", "deeper_discovery", "playlist_evolution", "trust_recovery"})
    )


def dashboard_is_unwanted_repetition(record: dict[str, Any]) -> bool:
    drivers = set(record.get("repeatDrivers") or [])
    return record.get("repetition") in {"algorithm_trapped", "trust_deficit", "friction_induced"} or bool(
        drivers & {"algorithmic_reinforcement", "low_discovery_confidence", "playlist_dependency", "weak_exploration_controls", "poor_first_song_risk", "time_pressure"}
    )


def clean_list(value: Any) -> list[str]:
    return [str(item) for item in value if item] if isinstance(value, list) else []


def unmet_need_labels(workarounds: list[dict[str, Any]], displacements: list[dict[str, Any]], signals: list[dict[str, Any]]) -> list[dict[str, str]]:
    labels: list[dict[str, str]] = []
    for workaround in workarounds:
        if isinstance(workaround, dict):
            labels.append({"label": need_label(workaround), "path": "workaround"})
    for displacement in displacements:
        if isinstance(displacement, dict):
            labels.append({"label": need_label(displacement), "path": "external discovery"})
    for signal in signals:
        if isinstance(signal, dict):
            labels.append({"label": need_label(signal), "path": "resignation"})
    return labels


def need_label(item: dict[str, Any]) -> str:
    text = " ".join(str(item.get(key, "")) for key in ("underlying_need", "need_served", "need_statement", "description", "feature_hypothesis")).lower()
    if "fresh" in text or "novel" in text or "adventurous" in text:
        return "Freshness control"
    if "familiar" in text or "balance" in text or "safe" in text:
        return "Familiarity balance"
    if "variety" in text or "repeat" in text or "same" in text:
        return "Better variety"
    if "mood" in text or "context" in text or "activity" in text:
        return "Mood awareness"
    if "language" in text or "culture" in text or "regional" in text or "local" in text:
        return "Language/culture relevance"
    if "explain" in text or "why" in text or "transparent" in text:
        return "Discovery transparency"
    if "manual" in text or "search" in text or "effort" in text:
        return "Low-effort exploration"
    if "genre" in text or "scene" in text or "niche" in text or "deep" in text:
        return "Deeper discovery"
    if "playlist" in text or "save" in text or "later" in text or "note" in text or "wishlist" in text:
        return "Playlist evolution"
    if "friend" in text or "peer" in text or "community" in text or "human" in text:
        return "Trusted human discovery"
    if "trust" in text or "repair" in text or "wrong" in text:
        return "Trust recovery"
    return "Controlled freshness"


def dashboard_css() -> str:
    return """
*{box-sizing:border-box}
html,body{margin:0;max-width:100%;overflow-x:hidden}
.db{font-family:Inter,Segoe UI,Arial,sans-serif;color:#18201b;background:#f7f8f6;padding:10px 6px 22px;font-size:12px;max-width:100%;overflow-x:hidden}
.filter-strip{margin:0 0 10px;padding:13px 14px;background:linear-gradient(180deg,#fff 0%,#fbfdfb 100%);border:1px solid #d9e5dc;border-radius:10px;box-shadow:0 4px 16px rgba(24,32,27,.035)}
.filter-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:11px}.filter-title{font-size:11px;color:#137a3a;font-weight:900;text-transform:uppercase;letter-spacing:.06em}.filter-subtitle{font-size:11px;color:#657067;line-height:1.35;margin-top:3px}.filter-reset{flex:0 0 auto}
.filter-grid{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(300px,.85fr);gap:10px;align-items:stretch}.filter-block{min-width:0;background:#fff;border:1px solid #e5ece5;border-radius:9px;padding:10px 11px}.filter-label{display:block;font-size:10px;color:#657067;margin:0 0 8px;font-weight:900;text-transform:uppercase;letter-spacing:.06em}.filter-controls{display:flex;align-items:center;gap:8px;flex-wrap:wrap;min-width:0}
.src-btn,.reset-btn,.weak-btn,.multi-summary{border:1px solid #cfd8d0;background:#fff;border-radius:999px;padding:7px 14px;font-weight:750;cursor:pointer;transition:.12s;color:#243029}
.src-btn:hover,.reset-btn:hover,.weak-btn:hover,.multi-summary:hover{border-color:#1db954;color:#137a3a}.src-btn.active,.weak-btn.active{background:#e9f7ee;border-color:#1db954;color:#137a3a}.reset-btn{padding:7px 12px;color:#555}.weak-btn{color:#555}
.multi-select{position:relative}.multi-select summary{list-style:none}.multi-select summary::-webkit-details-marker{display:none}.multi-menu{position:absolute;z-index:20;top:36px;left:0;min-width:255px;background:#fff;border:1px solid #cfd8d0;border-radius:8px;box-shadow:0 10px 28px rgba(24,32,27,.12);padding:8px}.multi-menu label{display:flex;gap:7px;align-items:center;padding:6px 7px;font-size:12px;color:#243029}.multi-menu input{accent-color:#1db954}
.quality-note{background:#fff;border:1px solid rgba(29,185,84,.25);border-left:4px solid #1db954;border-radius:8px;padding:13px 15px;margin:0 0 14px;font-size:13px;line-height:1.45;color:#24402e}
.filter-toast{position:sticky;top:4px;z-index:5;background:#fff7e6;border:1px solid #f2c879;border-left:4px solid #e49b22;border-radius:8px;padding:9px 11px;margin:0 0 10px;color:#5f3f06;box-shadow:0 6px 18px rgba(95,63,6,.12);font-size:11px}.filter-toast:empty{display:none}
.section-title{font-size:12px;font-weight:850;letter-spacing:.04em;text-transform:uppercase;color:#24402e;margin:14px 2px 8px;padding-top:2px}
.card{border:1px solid #dde4dc;border-radius:9px;padding:13px 14px;margin-bottom:10px;background:#fff;box-shadow:0 3px 12px rgba(24,32,27,.035);min-width:0;overflow:hidden}
.card-title{text-transform:uppercase;letter-spacing:.04em;font-weight:800;font-size:11px;margin-bottom:8px;color:#334038}
.qb{border-radius:12px;padding:1px 7px;margin-left:4px;text-transform:uppercase}.q1,.q5{background:#ebe8ff;color:#5b50c8}.q2{background:#fae8df;color:#a34725}.q3,.q6{background:#e0f4ed;color:#117d60}.q4,.signal{background:#f6ead2;color:#9a650f}
.hint{font-size:11px;margin:0 0 9px;color:#657067;line-height:1.35}.grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;align-items:stretch}
.legend{margin:0 0 10px;border:1px solid #e3e9e2;border-radius:7px;background:#fbfcfa;color:#334038}.legend summary{cursor:pointer;list-style:none;padding:8px 10px;font-size:11px;font-weight:800;color:#137a3a}.legend summary::-webkit-details-marker{display:none}.legend summary:after{content:'+';float:right;color:#657067;font-weight:900}.legend[open] summary:after{content:'-'}.legend-body{border-top:1px solid #e3e9e2;padding:9px 11px;font-size:11px;line-height:1.45}.legend-body ul{margin:6px 0 0 16px;padding:0}.legend-body li{margin:4px 0}
.matrix-grid{display:grid;grid-template-columns:minmax(132px,170px) repeat(3,minmax(0,1fr));gap:5px;align-items:stretch;min-width:0}.mh{text-align:center;font-weight:750;font-size:11px;min-width:0}.mh small{display:block;font-weight:500;color:#555}
.seg-label{display:flex;align-items:center;font-weight:750;font-size:12px;padding-left:10px}.seg-comfort_listener{color:#117d60}.seg-playlist_heavy_user{color:#d65330}.seg-active_explorer{color:#786ee6}.seg-mood_based_listener{color:#9a650f}.seg-regional_language_listener{color:#117d60}.seg-artist_loyal_user{color:#168fce}.seg-casual_listener{color:#777}.seg-premium_power_user{color:#d33f3f}.seg-unclassified{color:#555}
.mcell{border-radius:7px;min-height:58px;padding:8px 6px;color:#fff;text-align:center;border:2px solid #fff;min-width:0;overflow:hidden}.mcell.dim{opacity:.18!important}.mcell.sel{outline:3px solid #18201b}.mcount{font-size:18px;font-weight:850;line-height:1}.mlabel,.msev{font-size:10px;font-weight:700;overflow-wrap:anywhere}
.ins{background:#f4f6f2;border-radius:7px;padding:10px 12px;margin-top:10px;line-height:1.4;color:#334038;overflow-wrap:anywhere}.info{border-left:2px solid #168fce}
.hrow{display:grid;grid-template-columns:minmax(112px,165px) minmax(0,1fr) minmax(58px,92px);gap:8px;align-items:center;margin:7px 0;min-width:0}.hl{font-size:12px;min-width:0;overflow-wrap:anywhere}.bar{height:8px;background:#eef2ec;border-radius:9px;overflow:hidden;min-width:0}.fill{height:100%;border-radius:9px}.hv{text-align:right;font-size:11px;color:#444;min-width:0;overflow-wrap:anywhere}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px}
.seg-row{display:grid;grid-template-columns:34px 1fr 58px;gap:8px;align-items:center;margin:8px 0;border-radius:8px;padding:4px}
.seg-icon{width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:750}.seg-name{font-weight:800}.seg-meta{font-size:10px;color:#555}
.mini-bar{height:5px;background:#eef2ec;border-radius:8px;overflow:hidden}.int-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.int-card{border-radius:7px;text-align:center;padding:11px 6px;border:1px solid rgba(24,32,27,.06);min-width:0;overflow:hidden}.int-num{font-size:20px;font-weight:850}.int-label{font-weight:800}.int-sub{font-size:10px;overflow-wrap:anywhere}
.intent-table{width:100%;border-collapse:separate;border-spacing:4px;font-size:11px;table-layout:fixed}.intent-table th{font-size:10px;color:#555;overflow-wrap:anywhere}.intent-table td{min-width:0}.intent-cell{text-align:center;border-radius:4px;padding:8px 2px;color:#111;font-weight:850;min-width:0;min-height:30px;border:1px solid rgba(0,0,0,.06);overflow:hidden}
.quote{border-bottom:1px solid #dde4dc;padding:9px 0;line-height:1.45}.quote:last-child{border-bottom:0}.qtag{display:inline-block;border-radius:10px;padding:2px 7px;margin-right:5px;font-weight:800;font-size:10px;background:#e8f1ff;color:#2860a8}
@media(max-width:980px){.grid2{grid-template-columns:1fr}.filter-head{align-items:stretch}.filter-grid{grid-template-columns:1fr}.matrix-grid{grid-template-columns:minmax(105px,130px) repeat(3,minmax(0,1fr))}.hrow{grid-template-columns:minmax(96px,135px) minmax(0,1fr) minmax(48px,70px)}.src-btn{padding:7px 10px}}
"""


def dashboard_js() -> str:
    return r"""
const SEGS=['comfort_listener','playlist_heavy_user','active_explorer','mood_based_listener','regional_language_listener','artist_loyal_user','casual_listener','premium_power_user','unclassified'];
const INTS=['high','medium','low'];
const SRC_LABELS={app_store:'App Store',play_store:'Play Store',reddit:'Reddit',youtube:'YouTube',spotify_community:'Forums'};
const SEG_LABELS={comfort_listener:'Comfort listener',playlist_heavy_user:'Control-first listener',active_explorer:'Discovery-frustrated explorer',mood_based_listener:'Mood-based listener',regional_language_listener:'Regional-language listener',artist_loyal_user:'Artist-loyal user',casual_listener:'Casual listener',premium_power_user:'Premium power user',unclassified:'Unclassified'};
const INT_LABELS={high:'High use',medium:'Medium use',low:'Low use'};
const INT_HELP={high:'4+ hrs/day language',medium:'daily / 1-3 hrs/day language',low:'occasional or no frequency signal'};
const SEG_COLORS={comfort_listener:'#159f75',playlist_heavy_user:'#df5c36',active_explorer:'#8173dd',mood_based_listener:'#f0a128',regional_language_listener:'#117d60',artist_loyal_user:'#168fce',casual_listener:'#888780',premium_power_user:'#e24b4a',unclassified:'#6b7280'};
const BARRIER_COLORS={algorithmic:'#8173dd',surface:'#159f75',trust:'#d95734',cognitive:'#85837c',unclear:'#bbb'};
const BARRIER_LABELS={algorithmic:'Algorithm / taste model',surface:'Discovery surfaces hard to use',trust:'Low trust in recommendations',cognitive:'Too much effort to explore',unclear:'Needs manual review'};
const FRUSTRATION_LABELS={filter_bubble_lock_in:'Stuck in same taste loop',taste_model_staleness:'Taste profile feels outdated',wrong_context_genre_blending:'Wrong mood or genre mix',autoplay_regression:'Autoplay goes off-track',popularity_bias:'Too mainstream or obvious',context_unawareness:'Misses mood or activity',recommendation_opacity:'Why this? unclear',unclear:'Needs manual review'};
const REP_LABELS={comfort_ritual:'Comfort / ritual listening',algorithm_trapped:'Algorithm keeps looping',trust_deficit:'Familiar fallback from low trust',friction_induced:'Discovery feels too much effort',not_mentioned:'Not mentioned',unclear:'Unclear'};
const PM_BARRIER_LABELS={over_personalization:'Over-personalization',low_recommendation_trust:'Low trust in recommendations',repetition_fatigue:'Repetition fatigue',hidden_discovery_paths:'Hidden discovery paths',mood_mismatch:'Mood mismatch',regional_language_mismatch:'Regional/language mismatch',lack_of_control:'Lack of discovery control',unclear:'Needs manual review'};
const NOVELTY_LABELS={too_familiar:'Too familiar',too_unfamiliar:'Too unfamiliar',wants_safe_novelty:'Wants safe novelty',comfort_preferred:'Comfort preferred',unclear:'No clear novelty signal'};
const REPEAT_DRIVER_LABELS={habit_loop:'Habit loops',algorithmic_reinforcement:'Algorithmic reinforcement',low_discovery_confidence:'Low discovery confidence',playlist_dependency:'Playlist dependency',mood_safety:'Mood safety',weak_exploration_controls:'Weak exploration controls',poor_first_song_risk:'Poor first-song risk',time_pressure:'Time pressure'};
const FAILURE_LABELS={same_songs_repeating:'Same songs repeating',known_artists_dominating:'Known artists dominating',playlist_predictability:'Predictable playlists/mixes',discover_weekly_stale:'Discover Weekly stale',radio_too_narrow:'Radio too narrow',shuffle_non_random:'Shuffle feels non-random',mood_mismatch:'Mood mismatch',regional_mismatch:'Regional/language mismatch',too_mainstream:'Too mainstream',taste_profile_outdated:'Taste profile outdated'};
const GOAL_LABELS={comfort_listening:'Comfort listening',mood_based_listening:'Mood-based listening',activity_based_listening:'Activity-based listening',taste_expansion:'Taste expansion',social_discovery:'Social discovery',identity_building:'Identity building',deep_exploration:'Deep exploration',passive_freshness:'Passive freshness',fresh_music_without_effort:'Find fresh music without effort',match_current_mood:'Match current mood',safe_adjacent_genre_exploration:'Explore adjacent genres safely',similar_but_not_same:'Like this, but not same again',escape_repetitive_playlists:'Escape repetitive playlists',build_music_identity:'Build identity through music taste'};
const OPPORTUNITY_LABELS={freshness_control:'Freshness control',playlist_refresh:'Playlist refresh',mood_aware_discovery:'Mood-aware discovery',language_aware_discovery:'Language-aware discovery',deep_discovery:'Deep discovery',recommendation_repair:'Recommendation repair',discovery_explanation:'Discovery explanation',less_repeat_mode:'Less-repeat mode'};
const NEED_LABELS={trust_recovery:'Trust recovery',better_variety:'Better variety',freshness_control:'Freshness control',deeper_discovery:'Deeper discovery',familiarity_balance:'Familiarity balance',discovery_transparency:'Discovery transparency',low_effort_exploration:'Low-effort exploration',mood_awareness:'Mood awareness',playlist_evolution:'Playlist evolution',language_culture_relevance:'Language / culture relevance'};
const CATEGORY_FILTERS=SEGS.filter(s=>s!=='unclassified');
const active={sources:new Set([...new Set(RECORDS.map(r=>r.source))]),segments:new Set(),hideWeak:false};
function fmt(x){return (x||'unclear').replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase())}
function barrierLabel(x){return BARRIER_LABELS[x]||fmt(x)}
function frustrationLabel(x){return FRUSTRATION_LABELS[x]||fmt(x)}
function sourceFiltered(){return RECORDS.filter(r=>active.sources.has(r.source))}
function filtered(){return sourceFiltered().filter(r=>(!active.hideWeak||r.segment!=='unclassified')&&(!active.segments.size||active.segments.has(r.segment)))}
function avg(arr,fn){const vals=arr.map(fn).filter(v=>Number.isFinite(v));return vals.length?vals.reduce((a,b)=>a+b,0)/vals.length:0}
function countPct(n,d){return d?Math.round(n/d*100):0}
function issueLabel(x){return x>=4?'severe':x>=3?'clear friction':x>=2?'mild friction':'low signal'}
function renderQuality(){document.getElementById('qualityNote').innerHTML=`Using <strong>${QUALITY.dashboardRecords}</strong> high-confidence records from <strong>${QUALITY.meaningfulRecords}</strong> meaningful feedback items. <strong>${QUALITY.excludedRecords}</strong> low-confidence records are kept out so the charts stay reliable.`}
function categorySummary(){if(!active.segments.size)return active.hideWeak?'Classified user categories':'All user categories';const labels=[...active.segments].map(s=>SEG_LABELS[s]);return labels.length>2?`${labels.length} user categories selected`:labels.join(', ')}
function renderFilters(){const srcs=[...new Set(RECORDS.map(r=>r.source))];const sourceButtons=srcs.map(s=>`<button class="src-btn ${active.sources.has(s)?'active':''}" onclick="toggleSource('${s}')">${SRC_LABELS[s]||fmt(s)}</button>`).join('');const categoryChecks=CATEGORY_FILTERS.map(s=>`<label><input type="checkbox" ${active.segments.has(s)?'checked':''} onchange="toggleSegment('${s}')">${SEG_LABELS[s]}</label>`).join('');document.getElementById('filterStrip').innerHTML=`<div class="filter-head"><div><div class="filter-title">Dashboard filters</div><div class="filter-subtitle">Filter by feedback source and listener category. Every chart below recalculates from the selected evidence.</div></div><button class="reset-btn filter-reset" onclick="resetAll()">Reset</button></div><div class="filter-grid"><div class="filter-block"><span class="filter-label">Sources</span><div class="filter-controls">${sourceButtons}</div></div><div class="filter-block"><span class="filter-label">User categories</span><div class="filter-controls"><details class="multi-select"><summary class="multi-summary">${categorySummary()}</summary><div class="multi-menu">${categoryChecks}<button class="reset-btn" type="button" onclick="clearSegments()">All categories</button></div></details><button class="weak-btn ${active.hideWeak?'active':''}" onclick="toggleWeakSignal()">Hide Unclassified or weak signal records</button></div></div></div>`}
function toggleSource(s){if(active.sources.has(s)&&active.sources.size>1)active.sources.delete(s);else active.sources.add(s);renderAll()}
function toggleSegment(s){if(active.segments.has(s))active.segments.delete(s);else active.segments.add(s);renderAll()}
function clearSegments(){active.segments.clear();renderAll()}
function toggleWeakSignal(){active.hideWeak=!active.hideWeak;renderAll()}
function resetAll(){active.sources=new Set([...new Set(RECORDS.map(r=>r.source))]);active.segments.clear();active.hideWeak=false;renderAll()}
function renderActiveNote(){const parts=[];if(active.sources.size!==new Set(RECORDS.map(r=>r.source)).size)parts.push('sources: '+[...active.sources].map(s=>SRC_LABELS[s]||fmt(s)).join(', '));if(active.segments.size)parts.push('user categories: '+[...active.segments].map(s=>SEG_LABELS[s]).join(', '));if(active.hideWeak)parts.push('classified signal only');const isFiltered=parts.length>0;document.getElementById('filterToast').innerHTML=isFiltered?`<strong>Filter applied.</strong> ${parts.join(' - ')}. Use <strong>Reset</strong> to return to the full dashboard.`:''}
function isControlledFreshness(r){const goals=new Set(r.goals||[]), needs=new Set(r.unmetNeedTags||[]);return ['wants_safe_novelty','too_familiar'].includes(r.noveltySafety)||['fresh_music_without_effort','passive_freshness','safe_adjacent_genre_exploration','similar_but_not_same','escape_repetitive_playlists','taste_expansion','deep_exploration'].some(x=>goals.has(x))||['freshness_control','familiarity_balance','better_variety','mood_awareness','language_culture_relevance','low_effort_exploration','deeper_discovery','playlist_evolution','trust_recovery'].some(x=>needs.has(x))}
function isUnwantedRepeat(r){const drivers=new Set(r.repeatDrivers||[]);return ['algorithm_trapped','trust_deficit','friction_induced'].includes(r.repetition)||['algorithmic_reinforcement','low_discovery_confidence','playlist_dependency','weak_exploration_controls','poor_first_song_risk','time_pressure'].some(x=>drivers.has(x))}
function selectedRows(){return active.segments.size?[...active.segments]:(active.hideWeak?CATEGORY_FILTERS:SEGS)}
function renderMatrix(){const d=sourceFiltered().filter(r=>!active.hideWeak||r.segment!=='unclassified'), rows=selectedRows();let max=0,total=0;const cells={};rows.forEach(s=>INTS.forEach(i=>{const arr=d.filter(r=>r.segment===s&&r.intensity===i);const sev=avg(arr,r=>r.severity);cells[s+'_'+i]={arr,sev};max=Math.max(max,sev);total+=arr.length}));let html='<div class="matrix-grid"><div></div>'+INTS.map(i=>`<div class="mh">${INT_LABELS[i]}<small>${INT_HELP[i]}</small></div>`).join('');rows.forEach(s=>{html+=`<div class="seg-label seg-${s}">${SEG_LABELS[s]}</div>`;INTS.forEach(i=>{const c=cells[s+'_'+i], norm=max?c.sev/max:0, col=SEG_COLORS[s], is=active.segments.has(s);html+=`<div class="mcell ${is?'sel':''}" style="background:${col};opacity:${0.25+0.75*norm}"><div class="mcount">${c.arr.length}</div><div class="mlabel">${countPct(c.arr.length,total||d.length)}% of shown matrix</div><div class="msev">issue ${c.sev.toFixed(1)}/5</div></div>`})});document.getElementById('targetMatrix').innerHTML=html+'</div>'}
function renderSegments(){const d=filtered(), total=d.length||1, rows=selectedRows().map(s=>{const arr=d.filter(r=>r.segment===s), p=countPct(arr.length,total), col=SEG_COLORS[s];return{segment:s,arr,p,col}});document.getElementById('segmentPanel').innerHTML=rows.map(row=>`<div class="seg-row"><div class="seg-icon" style="background:${row.col}22;color:${row.col}">${row.segment[0].toUpperCase()}</div><div><div class="seg-name" style="color:${row.col}">${SEG_LABELS[row.segment]}</div><div class="seg-meta">${row.arr.length} records - avg issue ${avg(row.arr,r=>r.severity).toFixed(1)}/5</div></div><div><div class="mini-bar"><div class="fill" style="background:${row.col};width:${row.p}%"></div></div><div class="hv">${row.p}%</div></div></div>`).join('');const top=rows.filter(r=>r.arr.length).sort((a,b)=>b.arr.length-a.arr.length)[0];document.getElementById('segmentInsight').textContent=top?`${SEG_LABELS[top.segment]} is the largest user category in this view with ${top.arr.length} records.`:'No user-category signal is available for the active filters.'}
function renderIntensity(){const d=filtered(), rows=INTS.map(i=>{const arr=d.filter(r=>r.intensity===i), col=i==='high'?'#e24b4a':i==='medium'?'#ee9c21':'#159f75', bg=i==='high'?'#fde8e8':i==='medium'?'#f7ead2':'#e0f4ed';return{i,arr,col,bg}});document.getElementById('intensityPanel').innerHTML=rows.map(row=>`<div class="int-card" style="background:${row.bg};color:${row.col}"><div class="int-num">${row.arr.length}</div><div class="int-label">${INT_LABELS[row.i]}</div><div class="int-sub">${INT_HELP[row.i]}<br>avg issue ${avg(row.arr,r=>r.severity).toFixed(1)}/5</div></div>`).join('');const top=rows.sort((a,b)=>b.arr.length-a.arr.length)[0];document.getElementById('intensityInsight').textContent=top&&top.arr.length?`${INT_LABELS[top.i]} is the largest usage-frequency group in this view with ${top.arr.length} records; usage frequency is separate from user category.`:'No listening-intensity signal is available for the active filters.'}
function compactRows(rows,limit=7){if(rows.length<=limit||active.hideWeak)return rows.slice(0,limit);const head=rows.slice(0,limit-1),rest=rows.slice(limit-1),value=rest.reduce((a,r)=>a+r.value,0);return [...head,{key:'other',label:'Other signal',value,display:`${value} grouped`,color:'#9aa39b'}]}
function hRows(id,rows,colors){rows=compactRows(rows);if(!rows.length){document.getElementById(id).innerHTML='<div class="hint">No classified signal for the active filters.</div>';return []}const max=Math.max(...rows.map(r=>r.value),1);document.getElementById(id).innerHTML=rows.map(r=>`<div class="hrow"><div class="hl"><span class="dot" style="background:${colors[r.key]||r.color||'#999'}"></span>${r.label}</div><div class="bar"><div class="fill" style="width:${Math.round(r.value/max*100)}%;background:${colors[r.key]||r.color||'#999'}"></div></div><div class="hv">${r.display}</div></div>`).join('');return rows}
function insightFromRows(rows,prefix,unit='records'){const visible=rows.filter(r=>r.key!=='other');if(!visible.length)return 'No classified signal is available for the active filters.';const total=visible.reduce((a,r)=>a+r.value,0)||1, top=visible[0], second=visible[1], topShare=Math.round(top.value/total*100);if(topShare>=45)return `${prefix} ${top.label.toLowerCase()} dominates this view at ${top.value} ${unit} (${topShare}%).`;if(second)return `${prefix} ${top.label.toLowerCase()} and ${second.label.toLowerCase()} lead this view, but signal is spread across multiple themes.`;return `${prefix} ${top.label.toLowerCase()} lead this view, based on the same ${unit} shown in the chart.`}
function renderBarriers(){const d=filtered(), map=countBy(d,r=>['algorithmic','surface','trust','cognitive'].includes(r.barrier)?r.barrier:'');delete map[''];const denom=Object.values(map).reduce((a,b)=>a+b,0)||1;const rows=['algorithmic','surface','trust','cognitive'].filter(k=>map[k]).map(k=>({key:k,label:barrierLabel(k),value:map[k],display:`${map[k]} (${countPct(map[k],denom)}%)`}));const shown=hRows('barrierChart',rows,BARRIER_COLORS);document.getElementById('barrierInsight').textContent=insightFromRows(shown,'Primary discovery barriers are')}
function renderFrustrations(){const map={};filtered().forEach(r=>r.frustrations.forEach(f=>{if(!f.category||f.category==='unclear')return;map[f.category]??={n:0,s:0};map[f.category].n++;map[f.category].s+=f.severity||r.severity}));const denom=Object.values(map).reduce((a,v)=>a+v.n,0)||1;const rows=Object.entries(map).map(([k,v])=>({key:k,label:frustrationLabel(k),value:v.n,display:`${v.n} mentions (${countPct(v.n,denom)}%), issue ${(v.s/v.n).toFixed(1)}/5`,color:(v.s/v.n)>=4?'#e24b4a':(v.s/v.n)>=3?'#ee9c21':'#159f75'})).sort((a,b)=>b.value-a.value);const shown=hRows('frustrationChart',rows,{});document.getElementById('frustrationInsight').textContent=insightFromRows(shown,'Recommendation frustrations are','mentions')}
function renderRepeatDrivers(){const map={};filtered().forEach(r=>(r.repeatDrivers||[]).forEach(x=>{if(x&&x!=='unclear')map[x]=(map[x]||0)+1}));const denom=Object.values(map).reduce((a,b)=>a+b,0)||1;const rows=Object.entries(map).map(([k,v],i)=>({key:k,label:REPEAT_DRIVER_LABELS[k]||fmt(k),value:v,display:`${v} records (${countPct(v,denom)}%)`,color:['#159f75','#8173dd','#df5c36','#e24b4a','#ee9c21','#85837c'][i%6]})).sort((a,b)=>b.value-a.value);const shown=hRows('repeatDriverChart',rows,{});document.getElementById('repeatInsight').textContent=insightFromRows(shown,'Repeat listening is mainly driven by')}
function renderFailures(){const map={};filtered().forEach(r=>unique([...(r.failureModes||[]),...(r.frustrationThemes||[])]).forEach(x=>{if(x&&x!=='unclear')map[x]=(map[x]||0)+1}));const denom=Object.values(map).reduce((a,b)=>a+b,0)||1;const rows=Object.entries(map).map(([k,v],i)=>({key:k,label:FAILURE_LABELS[k]||fmt(k),value:v,display:`${v} mentions (${countPct(v,denom)}%)`,color:['#8173dd','#df5c36','#159f75','#ee9c21','#85837c','#168fce'][i%6]})).sort((a,b)=>b.value-a.value);const shown=hRows('failureChart',rows,{});document.getElementById('failureInsight').textContent=insightFromRows(shown,'Discovery fails most visibly through','mentions')}
function renderGoals(){const map={};filtered().forEach(r=>(r.goals||[]).forEach(x=>{if(x&&x!=='unclear')map[x]=(map[x]||0)+1}));const denom=Object.values(map).reduce((a,b)=>a+b,0)||1;const rows=Object.entries(map).map(([k,v],i)=>({key:k,label:GOAL_LABELS[k]||fmt(k),value:v,display:`${v} records (${countPct(v,denom)}%)`,color:['#159f75','#8173dd','#df5c36','#ee9c21','#168fce','#85837c'][i%6]})).sort((a,b)=>b.value-a.value);const shown=hRows('goalChart',rows,{});document.getElementById('goalInsight').textContent=insightFromRows(shown,'Users are mainly trying to achieve')}
function intentContext(r){const c=r.context;if(c.includes('commut'))return'Commute';if(c.includes('work')||c.includes('stud')||c.includes('creative'))return'Work';if(c.includes('exercise'))return'Exercise';if(c.includes('social'))return'Social';return'Home'}
function intentMode(r){return r.mode==='lean_back'?'Lean-back':r.mode==='active'?'Active':r.mode==='incidental'?'Incidental':'Unclear'}
function renderIntent(){const d=filtered(), modes=['Active','Lean-back','Incidental','Unclear'], ctxs=['Commute','Work','Exercise','Social','Home'];let m={};modes.forEach(a=>ctxs.forEach(c=>m[a+'__'+c]=0));d.forEach(r=>m[intentMode(r)+'__'+intentContext(r)]++);const max=Math.max(...Object.values(m),1);let html='<table class="intent-table"><tr><th></th>'+ctxs.map(c=>`<th>${c}</th>`).join('')+'</tr>';modes.forEach(mode=>{html+=`<tr><th>${mode}</th>`;ctxs.forEach(c=>{const v=m[mode+'__'+c], alpha=0.12+0.78*v/max, textColor=v?'#111':'#6f6f6f';html+=`<td><div class="intent-cell" style="background:rgba(32,167,122,${alpha});color:${textColor}">${v}</div></td>`});html+='</tr>'});document.getElementById('intentMatrix').innerHTML=html+'</table>';const top=Object.entries(m).sort((a,b)=>b[1]-a[1])[0];document.getElementById('intentInsight').textContent=top&&top[1]?`The most common intent context is ${top[0].replace('__',' in ').toLowerCase()}, with ${top[1]} records in the active view.`:'No listening-intent signal is available for the active filters.'}
function renderRep(){const d=filtered(), total=d.length||1, reps=['comfort_ritual','algorithm_trapped','trust_deficit','friction_induced','not_mentioned','unclear'], colors={comfort_ritual:'#159f75',algorithm_trapped:'#e24b4a',trust_deficit:'#ee9c21',friction_induced:'#85837c',not_mentioned:'#bbb',unclear:'#aaa'};const rows=reps.map(r=>({key:r,label:REP_LABELS[r]||fmt(r),value:d.filter(x=>x.repetition===r).length,display:`${d.filter(x=>x.repetition===r).length} (${countPct(d.filter(x=>x.repetition===r).length,total)}%)`})).filter(r=>r.value>0);hRows('repetitionChart',rows,colors);document.getElementById('repetitionInsight').textContent=INSIGHTS.repetition_patterns}
function renderNeeds(){const map={};filtered().forEach(r=>(r.unmetNeedTags||[]).forEach(x=>{if(x&&x!=='unclear')map[x]=(map[x]||0)+1}));const denom=Object.values(map).reduce((a,b)=>a+b,0)||1;const rows=Object.entries(map).map(([k,v],i)=>({key:k,label:NEED_LABELS[k]||fmt(k),value:v,display:`${v} records (${countPct(v,denom)}%)`,color:['#8173dd','#df5c36','#e24b4a','#159f75','#85837c'][i%5]})).sort((a,b)=>b.value-a.value);const shown=hRows('needChart',rows,{});document.getElementById('needInsight').textContent=insightFromRows(shown,'Unmet needs are')}
function renderOpportunities(){const map={};filtered().forEach(r=>{if(r.opportunity&&r.opportunity!=='unclear')map[r.opportunity]=(map[r.opportunity]||0)+1});const denom=Object.values(map).reduce((a,b)=>a+b,0)||1;const rows=Object.entries(map).map(([k,v],i)=>({key:k,label:OPPORTUNITY_LABELS[k]||fmt(k),value:v,display:`${v} records (${countPct(v,denom)}%)`,color:['#159f75','#8173dd','#df5c36','#ee9c21','#168fce','#85837c'][i%6]})).sort((a,b)=>b.value-a.value);const shown=hRows('opportunityChart',rows,{});document.getElementById('opportunityInsight').textContent=insightFromRows(shown,'Product opportunity areas are')}
function renderQuotes(){const d=filtered().sort((a,b)=>(b.severity*b.weight)-(a.severity*a.weight));document.getElementById('quotes').innerHTML=d.slice(0,5).map(r=>`<div class="quote"><span class="qtag">${r.segmentLabel}</span><span class="qtag">${r.intensityLabel}</span><span class="qtag">${r.sourceLabel}</span><span class="qtag">issue ${r.severity}/5</span>"${r.quote||'No quote available'}"</div>`).join('')||'<div class="hint">No quotes for the active selection.</div>';document.getElementById('quoteInsight').textContent=d.length?`Showing the strongest qualitative evidence from ${d.length} records in the active filter view.`:'No quote evidence is available for the active filters.'}
function countBy(arr,fn){const m={};arr.forEach(x=>{const k=fn(x);m[k]=(m[k]||0)+1});return m}
function topEntry(obj){const rows=Object.entries(obj).sort((a,b)=>b[1]-a[1]);return rows[0]}
function unique(arr){return [...new Set(arr.filter(Boolean))]}
function renderAll(){renderFilters();renderActiveNote();renderQuality();renderFailures();renderBarriers();renderFrustrations();renderGoals();renderIntent();renderRepeatDrivers();renderMatrix();document.getElementById('q5Insight').textContent=active.segments.size?`Matrix is narrowed to ${[...active.segments].map(s=>SEG_LABELS[s]).join(', ')} so usage intensity can be compared within selected user categories.`:'Matrix compares user categories by usage intensity. It is read-only; use the multi-select above to filter by one or more user categories.';renderSegments();renderIntensity();renderNeeds();renderOpportunities();renderQuotes()}
renderAll();
"""
