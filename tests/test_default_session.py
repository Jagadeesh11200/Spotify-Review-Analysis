import json
import os
from pathlib import Path

from src.analysis.pipeline import ANALYSIS_CACHE_VERSION
from src.default_session import load_default_run, write_default_session


def write_session(raw_base: Path, analysis_base: Path, session_id: str, usable_count: int = 1) -> None:
    raw_session = raw_base / session_id
    analysis_session = analysis_base / session_id
    raw_session.mkdir(parents=True)
    analysis_session.mkdir(parents=True)
    record = {
        "source": "reddit",
        "source_query": "spotify recommendations",
        "external_id": "reddit:usable-1",
        "text": "Spotify recommendations keep repeating songs and I want better discovery.",
        "quality_passed": True,
        "word_count": 20,
    }
    (raw_session / "reddit.json").write_text(
        json.dumps(
            {
                "source": "reddit",
                "raw_count": usable_count,
                "usable_count": usable_count,
                "filtered_count": 0,
                "records": [record],
                "usable_records": [record],
                "searches": ["spotify recommendations"],
                "errors": [],
            }
        ),
        encoding="utf-8",
    )
    (raw_session / "manifest.json").write_text(
        json.dumps(
            {
                "session_id": session_id,
                "sources": [
                    {
                        "source": "reddit",
                        "raw_count": usable_count,
                        "usable_count": usable_count,
                        "filtered_count": 0,
                        "output_path": str(raw_session / "reddit.json"),
                        "searches": ["spotify recommendations"],
                        "errors": [],
                    }
                ],
                "total_raw": usable_count,
                "total_usable": usable_count,
            }
        ),
        encoding="utf-8",
    )
    (analysis_session / "extractions.json").write_text(
        json.dumps(
            {
                "analysis_cache_version": ANALYSIS_CACHE_VERSION,
                "errors": [],
                "dashboard_insights": {},
                "extractions": [
                    {
                        "record_id": "reddit:usable-1",
                        "source": "reddit",
                        "severity": 4,
                        "extraction_confidence": 0.9,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_load_default_run_uses_persisted_pointer(tmp_path):
    raw_base = tmp_path / "raw"
    analysis_base = tmp_path / "analysis"
    pointer = tmp_path / "default_session.json"
    write_session(raw_base, analysis_base, "session_20260622_145954", usable_count=300)
    write_default_session(
        "session_20260622_145954",
        raw_base / "session_20260622_145954",
        analysis_base / "session_20260622_145954",
        pointer,
    )

    loaded = load_default_run(raw_base, analysis_base, pointer)

    assert loaded is not None
    ingestion, analysis = loaded
    assert ingestion.session_id == "session_20260622_145954"
    assert ingestion.total_usable == 300
    assert analysis["cached"] is True
    assert analysis["source_manifest"]["total_usable"] == 300


def test_load_default_run_falls_back_to_latest_analyzed_session(tmp_path):
    raw_base = tmp_path / "raw"
    analysis_base = tmp_path / "analysis"
    pointer = tmp_path / "missing_pointer.json"
    write_session(raw_base, analysis_base, "session_20260622_111111", usable_count=10)
    write_session(raw_base, analysis_base, "session_20260622_222222", usable_count=20)
    os.utime(analysis_base / "session_20260622_111111", (100, 100))
    os.utime(analysis_base / "session_20260622_222222", (200, 200))

    loaded = load_default_run(raw_base, analysis_base, pointer)

    assert loaded is not None
    ingestion, _ = loaded
    assert ingestion.session_id == "session_20260622_222222"
    assert ingestion.total_usable == 20
