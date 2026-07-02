from __future__ import annotations

from pathlib import Path
import json
from typing import Any


def list_ingestion_sessions(base_dir: str | Path = "data/raw") -> list[Path]:
    base = Path(base_dir)
    if not base.exists():
        return []
    return sorted([path for path in base.iterdir() if path.is_dir()], reverse=True)


def load_usable_records(session_dir: str | Path) -> list[dict[str, Any]]:
    path = Path(session_dir)
    records: list[dict[str, Any]] = []
    for source_file in sorted(path.glob("*.json")):
        if source_file.name == "manifest.json":
            continue
        payload = json.loads(source_file.read_text(encoding="utf-8"))
        source_records = payload.get("usable_records")
        if source_records is None:
            source_records = [record for record in payload.get("records", []) if record.get("quality_passed")]
        for index, record in enumerate(source_records):
            record_id = str(record.get("external_id") or f"{source_file.stem}:{index}")
            records.append(
                {
                    "record_id": record_id,
                    "source": record.get("source") or source_file.stem,
                    "created_at": record.get("created_at"),
                    "rating": record.get("rating"),
                    "text": record.get("text", ""),
                    "url": record.get("url"),
                    "author": record.get("author"),
                    "source_query": record.get("source_query"),
                    "word_count": record.get("word_count"),
                    "specificity_score": record.get("specificity_score"),
                    "engagement_score": record.get("engagement_score"),
                    "conversation_score": record.get("conversation_score"),
                    "signal_weight": record.get("signal_weight", 1.0),
                    "metadata": record.get("metadata", {}),
                }
            )
    return records


def load_session_manifest(session_dir: str | Path) -> dict[str, Any]:
    manifest_path = Path(session_dir) / "manifest.json"
    if not manifest_path.exists():
        return {}
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}
