from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class FeedbackRecord:
    source: str
    source_query: str
    external_id: str
    text: str
    created_at: str | None = None
    author: str | None = None
    url: str | None = None
    rating: float | None = None
    language: str | None = None
    word_count: int = 0
    quality_passed: bool = False
    quality_reason: str = "not_evaluated"
    specificity_score: float = 0.0
    engagement_score: float = 0.0
    conversation_score: float = 0.0
    signal_weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SourceResult:
    source: str
    raw_count: int
    usable_count: int
    filtered_count: int
    output_path: str
    searches: list[str]
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class IngestionResult:
    session_id: str
    session_dir: str
    manifest_path: str
    source_results: list[SourceResult]

    @property
    def total_raw(self) -> int:
        return sum(result.raw_count for result in self.source_results)

    @property
    def total_usable(self) -> int:
        return sum(result.usable_count for result in self.source_results)
