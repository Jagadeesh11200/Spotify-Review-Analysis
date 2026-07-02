from __future__ import annotations


MAX_RECORD_TEXT_CHARS = 2500

SYSTEM_INSTRUCTION = """
You are a senior product research analyst analyzing Spotify feedback about music discovery.
Return only valid JSON. Do not include markdown, prose outside JSON, or comments.
Classify against the provided taxonomies exactly. Use "unclear" when the text does not provide enough evidence.
Be conservative: avoid over-tagging, preserve uncertainty, and quote only short phrases from the review.
Your job is not sentiment analysis. Your job is to infer product mechanisms, listening intent, repetition causes,
segment proxies, and unmet needs from filtered, high-signal feedback.
Source engagement metadata can indicate legitimacy and priority, but it is not evidence for a classification unless the
review text itself supports that classification.
"""


def truncate_text(text: str) -> str:
    if len(text) <= MAX_RECORD_TEXT_CHARS:
        return text
    return text[:MAX_RECORD_TEXT_CHARS].rsplit(" ", 1)[0] + "..."
