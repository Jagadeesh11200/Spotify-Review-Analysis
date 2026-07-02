from __future__ import annotations

from dataclasses import dataclass
from math import log1p
import re
from typing import Any


DISCOVERY_TERMS = {
    "ai dj",
    "algorithm",
    "artist",
    "autoplay",
    "daily mix",
    "discover",
    "discover weekly",
    "discovery",
    "fresh finds",
    "liked songs",
    "listen",
    "listening",
    "loop",
    "music",
    "new music",
    "playlist",
    "radio",
    "recommend",
    "recommendations",
    "recommends",
    "recommended",
    "recommending",
    "recommendation",
    "repeat",
    "same songs",
    "shuffle",
    "song",
    "spotify",
    "taste profile",
    "track",
    "weekly",
}

PROJECT_RELEVANCE_TERMS = {
    "ai dj",
    "algorithm",
    "artist",
    "autoplay",
    "daily mix",
    "discover",
    "discover weekly",
    "discovery",
    "fresh finds",
    "genre",
    "liked songs",
    "loop",
    "new artist",
    "new artists",
    "new music",
    "playlist",
    "radio",
    "recommend",
    "recommendation",
    "recommendations",
    "recommends",
    "recommended",
    "recommending",
    "release radar",
    "repeat",
    "repeating",
    "same loop",
    "same song",
    "same songs",
    "shuffle",
    "similar artist",
    "similar artists",
    "smart shuffle",
    "taste profile",
}

PROBLEM_TERMS = {
    "bad",
    "broken",
    "can't",
    "cannot",
    "doesn't",
    "dont",
    "don't",
    "gave up",
    "hate",
    "keeps",
    "locked",
    "never",
    "not good",
    "old",
    "repeat",
    "repeating",
    "same",
    "stale",
    "stuck",
    "switched",
    "terrible",
    "wrong",
}

BEHAVIOR_TERMS = {
    "avoid",
    "cancel",
    "commute",
    "discover",
    "find",
    "gym",
    "listen",
    "listening",
    "manual",
    "playlist",
    "recommend",
    "save",
    "search",
    "skip",
    "sleep",
    "switch",
    "use",
    "want",
    "work",
}

CONTEXT_TERMS = {
    "ai dj",
    "apple music",
    "autoplay",
    "bandcamp",
    "daily mix",
    "discover weekly",
    "home",
    "radio",
    "reddit",
    "release radar",
    "taste profile",
    "youtube",
}

WORD_RE = re.compile(r"\b[\w']+\b", re.UNICODE)
SPACE_RE = re.compile(r"\s+")
SHORT_EXACT_TERMS = {"bad", "find", "gym", "home", "loop", "old", "save", "same", "skip", "song", "use", "want", "work"}


@dataclass(frozen=True)
class QualityResult:
    passed: bool
    reason: str
    word_count: int
    specificity_score: float = 0.0


@dataclass(frozen=True)
class PrefilterResult:
    passed: bool
    reason: str
    word_count: int


def clean_text(text: str | None) -> str:
    if not text:
        return ""
    return SPACE_RE.sub(" ", text).strip()


def count_words(text: str) -> int:
    return len(WORD_RE.findall(text))


def is_probably_english(text: str, language: str | None = None) -> bool:
    if language:
        lang = language.lower()
        if lang.startswith("en"):
            return True
        if len(lang) <= 5:
            return False

    letters = [char for char in text if char.isalpha()]
    if not letters:
        return False
    ascii_letters = [char for char in letters if "a" <= char.lower() <= "z"]
    return len(ascii_letters) / len(letters) >= 0.8


def has_discovery_signal(text: str) -> bool:
    lowered = text.lower()
    return any(term_present(lowered, term) for term in DISCOVERY_TERMS)


def has_project_relevance_signal(text: str) -> bool:
    lowered = text.lower()
    return any(term_present(lowered, term) for term in PROJECT_RELEVANCE_TERMS)


def has_problem_or_behavior_signal(text: str) -> bool:
    lowered = text.lower()
    return any(term_present(lowered, term) for term in PROBLEM_TERMS) or any(term_present(lowered, term) for term in BEHAVIOR_TERMS)


def term_present(lowered_text: str, term: str) -> bool:
    if not term:
        return False
    if " " in term:
        return term in lowered_text
    return re.search(rf"\b{re.escape(term)}\b", lowered_text) is not None


def specificity_score(text: str) -> float:
    lowered = text.lower()
    word_count = count_words(text)
    score = 0.0
    if has_discovery_signal(text):
        score += 0.25
    if any(term_present(lowered, term) for term in PROBLEM_TERMS):
        score += 0.25
    if any(term_present(lowered, term) for term in BEHAVIOR_TERMS):
        score += 0.25
    if any(term_present(lowered, term) for term in CONTEXT_TERMS):
        score += 0.15
    if word_count >= 40:
        score += 0.10
    return round(min(score, 1.0), 3)


def assess_quality(
    text: str | None,
    language: str | None = None,
    min_words: int = 20,
    context_text: str | None = None,
) -> QualityResult:
    cleaned = clean_text(text)
    context = clean_text(context_text)
    word_count = count_words(cleaned)
    text_specificity = specificity_score(cleaned)
    contextual_specificity = specificity_score(f"{cleaned} {context}") if context else text_specificity
    specificity = max(text_specificity, contextual_specificity)

    if word_count < min_words:
        return QualityResult(False, "too_short", word_count, specificity)
    if not is_probably_english(cleaned, language):
        return QualityResult(False, "not_english", word_count, specificity)
    if not (has_project_relevance_signal(cleaned) or has_project_relevance_signal(context)):
        return QualityResult(False, "missing_discovery_or_listening_signal", word_count, specificity)
    if context and not has_project_relevance_signal(cleaned) and not has_problem_or_behavior_signal(cleaned):
        return QualityResult(False, "missing_specific_behavior_signal", word_count, specificity)
    if specificity < 0.45:
        return QualityResult(False, "missing_specific_behavior_signal", word_count, specificity)
    return QualityResult(True, "passed", word_count, specificity)


def assess_prefilter(
    text: str | None,
    language: str | None = None,
    min_words: int = 20,
    context_text: str | None = None,
) -> PrefilterResult:
    cleaned = clean_text(text)
    context = clean_text(context_text)
    word_count = count_words(cleaned)
    minimum = max(8, min(min_words, min_words // 2))
    lowered = cleaned.lower()

    if lowered in {"[deleted]", "[removed]", "deleted", "removed"}:
        return PrefilterResult(False, "removed_or_deleted", word_count)
    if word_count < minimum:
        return PrefilterResult(False, "too_short_prefilter", word_count)
    if not is_probably_english(cleaned, language):
        return PrefilterResult(False, "not_english_prefilter", word_count)
    if not (has_project_relevance_signal(cleaned) or has_project_relevance_signal(context)):
        return PrefilterResult(False, "missing_discovery_context_prefilter", word_count)
    if context and not has_project_relevance_signal(cleaned) and not has_problem_or_behavior_signal(cleaned):
        return PrefilterResult(False, "generic_context_comment_prefilter", word_count)
    return PrefilterResult(True, "passed", word_count)


def passes_prefilter(record, min_words: int = 20, context_text: str | None = None) -> bool:
    return assess_prefilter(record.text, record.language, min_words=min_words, context_text=context_text).passed


def numeric_metadata(metadata: dict[str, Any], keys: list[str]) -> float:
    values = []
    for key in keys:
        value = metadata.get(key)
        try:
            if value is not None:
                values.append(float(value))
        except (TypeError, ValueError):
            continue
    return max(values) if values else 0.0


def engagement_values(metadata: dict[str, Any]) -> tuple[float, float]:
    upvotes = numeric_metadata(
        metadata,
        ["score", "thumbs_up_count", "like_count", "favorite_count", "kudos_count"],
    )
    replies = numeric_metadata(metadata, ["num_comments", "reply_count", "thread_reply_count", "comment_reply_count"])
    return max(upvotes, 0.0), max(replies, 0.0)


def engagement_score(metadata: dict[str, Any]) -> float:
    upvotes, _ = engagement_values(metadata)
    return round(min(log1p(upvotes) / log1p(100), 1.0), 3)


def conversation_score(metadata: dict[str, Any]) -> float:
    _, replies = engagement_values(metadata)
    return round(min(log1p(replies) / log1p(50), 1.0), 3)


def signal_weight(specificity: float, engagement: float, conversation: float) -> float:
    return round(min(1.0 + specificity * 0.55 + engagement * 0.65 + conversation * 0.70, 3.0), 3)


def apply_quality(record, min_words: int = 20, context_text: str | None = None):
    result = assess_quality(record.text, record.language, min_words=min_words, context_text=context_text)
    engagement = engagement_score(record.metadata)
    conversation = conversation_score(record.metadata)
    weight = signal_weight(result.specificity_score, engagement, conversation)
    record.text = clean_text(record.text)
    record.word_count = result.word_count
    record.quality_passed = result.passed
    record.quality_reason = result.reason
    record.specificity_score = result.specificity_score
    record.engagement_score = engagement
    record.conversation_score = conversation
    record.signal_weight = weight
    record.metadata["quality_signals"] = {
        "specificity_score": result.specificity_score,
        "engagement_score": engagement,
        "conversation_score": conversation,
        "signal_weight": weight,
    }
    return record
