from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Any

from src.models import FeedbackRecord, SourceResult


def create_session_dir(base_dir: str | Path = "data/raw") -> tuple[str, Path]:
    session_id = datetime.now(timezone.utc).strftime("session_%Y%m%d_%H%M%S")
    path = Path(base_dir) / session_id
    path.mkdir(parents=True, exist_ok=True)
    return session_id, path


def save_source_records(
    session_dir: Path,
    source: str,
    records: list[FeedbackRecord],
    searches: list[str],
    date_range: dict[str, str],
    errors: list[str] | None = None,
) -> SourceResult:
    output_path = session_dir / f"{source}.json"
    payload: dict[str, Any] = {
        "source": source,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date_range": date_range,
        "searches": searches,
        "raw_count": len(records),
        "usable_count": sum(1 for record in records if record.quality_passed),
        "filtered_count": sum(1 for record in records if not record.quality_passed),
        "records": [record.to_dict() for record in records],
        "usable_records": [record.to_dict() for record in records if record.quality_passed],
        "errors": errors or [],
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return SourceResult(
        source=source,
        raw_count=payload["raw_count"],
        usable_count=payload["usable_count"],
        filtered_count=payload["filtered_count"],
        output_path=str(output_path),
        searches=searches,
        errors=errors or [],
    )


def save_manifest(
    session_dir: Path,
    session_id: str,
    source_results: list[SourceResult],
    config: dict[str, Any],
) -> str:
    manifest_path = session_dir / "manifest.json"
    payload = {
        "session_id": session_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "sources": [result.to_dict() for result in source_results],
        "total_raw": sum(result.raw_count for result in source_results),
        "total_usable": sum(result.usable_count for result in source_results),
    }
    manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(manifest_path)
