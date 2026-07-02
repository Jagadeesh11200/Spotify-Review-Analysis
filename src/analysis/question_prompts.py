from __future__ import annotations

import json
from typing import Any

from src.analysis.prompts import MAX_RECORD_TEXT_CHARS, truncate_text
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
    SPOTIFY_FEATURES,
    SUBSCRIPTION_SIGNALS,
    UNMET_NEEDS,
    CHURN_SIGNAL_TYPES,
    USER_GOALS,
)


QUESTION_KEYS = ["q1", "q2", "q3", "q4", "q5", "q6"]


def compact_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "record_id": record["record_id"],
            "source": record.get("source"),
            "created_at": record.get("created_at"),
            "rating": record.get("rating"),
            "word_count": record.get("word_count"),
            "signal_weight": record.get("signal_weight", 1.0),
            "engagement_score": record.get("engagement_score", 0.0),
            "conversation_score": record.get("conversation_score", 0.0),
            "source_context": source_context(record),
            "text": truncate_text(record.get("text") or ""),
        }
        for record in records
    ]


def source_context(record: dict[str, Any]) -> dict[str, Any]:
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    return {
        "kind": metadata.get("kind"),
        "upvote_or_like_signal": first_present(metadata, ["score", "thumbs_up_count", "like_count", "favorite_count", "kudos_count"]),
        "reply_or_comment_signal": first_present(metadata, ["num_comments", "reply_count", "thread_reply_count", "comment_reply_count"]),
        "source_query": record.get("source_query"),
        "thread_or_video_title": first_present(metadata, ["post_title", "video_title", "title"]),
        "source_surface": first_present(metadata, ["subreddit", "video_channel", "query_type", "hashtag"]),
        "source_actor": metadata.get("source_actor"),
        "conversation_id": metadata.get("conversation_id"),
        "message_position": metadata.get("message_position"),
        "quality_scores": {
            "specificity": record.get("specificity_score"),
            "engagement": record.get("engagement_score"),
            "conversation": record.get("conversation_score"),
            "signal_weight": record.get("signal_weight", 1.0),
        },
    }


def first_present(metadata: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if metadata.get(key) is not None:
            return metadata.get(key)
    return None


def build_question_prompt(question_key: str, records: list[dict[str, Any]]) -> str:
    builders = {
        "q1": build_q1_prompt,
        "q2": build_q2_prompt,
        "q3": build_q3_prompt,
        "q4": build_q4_prompt,
        "q5": build_q5_prompt,
        "q6": build_q6_prompt,
    }
    return builders[question_key](records)


def json_shape(fields: str) -> str:
    return f"""
Return only JSON in this shape:
{{
  "analyses": [
    {{
      "record_id": "string",
{fields}
    }}
  ]
}}
"""


def build_q1_prompt(records: list[dict[str, Any]]) -> str:
    return f"""
Q1 - Why do users struggle to discover new music?

You are building a causal model of discovery failure. Do not produce a generic sentiment label.
Classify the dominant mechanism by which the user fails to encounter music they would have valued.
The core product question is controlled freshness: users want novelty, but novelty must still feel
safe, relevant, mood-aware, culturally aware, and worth their time.

Barrier taxonomy. Choose exactly one primary barrier:
- algorithmic: Spotify's model of the user's taste is wrong, narrow, outdated, over-indexed on old history,
  trapped in a small taste loop, or unable to represent multiple listening contexts. Signals:
  "it only ever recommends", "no matter what I do", "it thinks I only like", "used to know my taste".
- surface: discovery architecture is not legible. The user does not know where to go, how to start,
  what feature to use, or how Home/Browse/Search/Radio/Discover Weekly/Release Radar should be used.
- trust: the user has lost confidence that recommendations will be good. They ignore discovery surfaces,
  have given up, use manual alternatives, or no longer bother clicking recommendation features.
- cognitive: discovery feels too noisy, complex, choice-heavy, or overwhelming; friction creates paralysis.
- unclear: no clear mechanism.

Growth PM discovery barriers. Choose one primary_discovery_barrier:
- over_personalization: personalization overfits old listening, creating a taste bubble.
- low_recommendation_trust: user no longer believes Spotify understands their current need.
- repetition_fatigue: same songs, artists, playlists, radios, or mixes create staleness.
- hidden_discovery_paths: user does not know where to go or discovery is too passive/buried.
- mood_mismatch: recommendations may match history but not current emotional/activity context.
- regional_language_mismatch: language, culture, region, or local genre preferences are misunderstood.
- lack_of_control: user wants to tune freshness, familiarity, depth, genre, risk, or mainstreamness.
- unclear: no clear PM barrier.

Novelty-safety state:
- too_familiar: recommendations are relevant but stale, repetitive, or unsurprising.
- too_unfamiliar: recommendations are too random, jarring, or mismatched.
- wants_safe_novelty: user explicitly or implicitly wants fresh music that still fits their world.
- comfort_preferred: user is primarily choosing familiarity and not asking to escape it.
- unclear: no novelty-safety signal.

Recommendation/discovery failure modes. Select every mode supported by the text:
- same_songs_repeating: same tracks are repeatedly recommended or played.
- known_artists_dominating: known artists or already-discovered artists crowd out fresh discovery.
- playlist_predictability: playlists/mixes feel predictable, static, or library-like.
- discover_weekly_stale: Discover Weekly/Made for You feels weaker, stale, or no longer magical.
- radio_too_narrow: radio/artist radio keeps a narrow cluster rather than adjacent discovery.
- shuffle_non_random: shuffle feels repetitive or non-random inside the user's own library.
- mood_mismatch: current mood/activity does not match recommendations.
- regional_mismatch: language, culture, region, or local genre fit is poor.
- too_mainstream: recommendations are obvious, popular, or not deep enough.
- taste_profile_outdated: Spotify reflects old taste, not current taste.

Rules:
- Force a single primary barrier even if multiple symptoms appear.
- Include secondary_barrier_type only if the text clearly supports a second mechanism.
- Add discovery_failure_modes only when the review gives enough evidence; multiple modes may apply.
- Choose novelty_safety_state based on the user's tolerance for familiarity vs freshness.
- Extract a short quote that proves the primary barrier.
- Flag named Spotify features because feature-specific failures are more actionable.
- Confidence should be high only when mechanism and quote are clear.

Allowed primary values: {json.dumps(Q1_BARRIER_TYPES)}
Allowed PM barriers: {json.dumps(DISCOVERY_BARRIERS_PM)}
Allowed novelty-safety states: {json.dumps(NOVELTY_SAFETY_STATES)}
Allowed discovery failure modes: {json.dumps(DISCOVERY_FAILURE_MODES)}
Spotify features to flag: {json.dumps(SPOTIFY_FEATURES)}

{json_shape('''      "primary_barrier_type": "algorithmic|surface|trust|cognitive|unclear",
      "primary_discovery_barrier": "one allowed PM barrier",
      "novelty_safety_state": "one allowed novelty-safety state",
      "barrier_evidence_quote": "short quote or empty string",
      "secondary_barrier_type": "algorithmic|surface|trust|cognitive|unclear",
      "discovery_failure_modes": ["allowed discovery failure mode"],
      "named_features": ["feature names"],
      "q1_confidence": 0.0''')}

Records:
{json.dumps(compact_records(records), ensure_ascii=False)}
"""


def build_q2_prompt(records: list[dict[str, Any]]) -> str:
    return f"""
Q2 - What are the most common frustrations with recommendations?

You are building a prioritized bug map for the recommendation system. This is more granular than Q1.
Identify all recommendation failure categories present in each record. Multiple categories may apply.

Frustration taxonomy:
- filter_bubble_lock_in: algorithm converges on a narrow taste representation and refuses to explore.
- taste_model_staleness: recommendations reflect who the user used to be, not current taste.
- wrong_context_genre_blending: genre/energy mix breaks a listening context such as work, sleep, gym, commute, or social.
- autoplay_regression: quality drops when Spotify takes over after chosen content ends.
- popularity_bias: recommendations default to mainstream/obvious artists instead of deeper, obscure, emerging, or niche music.
- context_unawareness: broad taste is right but time, mood, activity, setting, or emotional context is wrong.
- recommendation_opacity: user cannot understand why a track was recommended, weakening trust or learning.

User-facing frustration themes. Select every theme supported by the text:
- same_songs_repeating: "I want freshness, not listening history recycled."
- known_artists_dominating: "I want artists outside my current bubble."
- playlist_predictability: "Spotify knows my taste, but is no longer surprising me."
- discover_weekly_stale: "The discovery product lost its magic."
- radio_too_narrow: "Songs like this should mean similar vibe, not the same cluster."
- shuffle_non_random: "I want variety inside my library."
- mood_mismatch: "My current situation matters more than long-term history."
- regional_mismatch: "My language or cultural taste is not handled carefully."
- too_mainstream: "I want deeper, niche, or less obvious recommendations."
- taste_profile_outdated: "Spotify is recommending for who I used to be."

Severity scoring:
- 1: neutral/light mention.
- 2: clear frustration but no major behavior change.
- 3: strong language like always/never/broken/awful or repeated annoyance.
- 4: behavioral change such as stopped using, gave up, manual workaround, avoids a feature.
- 5: explicit switching/leaving, severe disruption, or very high-stakes failure.

Status:
- ongoing unless the user clearly says it was fixed/resolved.
- resolved only for explicitly historical/solved issues.
- unclear when impossible to tell.

Allowed categories: {json.dumps(Q2_FRUSTRATION_CATEGORIES)}
Allowed user-facing themes: {json.dumps(DISCOVERY_FAILURE_MODES)}

{json_shape('''      "frustrations": [
        {
          "category": "one allowed category",
          "severity": 1,
          "status": "ongoing|resolved|unclear",
          "evidence_quote": "short quote"
        }
      ],
      "recommendation_frustration_themes": ["allowed user-facing theme"],
      "overall_severity": 1,
      "ongoing_vs_resolved": "ongoing|resolved|unclear",
      "best_verbatim_quote": "single best quote for recommendation frustration",
      "q2_confidence": 0.0''')}

Records:
{json.dumps(compact_records(records), ensure_ascii=False)}
"""


def build_q3_prompt(records: list[dict[str, Any]]) -> str:
    return f"""
Q3 - What listening behaviors are users trying to achieve?

Reconstruct intent, not failure. Identify what the user was trying to accomplish with Spotify,
the listening context they were in, their mental posture toward discovery, and what success would
have looked like. This should read like product research, not generic sentiment analysis.

Activity context categories:
{json.dumps(Q3_ACTIVITY_CONTEXTS)}

Activity context inference guide. Use direct mentions first, then strong linguistic clues:
- commuting_or_traveling: car, drive, commute, train, bus, walk, flight, travel, road trip.
- focused_work_or_studying: work, office, coding, studying, focus, productivity, concentration.
- physical_exercise: gym, workout, running, cycling, exercise, training.
- cooking_or_household_tasks: cooking, cleaning, chores, shower, household routine.
- social_listening: party, friends, group, shared speaker, guests, road trip with others.
- relaxing_at_home_passively: home, evening, couch, relaxing, casual listening, winding down without sleep.
- falling_asleep_or_winding_down: sleep, bedtime, night, fall asleep, calm down, insomnia.
- creative_work: DJing, making playlists for others, writing, art, content creation, music research.
- background_fill: background, radio on, autoplay, leave it playing, passive ambiance.
- unclear: no direct or strong contextual clue after considering the above.

Discovery mode:
- active: user intentionally came to find new music and is willing to search, seed radio, compare artists,
  build playlists, curate, or evaluate unfamiliar tracks.
- lean_back: user wants good music to find them passively through Discover Weekly, AI DJ, Radio, Autoplay,
  Home, Daily Mix, or recommendations without navigation/evaluation effort.
- incidental: user mainly wanted familiar or routine listening, but would welcome discovery if it appeared naturally.
- unclear: insufficient signal.

User goal categories. Select every goal supported by the text:
- comfort_listening: familiar music that feels safe, reliable, nostalgic, or emotionally predictable.
- mood_based_listening: music that matches current emotion, vibe, energy, or atmosphere.
- activity_based_listening: music for gym, work, travel, sleep, party, focus, cooking, chores, or commute.
- taste_expansion: discover new artists/genres without wasting time.
- social_discovery: find music through friends, trends, shared identity, creators, or communities.
- identity_building: music taste as self-expression, uniqueness, expertise, or personal identity.
- deep_exploration: less obvious, more niche, more surprising, underground, or adjacent discovery.
- passive_freshness: Spotify should refresh listening without extra effort.
- fresh_music_without_effort: user wants Spotify to bring fresh music with low effort or passive discovery.
- match_current_mood: user wants recommendations to fit current mood, energy, activity, or moment.
- safe_adjacent_genre_exploration: user wants to explore nearby genres/scenes without jarring irrelevant leaps.
- similar_but_not_same: user wants music like a song/artist/vibe, but not the same song, artist, or playlist again.
- escape_repetitive_playlists: user wants to break out of repeated playlists, radio loops, or autoplay loops.
- build_music_identity: user treats discovery as identity, taste-building, expertise, self-expression, or being a music person.

Rules:
- Do not overuse unclear. Choose unclear only after checking direct mentions and strong clues above.
- Do not invent a context from the source platform alone. A YouTube comment is not automatically social; an
  App Store review is not automatically casual.
- Extract desired_outcome as the user's success state, not the failure.
- If desired outcome is implied, phrase it conservatively.
- Quote the phrase that signals context, mode, or desired outcome.
- If a review only says recommendations are repetitive but no setting is visible, activity_context should be
  unclear, discovery_mode is usually lean_back, and desired_outcome is usually broader relevant discovery.
- effort_tolerance should be low_effort when the user wants freshness in-flow, willing_to_explore when they
  search/curate/seed intentionally, advanced_control when they ask for tuning/depth/sliders/filters, and
  unclear when not supported.

Allowed activity contexts: {json.dumps(Q3_ACTIVITY_CONTEXTS)}
Allowed discovery modes: {json.dumps(Q3_DISCOVERY_MODES)}
Allowed user goal categories: {json.dumps(USER_GOALS)}

{json_shape('''      "activity_context": "one allowed activity context",
      "discovery_mode": "active|lean_back|incidental|unclear",
      "user_goals": ["allowed user goal"],
      "effort_tolerance": "low_effort|willing_to_explore|advanced_control|unclear",
      "desired_outcome": "what success would have looked like, or empty string",
      "intent_evidence_quote": "short quote or empty string",
      "q3_confidence": 0.0''')}

Records:
{json.dumps(compact_records(records), ensure_ascii=False)}
"""


def build_q4_prompt(records: list[dict[str, Any]]) -> str:
    return f"""
Q4 - What causes users to repeatedly listen to the same content?

Do not assume repetition is bad. Separate intentional repetition from failure-state repetition.

Repetition typology:
- comfort_ritual: intentional familiar listening for comfort, nostalgia, emotional regulation, routine, or ownership.
  This is not a product failure.
- algorithm_trapped: user wants variety but Spotify cycles the same artists/songs/playlists despite attempts to change.
- trust_deficit: user repeats familiar content because they no longer trust Spotify recommendations.
- friction_induced: user repeats familiar content because finding new music requires too much effort, navigation, or attention.
- not_mentioned: repetition is not mentioned.
- unclear: repetition is mentioned but the cause cannot be inferred.

Repeat-driver categories. Select every driver supported by the text:
- habit_loop: user defaults to liked songs, saved playlists, familiar artists, or routine listening.
- algorithmic_reinforcement: past behavior appears to narrow future recommendations into a feedback loop.
- low_discovery_confidence: user avoids new songs because they expect skips, mismatch, or bad recommendations.
- playlist_dependency: repeated listening comes from relying on a few playlists, Liked Songs, Daily Mix, or saved collections.
- mood_safety: familiar songs provide predictable emotional comfort, safety, nostalgia, or regulation.
- weak_exploration_controls: user cannot control novelty, freshness, mainstreamness, genre, language, or depth.
- poor_first_song_risk: first few recommendations fail, causing the user to return to familiar content.
- time_pressure: user needs music immediately and does not want to search/evaluate.

Rules:
- Set repetition_intentional true only for comfort_ritual or clearly chosen repetition.
- Set desire_to_change_repetition true when the user wants more variety/discovery but remains stuck.
- Add repetition_drivers for the user-visible reason behind repetition; multiple drivers can apply.
- repetition_type should be intentional_comfort when clearly desired, unwanted_loop when the user wants escape,
  mixed when comfort and frustration coexist, mapped back to the allowed legacy value that best fits.
- Extract the evidence quote proving the cause.

Allowed values: {json.dumps(Q4_REPETITION_TYPES)}
Allowed repeat drivers: {json.dumps(REPETITION_DRIVERS)}

{json_shape('''      "repetition_type": "one allowed repetition type",
      "repetition_drivers": ["allowed repeat driver"],
      "repetition_intentional": false,
      "desire_to_change_repetition": false,
      "repetition_evidence_quote": "short quote or empty string",
      "q4_confidence": 0.0''')}

Records:
{json.dumps(compact_records(records), ensure_ascii=False)}
"""


def build_q5_prompt(records: list[dict[str, Any]]) -> str:
    return f"""
Q5 - Which user segments experience different discovery challenges, and how intensely are they using Spotify?

You only have review text. These are segment proxies, not measured segments.
Score every record against every proxy from 0.0 to 1.0, list evidence phrases, and only assign
top_segment when the top proxy score is >= 0.70 and the gap to second place is >= 0.25.
Otherwise use unclassified.

Segment proxy definitions:
- comfort_listener: repeatedly returns to familiar artists, saved playlists, liked songs, nostalgia, routine,
  or emotional reliability; may need gentle freshness without losing comfort.
- playlist_heavy_user: Control-first listener who relies on Liked Songs, Daily Mix, self-created playlists,
  genre playlists, or radio from playlists; often trapped in shuffle/radio/autoplay loops.
- active_explorer: Discovery-frustrated explorer who actively wants new music and complains about mainstream,
  obvious, shallow, or repetitive discovery.
- mood_based_listener: chooses music by mood, emotion, energy, activity, atmosphere, sleep, focus, gym, travel, or social setting.
- regional_language_listener: mentions language, country, local music, culture, regional identity, multilingual taste, or cultural fit.
- artist_loyal_user: repeatedly listens to specific artists, artist radio, fandom clusters, or wants broader scenes near an artist.
- casual_listener: low-effort listener who wants simple freshness and may not know where to start.
- premium_power_user: heavy/paying/advanced user who expects smarter personalization, notices repetition quickly,
  mentions Premium/payment, or asks for advanced controls.

Subscription signal is an attribute, not the main segment:
- premium: user explicitly mentions Premium, paying, subscription, family/student plan, or paid expectations.
- free: user explicitly mentions free tier, ads, limited skips, shuffle/control limits, or unpaid constraints.
- unknown: no subscription clue.

Listening intensity:
- high: near-constant use, explicit hour counts above three, Spotify/music on all day, or music as a primary daily anchor.
- medium: daily habit, regular commute/routine use, or repeated sessions without all-day language.
- low: occasional use, activity-gated use, infrequent language, or no frequency signal in the text.

Churn risk:
- churn_risk should be true when the user indicates switching, cancelling, leaving, disabling a core feature,
  giving up on discovery, avoiding recommendation surfaces, or moving discovery behavior to another platform.
- churn_signal_type values:
  - none: no disengagement signal.
  - disengagement: stopped using a feature, avoids recommendations, gave up trying, only uses old playlists.
  - switching: uses Apple Music, YouTube, Reddit, Bandcamp, friends, blogs, or another method instead of Spotify for the job.
  - exit_intent: threatens to leave, says they may cancel, or says Spotify is pushing them away.
  - cancelled: explicit past cancellation or completed switch.

Allowed segment keys: {json.dumps(Q5_SEGMENTS)}
Allowed intensity values: {json.dumps(Q5_INTENSITY_LEVELS)}
Allowed subscription signals: {json.dumps(SUBSCRIPTION_SIGNALS)}
Allowed churn signal values: {json.dumps(CHURN_SIGNAL_TYPES)}

{json_shape('''      "segment_scores": {
        "comfort_listener": 0.0,
        "playlist_heavy_user": 0.0,
        "active_explorer": 0.0,
        "mood_based_listener": 0.0,
        "regional_language_listener": 0.0,
        "artist_loyal_user": 0.0,
        "casual_listener": 0.0,
        "premium_power_user": 0.0
      },
      "segment_evidence": {
        "comfort_listener": [],
        "playlist_heavy_user": [],
        "active_explorer": [],
        "mood_based_listener": [],
        "regional_language_listener": [],
        "artist_loyal_user": [],
        "casual_listener": [],
        "premium_power_user": []
      },
      "top_segment": "comfort_listener|playlist_heavy_user|active_explorer|mood_based_listener|regional_language_listener|artist_loyal_user|casual_listener|premium_power_user|unclassified",
      "segment_confidence_gap": 0.0,
      "listening_intensity": "high|medium|low",
      "intensity_evidence_quote": "short quote or empty string",
      "subscription_signal": "premium|free|unknown",
      "subscription_evidence_quote": "short quote or empty string",
      "churn_risk": false,
      "churn_signal_type": "none|disengagement|switching|exit_intent|cancelled",
      "churn_evidence_quote": "short quote or empty string",
      "q5_confidence": 0.0''')}

Records:
{json.dumps(compact_records(records), ensure_ascii=False)}
"""


def build_q6_prompt(records: list[dict[str, Any]]) -> str:
    return f"""
Q6 - What unmet needs emerge consistently?

Users rarely state unmet needs directly. Infer them only when the record shows a compensating behavior,
an external method, or resignation to a product limitation.

Unmet need themes to look for:
- freshness_control: control how much new music appears.
- familiarity_balance: new songs should still fit the user's taste world.
- better_variety: less repetition across playlists, radio, autoplay, shuffle, and mixes.
- mood_awareness: recommendations should reflect current emotional/activity context.
- language_culture_relevance: recommendations should respect regional, language, and cultural preferences.
- discovery_transparency: users need to know why something was recommended and how to correct it.
- low_effort_exploration: discovery should happen without heavy manual searching.
- deeper_discovery: discovery-frustrated explorers want niche, underground, less obvious, adjacent music.
- playlist_evolution: playlists should grow/refine without becoming messy or stale.
- trust_recovery: users need a way to repair Spotify's understanding when it gets taste wrong.

Opportunity areas:
- freshness_control: slider/mode from familiar to adventurous.
- playlist_refresh: replace repeated tracks with fresh similar tracks.
- mood_aware_discovery: fresh songs for the current vibe/activity.
- language_aware_discovery: stronger regional/multilingual tuning.
- deep_discovery: go deeper into niche/adjacent artists.
- recommendation_repair: "Spotify got my taste wrong" correction flow.
- discovery_explanation: explain why a song appears.
- less_repeat_mode: session or playlist mode that actively reduces repeats.

Rules:
- Do not invent a need when the text only says recommendations are bad.
- Use concrete user behavior as the description.
- Phrase underlying_need as a stable product need, not a complaint.
- Phrase feature_hypothesis as a possible Spotify capability, not a final roadmap promise.
- Extract the user behavior or resignation phrase as a short quote.
- For competitive displacement, capture whether the user returns to Spotify or migrates away when stated.
- Extract unmet_need_tags and opportunity_area only when supported by the behavior/complaint/workaround.

Allowed unmet needs: {json.dumps(UNMET_NEEDS)}
Allowed opportunity areas: {json.dumps(OPPORTUNITY_AREAS)}

{json_shape('''      "workarounds": [
        {
          "description": "what the user does manually or outside the ideal flow",
          "underlying_need": "need served by the workaround",
          "feature_hypothesis": "feature that could remove the workaround",
          "quote": "short quote"
        }
      ],
      "competitive_displacements": [
        {
          "platform_or_method": "YouTube|Reddit|Apple Music|Bandcamp|friends|blogs|notes|other",
          "need_served": "what they get there that Spotify does not provide",
          "migration_status": "returned_to_spotify|partial_migration|full_migration|unclear",
          "quote": "short quote"
        }
      ],
      "resignation_signals": [
        {
          "accepted_limitation": "what the user has accepted",
          "need_statement": "unmet need",
          "quote": "short quote"
        }
      ],
      "unmet_need_tags": ["allowed unmet need"],
      "opportunity_area": "one allowed opportunity area or unclear",
      "q6_confidence": 0.0''')}

Records:
{json.dumps(compact_records(records), ensure_ascii=False)}
"""
