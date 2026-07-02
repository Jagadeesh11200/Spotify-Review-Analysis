# Phase 1 Ingestion Contract

This phase collects live English-language feedback from App Store, Play Store, Reddit, YouTube, and Spotify Community, applies a quality gate, and stores normalized JSON records for each source in a per-session folder.

The default collection plan is at most 100 candidate feedback records per source before quality filtering, with a target of up to 50 usable feedback records per source after filtering. Across seven sources, that gives a default maximum of 700 candidate records and a target of up to 350 meaningful records when enough data is available in the selected date range.

The candidate records UI value is a true maximum per source. If it is set below 50, the usable target is capped to that lower value as well.

Reddit is collected through the Apify `trudax/reddit-scraper-lite` actor. Spotify Community is collected directly through public Khoros Community API v2 `/api/2.0/search` JSON/LiQL queries first, then public HTML search/topic pages if API v2 is blocked or unavailable. Spotify Community does not require scraping API credentials.

## Two-Stage Quality Funnel

Phase 1 uses two quality layers:

- Pre-filter during collection: removes obviously unusable candidates before they consume the source budget, including deleted/removed text, very short items, non-English text, generic context-free comments, and items without Spotify discovery/listening context.
- Usability quality gate after normalization: applies the stricter rule-based scoring that determines `quality_passed`, `quality_reason`, `specificity_score`, engagement, conversation, and `signal_weight`.

Only records that pass the usability quality gate are written into `usable_records` and sent to Phase 2 Gemini analysis. Filtered records remain in the source JSON for auditability.

## Usable Data Point

A feedback item is usable when all of these are true:

- It has at least 20 words by default.
- It is English or likely English.
- It contains a Spotify discovery, recommendation, playlist, listening, repetition, or music-behavior signal.
- It contains a specific behavioral signal, not only generic sentiment or broad app commentary.

Items that pass the pre-filter but fail the stricter usability gate are still stored with `quality_passed=false` and a `quality_reason`, so the team can audit what was filtered out.

Passing records also receive deterministic signal scores:

- `specificity_score`: how clearly the text describes a concrete recommendation, discovery, listening, repetition, workaround, or churn behavior.
- `engagement_score`: normalized upvote, like, thumbs-up, kudos, or equivalent public engagement strength when available.
- `conversation_score`: normalized reply or thread-comment strength when available.
- `signal_weight`: bounded `1.0` to `3.0` score used by Phase 2 aggregation so heavily validated feedback influences prioritization more than isolated low-signal comments.

The quality gate decides whether a record is usable. The signal weight decides how strongly a usable record contributes to dashboard rankings.

## Normalized Record Fields

Each collected item is stored with:

- `source`
- `source_query`
- `external_id`
- `created_at`
- `author`
- `text`
- `url`
- `rating`
- `language`
- `word_count`
- `quality_passed`
- `quality_reason`
- `specificity_score`
- `engagement_score`
- `conversation_score`
- `signal_weight`
- `metadata`

Each source JSON also includes `usable_records`, which contains only records where `quality_passed=true`.

## Source Bias Rule

Analysis should first aggregate within each source, then compare convergence across sources. A theme found across stores, Reddit, YouTube, and Spotify Community is stronger evidence than a theme isolated to one source.

## Future Extraction Fields

The next AI extraction pass should create one structured record per usable feedback item with:

- `primary_barrier_type`
- `frustration_categories`
- `listening_intent_context`
- `repetition_type`
- `segment_confidence_scores`
- `workaround_description`
- `severity_score`
- `ongoing_vs_resolved`
- `best_verbatim_quote`
- `extraction_confidence`

Low-confidence AI extractions should be excluded from quantitative aggregation, but can remain available for qualitative review.
