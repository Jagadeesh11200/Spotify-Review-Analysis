from __future__ import annotations

from pathlib import Path
import json
from typing import Any

from src.analysis.pipeline import load_cached_analysis
from src.models import IngestionResult, SourceResult


DEFAULT_SESSION_POINTER = Path("data/default_session.json")


def write_default_session(
    session_id: str,
    session_dir: str | Path,
    analysis_dir: str | Path | None = None,
    pointer_path: str | Path = DEFAULT_SESSION_POINTER,
) -> None:
    path = Path(pointer_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "session_id": session_id,
        "session_dir": str(session_dir),
        "analysis_dir": str(analysis_dir) if analysis_dir is not None else str(Path("data/analysis") / session_id),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_default_run(
    raw_base_dir: str | Path = "data/raw",
    analysis_base_dir: str | Path = "data/analysis",
    pointer_path: str | Path = DEFAULT_SESSION_POINTER,
) -> tuple[IngestionResult, dict[str, Any]] | None:
    session_dir = default_session_dir(raw_base_dir, analysis_base_dir, pointer_path)
    if session_dir is None:
        return None
    analysis = load_cached_analysis(session_dir, analysis_base_dir)
    if not analysis:
        return None
    ingestion = load_ingestion_result(session_dir)
    return ingestion, analysis


def default_session_dir(
    raw_base_dir: str | Path = "data/raw",
    analysis_base_dir: str | Path = "data/analysis",
    pointer_path: str | Path = DEFAULT_SESSION_POINTER,
) -> Path | None:
    pointed = pointed_session_dir(raw_base_dir, analysis_base_dir, pointer_path)
    if pointed is not None:
        return pointed
    return latest_analyzed_session_dir(raw_base_dir, analysis_base_dir)


def pointed_session_dir(
    raw_base_dir: str | Path,
    analysis_base_dir: str | Path,
    pointer_path: str | Path,
) -> Path | None:
    path = Path(pointer_path)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    session_id = str(payload.get("session_id") or "")
    configured_dir = payload.get("session_dir")
    candidates = []
    if configured_dir:
        candidates.append(Path(str(configured_dir)))
    if session_id:
        candidates.append(Path(raw_base_dir) / session_id)
    for candidate in candidates:
        if is_complete_analyzed_session(candidate, analysis_base_dir):
            return candidate
    return None


def latest_analyzed_session_dir(raw_base_dir: str | Path, analysis_base_dir: str | Path) -> Path | None:
    analysis_base = Path(analysis_base_dir)
    if not analysis_base.exists():
        return None
    for analysis_dir in sorted((path for path in analysis_base.iterdir() if path.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True):
        session_dir = Path(raw_base_dir) / analysis_dir.name
        if is_complete_analyzed_session(session_dir, analysis_base_dir):
            return session_dir
    return None


def is_complete_analyzed_session(session_dir: Path, analysis_base_dir: str | Path) -> bool:
    if not (session_dir / "manifest.json").exists():
        return False
    analysis_dir = Path(analysis_base_dir) / session_dir.name
    return (analysis_dir / "extractions.json").exists()


def load_ingestion_result(session_dir: str | Path) -> IngestionResult:
    path = Path(session_dir)
    manifest_path = path / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_results = [
        SourceResult(
            source=str(source.get("source", "")),
            raw_count=int(source.get("raw_count") or 0),
            usable_count=int(source.get("usable_count") or 0),
            filtered_count=int(source.get("filtered_count") or 0),
            output_path=str(source.get("output_path") or path / f"{source.get('source', 'source')}.json"),
            searches=[str(query) for query in source.get("searches", []) if query is not None],
            errors=[str(error) for error in source.get("errors", []) if error is not None],
        )
        for source in payload.get("sources", [])
        if isinstance(source, dict)
    ]
    return IngestionResult(
        session_id=str(payload.get("session_id") or path.name),
        session_dir=str(path),
        manifest_path=str(manifest_path),
        source_results=source_results,
    )
